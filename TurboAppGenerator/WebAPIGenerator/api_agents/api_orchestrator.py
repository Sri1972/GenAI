"""
ApiCrewOrchestrator — runs shared agents through an API-focused pipeline
to build production-grade REST APIs.

Stages:
  1. architecture   — API Architect designs resources, endpoints, auth model
  2. data_modeling  — Data Architect designs schema + models (shared with UI pipeline)
  3. implementation — Services Engineer generates routes, services, models, config
  4. security       — deterministic middleware (rate limit, usage log, basic auth) for
                      auth_type in (none, basic); falls back to an LLM security stage
                      for auth_type in (api_key, jwt)
  5. testing        — Test Engineer generates tests, OpenAPI spec, docs
  6. packaging      — DevOps generates Dockerfile, docker-compose, health checks

Reuses WebUIGenerator's shared agents.llm for LLM calls (see api_config.py's docstring
for why this project's own modules are named api_agents/api_config to avoid collision).
"""

import json
import os
import re
import secrets
from pathlib import Path
from typing import Callable, Optional

from AgentPlatform.core.codegen_verify import CodegenVerifyMixin

USE_SDK_AGENTS = os.environ.get("USE_SDK_AGENTS", "").lower() in ("true", "1", "yes")

API_STAGES = [
    {
        "id": "architecture",
        "name": "API Architecture",
        "description": "Design resources, endpoints, relationships, auth model",
    },
    {
        "id": "data_modeling",
        "name": "Data Modeling",
        "description": "Design database schema, models, and migrations",
    },
    {
        "id": "implementation",
        "name": "API Implementation",
        "description": "Generate routes, services, validation, config",
    },
    {
        "id": "security",
        "name": "Security & Middleware",
        "description": "Auth, rate limiting, CORS, error handling",
    },
    {
        "id": "testing",
        "name": "Testing & Documentation",
        "description": "Tests, OpenAPI spec, README, test harness",
    },
    {
        "id": "packaging",
        "name": "Packaging & Deploy",
        "description": "Dockerfile, docker-compose, health checks, .env template",
    },
]


class ApiCrewOrchestrator(CodegenVerifyMixin):
    """
    Orchestrates shared agents to build a production-grade REST API.

    Reuses the same agent pool as CrewOrchestrator but with API-mode prompts
    that activate full production capabilities (auth, rate limiting, tests, Docker).

    The boot-check-and-repair verification pipeline (compile/import checks,
    real throwaway-server boot checks, LLM repair calls) lives in
    CodegenVerifyMixin (AgentPlatform/core/codegen_verify.py) — shared with
    WebUIGenerator's own per-entity generation, not duplicated.
    """

    # Entities per Stage-3 implementation call — a middle ground between one
    # monolithic call (no progress visibility, real truncation risk on a
    # large API) and one call per entity (finest-grained progress, but the
    # most independent-call disagreement opportunities). 3 was chosen to cut
    # entity-implementation calls roughly 3x versus one-per-entity while still
    # reporting real incremental progress every batch.
    _ENTITY_BATCH_SIZE = 3

    # Coarse type categories used by _reconcile_schema_types_with_entities to
    # detect schema.sql/entity type disagreement without needing a full,
    # precise type system — just enough to catch "a numeric column got a
    # text declaration or vice versa", the exact failure class reproduced
    # directly (schema.sql: `id TEXT`, entity: `Long id` -> Hibernate builds
    # an INTEGER column, seed data written against schema.sql's TEXT
    # declaration fails to insert with "datatype mismatch").
    _JAVA_TYPE_CATEGORY = {
        "long": "integer", "integer": "integer", "int": "integer",
        "short": "integer", "byte": "integer", "boolean": "integer",
        "double": "real", "float": "real", "bigdecimal": "real",
        "string": "text", "localdate": "text", "localdatetime": "text", "instant": "text",
    }
    _PYTHON_TYPE_CATEGORY = {
        "int": "integer", "integer": "integer", "bigint": "integer",
        "smallint": "integer", "bool": "integer", "boolean": "integer",
        "float": "real", "numeric": "real", "double": "real",
        "str": "text", "string": "text", "date": "text", "datetime": "text", "text": "text",
    }
    # SQL-side categories come from AgentPlatform.core.codegen_batching's
    # sql_type_category — shared with WebUIGenerator's seed-vs-live-schema
    # check (uigen_agent.py) so both sides of this pipeline agree on the
    # same numeric/text/blob judgment instead of keeping two copies that
    # could quietly drift apart.
    _CANONICAL_SQL_TYPE = {"integer": "INTEGER", "real": "REAL", "text": "TEXT", "blob": "BLOB"}

    def __init__(self, progress: Optional[Callable] = None):
        self.progress = progress
        self.artifacts: dict[str, str] = {}
        self.files: dict[str, str] = {}
        self.api_options: dict = {}
        # Snapshotted right after bootstrap finishes (see generate()) — every
        # entity call needs these files' EXACT contents (e.g. PagedResponse's
        # real constructor signature), not a truncated/possibly-dropped
        # summary. _files_summary() caps total size and sorts alphabetically,
        # so a shared DTO could silently fall out of context by the 6th+
        # entity once enough other files pile up — that's what let entities
        # call PagedResponse's constructor with the wrong argument count/order,
        # each independently guessing a plausible-looking signature instead of
        # reading the real one.
        self._shared_contract_paths: set[str] = set()
        # Set once the architecture stage resolves a project name (see generate()).
        # Every stage flushes to this directory as it finishes, instead of the
        # caller writing everything in one shot only after the whole pipeline
        # returns — a failure late in the pipeline (e.g. Stage 6, or even a
        # runtime startup crash after generation itself "succeeded") used to
        # discard every already-generated file, including entities implemented
        # several minutes earlier, since nothing had touched disk yet.
        self.project_dir: Optional[Path] = None

        # Real catalog agents (AgentPlatform/catalog/) for the two stages that
        # map onto an actual persona — Implementation (route/service/repo code)
        # and Security (jwt/api_key middleware). Instantiated once and reused
        # across every call site in a run, rather than re-reading config.yaml
        # per LLM call. Everything else in this class stays orchestration
        # plumbing (batching, disk flushing, per-language deterministic
        # patchers) — see AgentPlatform/catalog/api_services_engineer/'s and
        # api_security_engineer/'s own docstrings for why only these two split
        # out.
        from AgentPlatform.core.registry import get_agent
        self._services_agent = get_agent("api_services_engineer")
        self._security_agent = get_agent("api_security_engineer")
        self._architect_agent = get_agent("api_architect")
        self._data_architect_agent = get_agent("api_data_architect")

    def _p(self, msg: str):
        if self.progress:
            self.progress(msg)
        print(f"[api-crew] {msg}", flush=True)

    def _flush_to_disk(self):
        """Write every file currently in self.files to self.project_dir. A full
        flush (not just newly-added files) so it's correct regardless of
        whether the latest change was a new file or a fixup that rewrote an
        existing one (e.g. _ensure_java_seed_data_disabled_in_spring patching
        application.properties) — those mutate self.files directly rather than
        going through a merge call, so tracking "just the delta" would miss them."""
        if not self.project_dir:
            return
        for fpath, content in self.files.items():
            out = self.project_dir / fpath
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 32000) -> dict:
        """Call the LLM directly with system + user prompts, expecting JSON response."""
        # Reuses WebUIGenerator's shared LLM client — WebUIGenerator stays on
        # sys.path and owns the `agents` package name (see api_config.py's docstring).
        from agents.llm import chat_json
        messages = [{"role": "user", "content": user_prompt}]
        return chat_json(messages, system=system_prompt, max_tokens=max_tokens)

    def _architecture_shape_problems(self, arch_result: dict) -> list[str]:
        """
        Check that 'entities' and 'endpoints' are actually lists of objects,
        not some other type the model occasionally substitutes under real
        strain — reproduced directly on a complex, correlation-heavy schema
        (multiple tables with cross-references, weighted seed distributions):
        the model returned 'entities' as one long free-text string instead
        of a proper array. That passes _recover_expected_shape (the key
        "entities" IS present at the top level — it's the right SHAPE at
        the wrong TYPE), then silently corrupts the progress log
        (len() on a string reports its character count — is how a 3-table
        app produced a logged "4647 entities") before crashing deep in
        unrelated code (`for e in data_entities: e.get("name")` — `e` is a
        single character, not an entity object) with a cryptic AttributeError
        that gives no hint the real problem is several calls upstream.
        Returns a list of human-readable problems, empty if the shape is fine.
        """
        problems = []
        entities = arch_result.get("entities")
        if not isinstance(entities, list):
            problems.append(f"'entities' must be a list of entity objects, got {type(entities).__name__}")
        elif entities and not all(isinstance(e, dict) for e in entities):
            problems.append("'entities' must be a list of entity OBJECTS — it contains non-object items")
        endpoints = arch_result.get("endpoints")
        if endpoints is not None and not isinstance(endpoints, list):
            problems.append(f"'endpoints' must be a list, got {type(endpoints).__name__}")
        return problems

    def _recover_expected_shape(self, obj: dict, required_key: str, label: str = "") -> dict:
        """If `obj` is missing `required_key` at its top level, search one
        level into its own values for a nested dict that DOES have it, and
        use that instead.

        agents.llm.chat_json()'s own _unwrap_stray_json_key() already
        recovers the one exact stray-wrapper shape confirmed in practice
        ({"json": {...}}) for every JSON-mode caller platform-wide — but
        that's deliberately scoped to the literal key "json" only, since a
        shared function can't safely guess every caller's expected shape
        (unwrapping any single-key dict there would also break a caller
        that legitimately expects one, like this file's own _coerce_files
        and its {"files": {...}} shape). A model free to name its own
        wrapper key isn't guaranteed to always pick "json" — this is the
        per-caller fallback for that: this call site KNOWS it needs
        `required_key` (e.g. "entities" for an architecture response), so it
        can safely recover from ANY wrapper name, not just one specific
        guess. Logs when it fires rather than silently masking it — frequent
        hits here would mean the tool schema itself needs tightening, not
        just working around it in perpetuity.
        """
        if not isinstance(obj, dict) or required_key in obj:
            return obj
        for key, value in obj.items():
            if isinstance(value, dict) and required_key in value:
                self._p(f"skill:{label or 'Response'} was wrapped under an unexpected "
                        f"top-level key ('{key}') — recovered by unwrapping it.")
                return value
        return obj

    def _build_context(self, keys: list[str] | None = None, max_chars: int = 15000) -> str:
        parts = []
        items = self.artifacts.items() if keys is None else (
            (k, self.artifacts[k]) for k in keys if k in self.artifacts
        )
        for key, content in items:
            truncated = content[:max_chars] if len(content) > max_chars else content
            parts.append(f"=== {key} ===\n{truncated}")
        return "\n\n".join(parts)

    def _files_summary(self, max_chars: int = 8000) -> str:
        """Summarize generated files so far for context passing."""
        parts = []
        total = 0
        for path, content in sorted(self.files.items()):
            entry = f"--- {path} ---\n{content[:2000]}"
            if total + len(entry) > max_chars:
                parts.append(f"... and {len(self.files) - len(parts)} more files")
                break
            parts.append(entry)
            total += len(entry)
        return "\n".join(parts)

    _STUB_CONTENT_TOKENS = {
        "placeholder", "todo", "tbd", "n/a", "na", "not implemented",
        "...", "stub", "// todo", "# todo",
    }

    def _coerce_files(self, files: dict, label: str = "") -> dict:
        """
        Defensive normalization of an LLM's {"files": {"path": "content"}}
        response before it's merged into self.files or written to disk.
        chat_json() is shared platform-wide code used for many different JSON
        shapes, so its tool-forced schema can't hardcode "every value here
        must be a string" — occasionally (seen in practice) the model nests
        an entire second files dict one level too deep, e.g.
        {"files": {"files": {"path": "content", ...}}}. Flatten that one
        known shape rather than crashing the whole generation at write-time
        on a str-vs-dict mismatch, and drop (with a log line, not silently)
        anything else that isn't a plain string, which would fail identically
        later anyway. Also guards against `files` itself not being a dict at
        all (seen in practice for the docs call: the model returned
        {"files": "the whole README as one string"} instead of nesting it
        under a filename) — call sites that can sensibly recover a bare
        string (e.g. docs, where it's unambiguous what a lone string would
        mean) should unwrap it into a proper {path: content} dict themselves
        BEFORE calling this, since this generic helper has no way to know
        what filename a caller-specific bare string was meant to be.

        Also unwraps a double-encoded envelope — observed directly on a
        seed-data batch: the model returned {"files": {"data.sql":
        "{\"data.sql\": \"-- Plants\\nINSERT INTO ...\"}"}}, i.e. the *value*
        for the correct path was itself a second, redundant JSON envelope
        (as a string) rather than plain file content. Passed through
        unchecked, that string still contains "INSERT" and other real-looking
        content, so a substring check like the seed-data caller's own
        _has_real_seed_data() doesn't catch it — it silently writes a JSON
        blob into the generated file instead of SQL, and seeding then fails
        with a SQLite parse error at that file's first "{" (breaking every
        table seeded from that point on, since it's all one executescript).
        """
        if not isinstance(files, dict):
            self._p(f"skill:{label} response wasn't a files object (got {type(files).__name__}) — dropped")
            return {}
        out = {}
        for path, content in files.items():
            if isinstance(content, str):
                content = self._unwrap_double_encoded_content(content, path, label)
                # Reproduced directly on a multi-entity implementation batch:
                # most files in the batch were real, but a couple came back
                # with the literal word "placeholder" as their ENTIRE file
                # content instead of real code — accepted as a normal,
                # successfully-generated file by every caller (nothing here
                # or downstream ever inspected content quality), so it was
                # written to disk as-is and silently shipped as a broken
                # route/service. Treating this the same as a dropped
                # non-string value — instead of writing it — lets each
                # caller's own completeness check (e.g. Stage 3's per-entity
                # route-file check) see it as MISSING and retry, rather than
                # as a false success. Exact-match only, not a length
                # heuristic — a genuinely short but real file (an empty
                # __init__.py, a one-line override) must never be dropped.
                if content.strip().lower() in self._STUB_CONTENT_TOKENS:
                    self._p(f"skill:{label} response returned a stub placeholder for '{path}' instead of real content — dropped")
                    continue
                out[path] = content
            elif isinstance(content, dict) and content and all(isinstance(v, str) for v in content.values()):
                self._p(f"skill:{label} response nested an extra 'files' level under '{path}' — flattened automatically")
                out.update(content)
            else:
                self._p(f"skill:{label} response had non-string content for '{path}' — dropped (type {type(content).__name__})")
        return out

    def _unwrap_double_encoded_content(self, content: str, path: str, label: str, _depth: int = 0) -> str:
        """
        If `content` is itself a JSON object (a redundant nested envelope —
        see _coerce_files' docstring), pull out the real file content: the
        value under `path` if present, the value under "files" if that's
        where the model put it, or the sole value if it's a single-key dict.
        Recurses (bounded) in case the model nested it more than once.
        Anything that isn't a JSON object, or doesn't match one of those
        shapes, is returned unchanged — this only touches the specific
        double-encoding shape observed in practice, not arbitrary strings
        that happen to start with '{' (e.g. real JSON seed content).

        Uses raw_decode (parses the first complete JSON value, ignoring
        whatever follows) rather than json.loads (which demands the ENTIRE
        string be valid JSON) — observed directly on a second, independent
        occurrence: the envelope had one stray extra '}' trailing a
        perfectly valid object (`{"...": "..."}}`), which json.loads rejects
        outright with "Extra data", silently defeating this exact guard the
        first time it was written. raw_decode parses the valid object and
        simply ignores the garbage after it.

        strict=False for the same reason every other JSON parse in this
        codebase already uses it (chat_json's own json.loads/raw_decode
        calls): a multi-line seed-data string frequently contains literal
        newline BYTES instead of a properly escaped "\\n" — strict JSON
        rejects a raw control character inside a string outright
        ("Invalid control character"), which silently defeated this guard
        a THIRD time (reproduced directly: a whole seed batch, complete
        with a trailing stray '</invoke>' tool-call-scaffold fragment,
        was written to data.sql verbatim because this one raw_decode call
        — unlike every other JSON parse here — was still strict).
        """
        stripped = content.strip()
        if _depth >= 3 or not stripped.startswith("{"):
            return content
        try:
            parsed, _end = json.JSONDecoder(strict=False).raw_decode(stripped)
        except (json.JSONDecodeError, ValueError):
            return content
        if not isinstance(parsed, dict):
            return content
        if path in parsed and isinstance(parsed[path], str):
            inner = parsed[path]
        elif "files" in parsed and isinstance(parsed["files"], dict) and path in parsed["files"] \
                and isinstance(parsed["files"][path], str):
            inner = parsed["files"][path]
        elif len(parsed) == 1 and isinstance(next(iter(parsed.values())), str):
            inner = next(iter(parsed.values()))
        else:
            return content
        self._p(f"skill:{label} response double-encoded '{path}' as a nested JSON string — unwrapped automatically")
        return self._unwrap_double_encoded_content(inner, path, label, _depth + 1)

    def _remove_orphaned_files_for(self, skipped_entities: list, language: str):
        """
        Remove any already-generated file that references one of these
        entities' model classes — called when a batch is skipped, since
        their repository interfaces (generated upfront, before any batch
        ran — see _generate_repositories) still exist and reference model
        classes that will now never be generated. A repository importing/
        extending a nonexistent model class is a guaranteed compile error,
        not a soft failure the app can start without, so it must be removed
        rather than just logged.

        Java-only for now: the match is precise (a full package-qualified
        import statement, or a generic type argument) specifically to avoid
        prefix collisions between entity names (e.g. "Sale" is a literal
        prefix of "Salesperson" — a naive substring check would wrongly
        remove Salesperson's own files too). Python doesn't have an
        equally precise, reliably-generated marker to match against yet.
        """
        if language != "java":
            return
        names = [e.get("name") for e in skipped_entities if e.get("name")]
        if not names:
            return
        to_remove = [
            path for path, content in self.files.items()
            if path.endswith(".java") and any(
                f"import com.api.model.{n};" in content or f"<{n}," in content or f"<{n}>" in content
                for n in names
            )
        ]
        for path in to_remove:
            del self.files[path]
        if to_remove:
            self._p(f"skill:Removed {len(to_remove)} file(s) referencing "
                    f"{', '.join(names)} (skipped — model never generated): {', '.join(to_remove)}")

    def _shrink_until_success(self, batch: list, run_batch, min_size: int, on_final_failure=None) -> list:
        """Delegates to AgentPlatform.core.codegen_batching (single source of
        truth, shared with WebUIGenerator's own per-entity generation) — see
        that module's docstring for the actual algorithm."""
        from AgentPlatform.core.codegen_batching import shrink_until_success
        return shrink_until_success(batch, run_batch, min_size, on_final_failure, log=self._p)

    def _run_with_adaptive_batching(self, items: list, run_batch, initial_size: int,
                                     min_size: int = 1, on_final_failure=None) -> list:
        """Delegates to AgentPlatform.core.codegen_batching — see that
        module's docstring for the actual algorithm."""
        from AgentPlatform.core.codegen_batching import run_with_adaptive_batching
        return run_with_adaptive_batching(items, run_batch, initial_size, min_size, on_final_failure, log=self._p)

    def _shared_contract_files_text(self) -> str:
        """Full, untruncated content of every bootstrap/shared file — the
        handful of files every entity call MUST reproduce byte-exact
        signatures from (shared DTOs, shared exceptions), unlike the general
        _files_summary() context, which exists only for soft style
        consistency and is allowed to truncate or drop files under budget."""
        parts = []
        for path in sorted(self._shared_contract_paths):
            if path in self.files:
                parts.append(f"--- {path} ---\n{self.files[path]}")
        return "\n\n".join(parts)

    def generate(self, user_prompt: str, api_options: dict | None = None,
                 project_name_override: str | None = None) -> dict:
        """
        Run the full API generation pipeline.

        Args:
            user_prompt: Requirements text from the user
            api_options: {language, auth_type, rate_limit, database, endpoints, include_docker, include_tests}
            project_name_override: if given, use this slug instead of whatever name the
                architect LLM picks — mirrors WebUIGenerator's generate_project()
                project_name_override, so a project you create under a specific name
                doesn't silently end up registered under a different one.

        Returns:
            {"projectName": str, "title": str, "description": str, "files": dict[str,str]}
        """
        self.api_options = api_options or {}
        language = self.api_options.get("language", "python")
        auth_type = self.api_options.get("auth_type", "jwt")
        database = self.api_options.get("database", "sqlite")
        rate_limit = self.api_options.get("rate_limit", 100)
        # Default OFF: the runner already starts generated APIs directly
        # (uvicorn / mvn spring-boot:run — see api_runner.py), the same way
        # web apps run their own dev server, so a Dockerfile/docker-compose
        # generated here goes completely unused. Docker support is coming as
        # its own deliberate opt-in (a separate Docker tab, mirroring Web UI's),
        # not as a default side effect of every generation.
        include_docker = self.api_options.get("include_docker", False)
        include_tests = self.api_options.get("include_tests", True)
        endpoints_hint = self.api_options.get("endpoints", [])

        total_stages = len(API_STAGES)

        # ── Stage 1: Architecture ──────────────────────────────────────────────
        self._p(f"crew:Stage 1/{total_stages} — Designing API architecture...")
        from .api_prompts import API_ARCHITECT_USER

        endpoint_hints_str = ""
        if endpoints_hint:
            endpoint_hints_str = "User-defined endpoints (incorporate these):\n"
            for ep in endpoints_hint:
                endpoint_hints_str += f"  {ep.get('method', 'GET')} {ep.get('path', '')} — {ep.get('description', '')}\n"

        arch_result = self._architect_agent.generate(
            API_ARCHITECT_USER.format(
                requirements=user_prompt,
                endpoint_hints=endpoint_hints_str,
                language=language,
                database=database,
            ),
            max_tokens=16000,
            json_mode=True,
        )
        arch_result = self._recover_expected_shape(arch_result, "entities", label="Architecture")
        shape_problems = self._architecture_shape_problems(arch_result)
        if shape_problems:
            self._p(f"skill:Architecture response was malformed ({'; '.join(shape_problems)}) — "
                    f"retrying with a stricter instruction...")
            retry_prompt = (
                API_ARCHITECT_USER.format(
                    requirements=user_prompt,
                    endpoint_hints=endpoint_hints_str,
                    language=language,
                    database=database,
                )
                + "\n\nIMPORTANT: 'entities' MUST be a JSON array of entity objects (each with its own "
                  "name/table/fields), never a single string or free-text description. The same applies "
                  "to 'endpoints'. Structure the ENTIRE architecture as proper nested objects and arrays — "
                  "do not summarize any part of it as plain text, no matter how many entities there are."
            )
            arch_result = self._architect_agent.generate(retry_prompt, max_tokens=16000, json_mode=True)
            arch_result = self._recover_expected_shape(arch_result, "entities", label="Architecture (retry)")
            shape_problems = self._architecture_shape_problems(arch_result)
            if shape_problems:
                raise RuntimeError(
                    f"API architecture response was malformed even after a retry: "
                    f"{'; '.join(shape_problems)}. This usually means the request is too complex for "
                    f"one JSON response — try fewer entities/pages, or split the request."
                )
        architecture_json = json.dumps(arch_result, indent=2)
        self.artifacts["architecture"] = architecture_json
        if project_name_override:
            import re as _re
            project_name = _re.sub(r"[^a-z0-9-]", "-", project_name_override.lower()).strip("-") or "api-project"
        else:
            project_name = arch_result.get("projectName", "api-project")
        title = arch_result.get("title", project_name)
        description = arch_result.get("description", "")
        self._p(f"skill:Architecture designed — {len(arch_result.get('entities', []))} entities, {len(arch_result.get('endpoints', []))} endpoints")

        from api_config import WEB_API_DIR
        self.project_dir = WEB_API_DIR / project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # ── Stage 2a: Schema & Models (adaptively batched) ──────────────────────
        # Split from seed-data generation (2b below) for the same reason Stage
        # 3 was split into bootstrap + entity batches: one call asked to
        # produce a full schema, 12 JPA entity classes, AND substantial seed
        # data was simply too much for one completion — observed directly, as
        # the schema coming back fine but data.sql never appearing at all,
        # even after a full re-roll retry. Batched here too, same reasoning
        # and same adaptive-shrink mechanism as seed data and Stage 3: no
        # fixed size is guaranteed right for every project's entity count.
        self._p(f"crew:Stage 2/{total_stages} — Designing data models...")
        seed_path = "src/main/resources/data.sql" if language == "java" else "seed_data.sql"
        schema_path = "src/main/resources/schema.sql" if language == "java" else "schema.sql"
        data_entities = arch_result.get("entities", [])
        data_fk_by_entity = {e.get("name"): self._entity_fk_map(e) for e in data_entities}
        data_order = self._topo_order_entities(data_entities, data_fk_by_entity)

        schema_acc = [""]  # mutable box — accumulates schema.sql across batches, same pattern as seed data's acc

        def _run_data_batch(batch: list):
            batch_names = [e.get("name") for e in batch]
            label = ", ".join(batch_names)
            self._p(f"crew:Stage 2/{total_stages} — Designing data models for {label}...")
            for attempt in range(2):
                data_prompt = self._build_data_batch_prompt(arch_result, batch, language, database, schema_acc[0])
                data_result = self._data_architect_agent.generate(data_prompt, max_tokens=8000, json_mode=True)
                batch_files = self._coerce_files(data_result.get("files", {}), f"Data modeling ({label})")
                # schema.sql is one shared file, not one per entity — pull this
                # batch's fragment out before the generic merge below (which
                # would otherwise overwrite, not append) and accumulate it
                # separately, same as seed data's data.sql.
                new_schema = batch_files.pop(schema_path, batch_files.pop("schema.sql", "")) if batch_files else ""
                # Non-empty isn't the same as complete — reproduced directly:
                # a 3-entity batch returned real content (schema.sql + one
                # model file) and was accepted as a full success under the old
                # "if batch_files:" check, silently missing model files for
                # the other two entities entirely. Everything downstream
                # (repositories/services/routes) still assumed those entities
                # existed, so the actual failure only surfaced many stages
                # later as an unrelated-looking ImportError, with nothing in
                # this file for the repair loop to have ever created from
                # scratch. Checking every entity's own expected model file is
                # present is what the seed-data batch's _has_real_seed_data
                # already does for its own file — this is the same idea, one
                # level earlier in the pipeline where it's far cheaper to
                # catch.
                missing = [name for name in batch_names
                           if self._expected_model_path(name, language) not in batch_files]
                if batch_files and not missing:
                    if language == "python":
                        self._fix_python_typing_mapped_import(batch_files)
                    self.files.update(batch_files)
                    if new_schema:
                        schema_acc[0] = (schema_acc[0] + "\n\n" + new_schema).strip()
                        self.files[schema_path] = schema_acc[0]
                    self._p(f"skill:{label} data model generated — {len(batch_files) + (1 if new_schema else 0)} files")
                    self._flush_to_disk()
                    return batch_files
                if attempt == 0:
                    reason = "returned no files" if not batch_files else f"was missing a model file for {', '.join(missing)}"
                    self._p(f"skill:Data modeling for {label} {reason}, retrying once...")
            return None

        def _on_data_final_failure(batch: list):
            names = ", ".join(e.get("name") for e in batch)
            self._p(f"skill:WARNING — data model for {names} is still missing even at the smallest "
                     f"batch size; everything downstream for {names} will likely be broken")

        self._run_with_adaptive_batching(
            data_order, _run_data_batch, self._ENTITY_BATCH_SIZE, on_final_failure=_on_data_final_failure,
        )
        if language == "python":
            self._wire_python_models_init()

        schema_sql = schema_acc[0]
        # Correct schema.sql's column types against the entity classes that
        # actually got generated, BEFORE Stage 2b (seed data) reads
        # schema_sql as its ground truth — see
        # _reconcile_schema_types_with_entities's docstring for the exact
        # failure this closes.
        schema_sql, type_fixes = self._reconcile_schema_types_with_entities(schema_sql, data_entities, language)
        if type_fixes:
            self.files[schema_path] = schema_sql
            for fix in type_fixes:
                self._p(f"skill:{fix}")
        self.artifacts["schema"] = schema_sql
        if not schema_sql:
            self._p("skill:WARNING — no schema.sql was generated at all; continuing, but the "
                     "database schema is entirely missing")
        self._p(f"skill:Data models generated — {len(schema_sql)} schema chars")

        # ── Stage 2b: Seed Data (adaptively batched) ────────────────────────────
        # One call for ALL seed data was still too much for a project this
        # size — observed directly: this project's own requirements need
        # ~78 rows across 12 tables, and a single seed-data completion kept
        # coming back empty even after a full retry, the same failure mode
        # that motivated splitting Stage 2 in the first place. Rather than
        # pick another fixed batch size and risk hitting the identical wall on
        # some future, larger project, this starts at _ENTITY_BATCH_SIZE and
        # adaptively shrinks (see _run_with_adaptive_batching) only the
        # specific batches that actually fail — self-correcting regardless of
        # entity count or how much seed data any given project asks for.
        self._p(f"crew:Stage 2/{total_stages} — Generating seed data...")
        seed_system = self._seed_data_system(language)
        seed_entities = arch_result.get("entities", [])
        seed_fk_by_entity = {e.get("name"): self._entity_fk_map(e) for e in seed_entities}
        seed_order = self._topo_order_entities(seed_entities, seed_fk_by_entity)

        # A double-quoted "key": "value" shape essentially never occurs in
        # legitimate seed SQL — every string literal in this codebase's SQL
        # convention is single-quoted ('like this'), never double-quoted.
        # Reproduced directly: a batch's own response glitched mid-generation
        # and emitted a stray, incomplete re-opening of its own JSON envelope
        # ("7,'test'\n], \"src/main/resources/data.sql\":\"\"}") instead of
        # continuing the real INSERT statement — `"insert" in sql.lower()`
        # alone still saw the many real INSERT statements earlier in the same
        # string and accepted the whole thing, permanently merging that
        # garbage tail into the accumulated seed file (breaking the SQLite
        # executescript at that exact "{" on every later run).
        _STRAY_JSON_KV = re.compile(r'"[^"\n]{1,200}"\s*:\s*"')

        def _has_real_seed_data(sql: str) -> bool:
            """
            Checks for real INSERT content AND that the SQL actually
            terminates — reproduced directly: a batch ran out of tokens
            mid-way through its second table's row list (`...'VIP'),`, no
            closing `)` for the statement, no trailing `;`), which still
            has "insert" in it and no stray-JSON artifact, so the old check
            accepted it as complete. It only failed much later, at real
            SQLite executescript time ("incomplete input"), by which point
            this had already been merged into acc[0] and there was no
            retry left — the whole seed file failed and the automatic
            repair pass (working from the same already-broken text) had
            nothing salvageable to fix. Catching it here instead re-enters
            the SAME retry-once / adaptive-batch-shrink path every other
            seed failure already goes through, while the batch can still
            be regenerated cleanly.
            """
            stripped = sql.rstrip()
            return (
                "insert" in stripped.lower()
                and not _STRAY_JSON_KV.search(stripped)
                and stripped.endswith(";")
            )

        def _fix_trailing_terminator(sql: str) -> str:
            """A batch's generated SQL occasionally ends with a stray
            bracket (']' or '}') right after the last row's closing ')'
            instead of the real ';' statement terminator — reproduced
            directly on a chat_messages batch: ...'2025-06-05 11:02:23')]
            with no semicolon anywhere in the whole 24-row statement (the
            earlier double-encoded-JSON-object case this pipeline already
            defends against is the '{'-shaped version of the same class of
            artifact; this is the ']'-shaped one). Left in place, SQLite
            rejects the entire script with "unrecognized token" at that
            exact character, breaking every table seeded after it — it's
            all one executescript. Everything up to the stray bracket is a
            real, complete row, not a truncation, so replacing it with the
            terminator it should have been is safe; a properly terminated
            response is untouched since the regex only matches when ';' is
            absent from that trailing run of brackets."""
            stripped = sql.rstrip()
            m = re.search(r"\)[\]\}]+$", stripped)
            if not m:
                return sql
            return stripped[:m.start() + 1] + ";\n"

        acc = [""]  # mutable box — _run_seed_batch both reads and extends this as each (sub-)batch succeeds

        def _run_seed_batch(batch: list):
            batch_names = [e.get("name") for e in batch]
            label = ", ".join(batch_names)
            self._p(f"crew:Stage 2/{total_stages} — Generating seed data for {label}...")
            # Scales with batch size, same reasoning as the entity-implementation
            # batches' own max_tok formula — a flat 8000 was reproduced directly
            # as too small for a single, heavily-constrained table (60 rows x ~10
            # columns, each value validated against an enum/regex, per the app's
            # own requirements) even at the smallest possible batch size (this
            # one entity alone): the completion cuts off mid-JSON before the
            # closing brace, so the whole response fails to parse and comes back
            # as "no INSERT statements" even though the model likely wrote dozens
            # of complete rows before running out of room.
            max_tok = min(8000 * len(batch) + 8000, 32000)
            for attempt in range(2):
                seed_prompt = self._build_seed_data_batch_prompt(
                    user_prompt, arch_result, batch, language, database, schema_sql, acc[0],
                )
                seed_result = self._call_llm(seed_system, seed_prompt, max_tokens=max_tok)
                seed_raw = seed_result.get("files", {})
                if isinstance(seed_raw, str):
                    # Observed directly (Customer-only batch): the model sometimes
                    # returns the whole INSERT-statements block as one bare string
                    # under "files" instead of nesting it under a filename. Same
                    # recovery as the docs call site — unambiguous here since this
                    # call always writes to exactly one known path.
                    seed_raw = {seed_path: seed_raw}
                seed_files_batch = self._coerce_files(seed_raw, f"Seed data ({label})")
                sql = seed_files_batch.get(seed_path, "")
                fixed_sql = _fix_trailing_terminator(sql)
                if fixed_sql != sql:
                    self._p(f"skill:Seed data for {label} ended with a stray bracket instead of ';' — fixed automatically")
                    sql = fixed_sql
                if _has_real_seed_data(sql):
                    acc[0] = (acc[0] + "\n\n" + sql).strip()
                    return sql
                if attempt == 0:
                    if "insert" not in sql.lower():
                        reason = "had no INSERT statements"
                    elif _STRAY_JSON_KV.search(sql):
                        reason = "contained a stray JSON artifact mid-response"
                    else:
                        reason = "ran out of room mid-statement (no closing ';')"
                    self._p(f"skill:Seed data for {label} {reason}, retrying once...")
            return None

        failed_seed_entities: list[str] = []
        self._run_with_adaptive_batching(
            seed_order, _run_seed_batch, self._ENTITY_BATCH_SIZE,
            on_final_failure=lambda batch: failed_seed_entities.extend(e.get("name") for e in batch),
        )
        if failed_seed_entities:
            self._p(f"skill:WARNING — seed data for {', '.join(failed_seed_entities)} is still missing "
                     f"even at the smallest batch size; those tables will start empty")
        if _has_real_seed_data(acc[0]):
            self.files[seed_path] = acc[0]
        self._p(f"skill:Seed data generated — {len(acc[0])} chars"
                + (" (some tables missing)" if failed_seed_entities else ""))

        # `arch_result["entities"]` is the same list object referenced by
        # data_entities/seed_entities above — mutating it here (dropping any
        # has_one relationship the real seed data just proved isn't actually
        # 1:1) is what Stage 3 below sees too, since it re-reads
        # arch_result.get("entities", ...) and architecture_json fresh. The
        # already-written entity model file (Java) needs its own retroactive
        # cleanup too — see _fix_invalid_one_to_one_relationships's own
        # docstring for why the JSON mutation alone isn't enough.
        one_to_one_fixes = self._fix_invalid_one_to_one_relationships(
            arch_result.get("entities", []), self.files.get(seed_path, ""), language
        )
        if one_to_one_fixes:
            for fix in one_to_one_fixes:
                self._p(f"skill:{fix}")
            architecture_json = json.dumps(arch_result, indent=2)
            self.artifacts["architecture"] = architecture_json

        self._flush_to_disk()

        # ── Stage 3: Implementation ───────────────────────────────────────────
        # A bootstrap call (entry point, DB setup, shared schemas, dependency
        # manifest) followed by one call per entity, instead of a single
        # monolithic call — see api_prompts.py's comment above
        # SERVICES_ENGINEER_API_BOOTSTRAP_USER for why (real progress visibility
        # + no single call sized to the whole app's worth of files).
        from .api_prompts import (
            SERVICES_ENGINEER_API_BOOTSTRAP_USER,
            SERVICES_ENGINEER_API_BATCH_USER,
        )

        entities = arch_result.get("entities", [])
        all_endpoints = arch_result.get("endpoints", [])
        rate_limiting_str = f"{rate_limit} rpm" if rate_limit else "none"

        self._p(f"crew:Stage 3/{total_stages} — Implementing app bootstrap (entry point, DB, shared schemas)...")
        bootstrap_prompt = SERVICES_ENGINEER_API_BOOTSTRAP_USER.format(
            architecture_json=architecture_json,
            language=language,
            auth_type=auth_type,
            rate_limiting=rate_limiting_str,
            database=database,
        )
        # Same reasoning as Stage 2's retry-on-empty: no entry point, DB
        # config, or shared exceptions means every one of the batches below
        # is building on nothing, and nothing downstream would notice.
        bootstrap_files: dict = {}
        for attempt in range(2):
            bootstrap_result = self._services_agent.generate(bootstrap_prompt, max_tokens=12000, json_mode=True)
            bootstrap_files = self._coerce_files(bootstrap_result.get("files", {}), "Bootstrap")
            if bootstrap_files:
                break
            if attempt == 0:
                self._p("skill:Bootstrap returned no files, retrying once...")
        if not bootstrap_files:
            self._p("skill:WARNING — Bootstrap returned no files after retry; "
                     "continuing, but the entry point/DB setup/shared exceptions may be entirely missing")
        self.files.update(bootstrap_files)
        if language == "python":
            self._ensure_python_database_py(database)
        self._ensure_shared_exceptions(language)
        # Snapshot AFTER _ensure_shared_exceptions, not just bootstrap_files —
        # no entity-specific file exists yet at this point, so every path in
        # self.files right now is, by construction, a shared/foundational file
        # every entity call needs to see in full.
        self._shared_contract_paths = set(self.files.keys())
        self._p(f"skill:Bootstrap generated — {len(bootstrap_files)} files (entry point, DB setup, shared schemas)")
        self._flush_to_disk()

        # ── Repository interfaces — ALL entities, before any entity/batch
        # implementation begins (batched, adaptively). Not per-entity like
        # model/schema/service/controller: repository method signatures are a
        # hard compile-time contract, and several of this project's own
        # endpoints require one entity to query ANOTHER entity directly (e.g.
        # Customer's own endpoint needing to look up ServiceAppointments by a
        # list of Vehicle ids it doesn't even have a foreign key to).
        # Accumulating repositories progressively as each entity/service batch
        # finished (an earlier approach) left an ordering-dependent blind
        # spot: an entity processed EARLIER in topological order had
        # literally no way to see a LATER entity's repository, no matter how
        # much other context was shared — observed directly: CustomerService
        # called serviceAppointmentRepository.findByVehicleIdIn(...), a
        # method ServiceAppointmentRepository never declared, because
        # Customer's batch ran before ServiceAppointment's ever existed.
        # Generating every repository before any entity/service batch starts
        # removes that blind spot entirely. Batching THIS generation too
        # (rather than one call for all entities) doesn't reintroduce that
        # same risk: unlike service/controller code, one entity's repository
        # never needs to read another repository's file content — only the
        # full endpoint list (unfiltered, given to every batch regardless of
        # which entities it covers) and the schema, both already
        # entity-count-independent.
        self._p(f"crew:Stage 3/{total_stages} — Generating repository interfaces...")
        repo_system = self._repository_system(language)
        repo_fk_by_entity = {e.get("name"): self._entity_fk_map(e) for e in entities}
        repo_order = self._topo_order_entities(entities, repo_fk_by_entity)

        repo_paths: list[str] = []

        def _run_repo_batch(batch: list):
            batch_names = [e.get("name") for e in batch]
            label = ", ".join(batch_names)
            self._p(f"crew:Stage 3/{total_stages} — Generating repository interfaces for {label}...")
            for attempt in range(2):
                repo_prompt = self._build_repository_batch_prompt(
                    user_prompt, arch_result, batch, schema_sql, language, database,
                )
                repo_result = self._call_llm(repo_system, repo_prompt, max_tokens=8000)
                batch_files = self._coerce_files(repo_result.get("files", {}), f"Repositories ({label})")
                if batch_files:
                    self.files.update(batch_files)
                    self._shared_contract_paths |= set(batch_files.keys())
                    repo_paths.extend(batch_files.keys())
                    self._p(f"skill:{label} repository interfaces generated — {len(batch_files)} files")
                    self._flush_to_disk()
                    return batch_files
                if attempt == 0:
                    self._p(f"skill:Repository interfaces for {label} returned no files, retrying once...")
            return None

        def _on_repo_final_failure(batch: list):
            names = ", ".join(e.get("name") for e in batch)
            self._p(f"skill:WARNING — repository interface for {names} is still missing even at the "
                     f"smallest batch size; entity implementation for {names} will likely fail to compile")

        self._run_with_adaptive_batching(
            repo_order, _run_repo_batch, self._ENTITY_BATCH_SIZE, on_final_failure=_on_repo_final_failure,
        )

        # Reuse repo_order — same entities, same FK-dependency ordering already
        # computed above; no need to derive it a second time for Stage 3's
        # own entity/service batches.
        ordered_entities = repo_order
        impl_paths = list(bootstrap_files.keys()) + repo_paths
        implemented_entity_names: set = set()

        # Batched, not one call per entity — one-per-entity gave the best
        # possible progress granularity, but every independent call is a
        # chance for it to disagree with something an earlier call already
        # defined (a bean-name collision, a duplicate route, a guessed DTO
        # constructor signature, a guessed cross-entity repository method —
        # all hit in practice). Batching a few entities per call cuts the
        # number of independent calls (and thus disagreement opportunities),
        # while still reporting real incremental progress every batch rather
        # than one shot for the whole implementation stage. Starts at
        # _ENTITY_BATCH_SIZE and adaptively shrinks (see
        # _run_with_adaptive_batching) only the specific batches that
        # actually fail — no fixed size is guaranteed right for every
        # project's entity count or per-entity complexity.
        def _run_entity_batch(batch: list):
            batch_names = [e.get("name") or f"Entity{j}" for j, e in enumerate(batch, 1)]
            label = ", ".join(batch_names)
            self._p(f"crew:Stage 3/{total_stages} — Implementing {label}...")

            batch_endpoints = []
            for e in batch:
                batch_endpoints.extend(self._endpoints_for_entity(all_endpoints, e))

            batch_prompt = SERVICES_ENGINEER_API_BATCH_USER.format(
                architecture_json=architecture_json,
                entities_json=json.dumps(batch, indent=2),
                batch_endpoints_json=json.dumps(batch_endpoints, indent=2),
                shared_contract_files=self._shared_contract_files_text(),
                existing_files_summary=self._files_summary(),
                language=language,
                auth_type=auth_type,
                rate_limiting=rate_limiting_str,
                database=database,
            )
            # Scales with batch size since a batch's completion is
            # proportionally larger than a single entity's; capped well
            # under typical provider ceilings. Widened from 12000*n+4000:
            # reproduced directly on a real generation, the one entity with
            # the most fields/relationships (13 columns, referenced by
            # several other entities) kept coming back with its route file
            # silently missing -- even alone, at the smallest possible
            # batch size and after the one built-in retry -- because model
            # + 3 schemas + repository + service + route for that one
            # entity didn't fit in the old budget. Same fix as the
            # seed-data batch's identical token-budget gap.
            max_tok = min(16000 * len(batch) + 8000, 64000)

            last_err: Exception | None = None
            for attempt in range(2):
                try:
                    batch_result = self._services_agent.generate(batch_prompt, max_tokens=max_tok, json_mode=True)
                    batch_files = self._coerce_files(batch_result.get("files", {}), label)
                    # Non-empty isn't complete — reproduced directly: a
                    # 3-entity batch came back with real content for two
                    # entities but no route/controller file at all for the
                    # third (silently absent, not even a stub), and was
                    # still accepted as a full success under the old
                    # "if batch_files:" check. Nothing wires a router that
                    # was never generated, so that entity's endpoints just
                    # never existed — invisible in Swagger, no error
                    # anywhere, since there's no request to fail. Same
                    # per-entity presence check as Stage 2's own model-batch
                    # fix, one stage later where it's equally cheap to catch.
                    missing = [
                        name for name in batch_names
                        if self._expected_route_path(name, language) not in batch_files
                        and self._expected_route_path(name, language) not in self.files
                    ]
                    if batch_files and not missing:
                        if language == "python":
                            self._fix_python_low_limit_ceiling(batch_files)
                            self._fix_python_zero_indexed_page_param(batch_files)
                        else:
                            self._fix_java_low_limit_ceiling(batch_files)
                        # Applied immediately, not deferred to after every
                        # batch finishes — a later (sub-)batch's own prompt
                        # (built above, at ITS call time) must see this
                        # batch's files in self.files/_shared_contract_paths,
                        # the same as when this loop was a plain sequential
                        # for-loop. Deferring this would silently reintroduce
                        # the exact "later entity can't see earlier one's
                        # output" blind spot the repository-upfront fix and
                        # _shared_contract_paths accumulation both exist to
                        # close.
                        self.files.update(batch_files)
                        impl_paths.extend(batch_files.keys())
                        implemented_entity_names.update(batch_names)
                        self._shared_contract_paths |= {
                            p for p in batch_files if "/repository/" in p or "/repositories/" in p
                        }
                        if language == "python":
                            self._wire_python_router(batch_files)
                        self._p(f"skill:{label} implemented — {len(batch_files)} files")
                        self._flush_to_disk()
                        return batch_files
                    if missing:
                        last_err = RuntimeError(f"missing route/controller file for {', '.join(missing)}")
                except Exception as e:
                    last_err = e
                if attempt == 0:
                    self._p(f"skill:{label} implementation hit an issue, retrying once: {last_err or 'no files returned'}")
            self._p(f"skill:{label} implementation failed after retry — {last_err or 'no files returned'}")
            return None

        def _on_batch_final_failure(batch: list):
            # Repositories for this batch's entities were already generated
            # upfront (see _generate_repositories) — since the model classes
            # that would have backed them just failed to generate, those
            # repositories (and anything else already referencing these
            # entities) are now dangling references to classes that will
            # never exist, which is a guaranteed compile error, not a soft
            # failure. Must remove them here, not just skip and move on.
            self._remove_orphaned_files_for(batch, language)

        self._run_with_adaptive_batching(
            ordered_entities, _run_entity_batch, self._ENTITY_BATCH_SIZE,
            on_final_failure=_on_batch_final_failure,
        )

        self._run_custom_endpoint_batch(
            ordered_entities, all_endpoints, architecture_json, language,
            auth_type, rate_limiting_str, database, impl_paths, total_stages,
        )

        # Reproduced directly: every entity's implementation batch failed
        # permanently (down to the smallest batch size, both retries
        # exhausted) for an entire real generation, leaving a "backend" with
        # zero models/repositories/services/controllers — just the
        # unconditional scaffolding (security filters, exception handlers,
        # the deterministic metadata endpoint) added in later stages
        # regardless of whether Stage 3 produced anything. Nothing raised,
        # so the caller (WebUIGenerator's _run_backend_generation) treated
        # this as a normal success: it wrote the empty backend to disk,
        # bundled the frontend against it, and the has_api/has_api_files
        # detection elsewhere then mistook the unrelated DataChat sidecar's
        # app_server.py for the real API and started THAT on the main API
        # port instead — a working-looking process serving none of the
        # app's own endpoints. Fail loudly here instead of shipping an app
        # that looks generated but has no real backend at all.
        if ordered_entities and not implemented_entity_names:
            raise RuntimeError(
                f"Backend implementation failed for every entity "
                f"({', '.join(e.get('name', '?') for e in ordered_entities)}) — "
                f"0 of {len(ordered_entities)} entities produced usable model/"
                f"repository/service/controller files, even after retries at "
                f"the smallest batch size. Not continuing with an empty backend."
            )

        self.artifacts["implementation_summary"] = "\n".join(sorted(impl_paths))
        self._p(f"skill:Implementation generated — {len(ordered_entities)} entities, {len(impl_paths)} files")

        if language == "python":
            self._normalize_python_layout()
            self._ensure_dotenv_loaded_early()
        elif language == "java":
            # Runs before every other pom.xml fixup below, since an
            # invalid pom.xml means Maven can't even read the project at
            # all — nothing downstream that touches this file matters
            # until it's valid XML first.
            self._fix_pom_xml_unescaped_entities()
            # Swagger UI (the platform's built-in API testing harness) needs
            # springdoc-openapi regardless of auth_type — unlike sqlite-jdbc/
            # spring-security (only needed by the deterministic security stage
            # below), this applies to every Java API.
            self._ensure_java_docs_dep()
            self._remove_conflicting_java_security_classes()
            self._fix_java_sqlite_timestamp_format()
            self._fix_java_bare_date_literals()
            self._fix_java_jpa_relationship_json_cycles()
            self._ensure_java_property_reference_exception_handled()
            # Must run AFTER Stage 3, not right after Stage 2 where this used
            # to live: application.properties is frequently written (or fully
            # rewritten) by THIS stage's own output, not the data-modeling
            # stage — self.files.update(impl_files) above silently overwrote
            # whatever seed-config lines were added right after Stage 2,
            # since dict.update() on a matching key replaces it wholesale.
            # Checking only after every stage that can touch this file has
            # actually run is what makes this reliable regardless of which
            # stage the LLM happens to write it from.
            self._ensure_java_seed_data_disabled_in_spring()
            self._ensure_java_sqlite_foreign_keys_enabled()
            self._ensure_java_open_session_in_view()
            self._ensure_java_hibernate_sqlite_dialect_dep()
            self._ensure_java_ddl_auto_update()
            self._ensure_java_pagination_property()
        self._flush_to_disk()

        # ── Stage 4: Security ─────────────────────────────────────────────────
        # For none/basic auth, security is deterministic code (rate limit, usage
        # metering, basic auth), not an LLM freeform call — see
        # _generate_security_middleware's docstring for why. api_key/jwt still go
        # through the LLM security stage (not rebuilt deterministically yet).
        if auth_type in ("none", "basic"):
            self._p(f"crew:Stage 4/{total_stages} — Adding deterministic security middleware...")
            sec_files = self._generate_security_middleware(language, auth_type, rate_limit)
            self.files.update(sec_files)
            if language == "python" and "src/main.py" in self.files:
                self.files["src/main.py"] += (
                    "\n\n# --- Security & observability (auto-generated, do not remove) ---\n"
                    "from src.security_bootstrap import install_security\n"
                    "install_security(app)\n"
                )
            if language == "java":
                self._ensure_java_security_deps(auth_type)
            self._p(f"skill:Security added — {auth_type} auth + rate limiting ({rate_limit} rpm) + usage metering (deterministic)")
        else:
            self._p(f"crew:Stage 4/{total_stages} — Adding security middleware (LLM)...")
            from .api_prompts import SECURITY_ENGINEER_USER

            sec_result = self._security_agent.generate(
                SECURITY_ENGINEER_USER.format(
                    architecture_json=architecture_json,
                    language=language,
                    auth_type=auth_type,
                    rate_limit_rpm=rate_limit,
                    existing_files_summary=self._files_summary(),
                ),
                max_tokens=32000,
                json_mode=True,
            )
            sec_files = self._coerce_files(sec_result.get("files", {}), "Security")
            self.files.update(sec_files)
            self._p(f"skill:Security added — {auth_type} auth + rate limiting ({rate_limit} rpm)")

        if language == "python":
            self._ensure_python_deps(database)
        self._flush_to_disk()

        # ── Stage 5: Testing & Docs ───────────────────────────────────────────
        # Tests are generated deterministically now, not by an LLM: the
        # architecture document already fully describes entities (fields,
        # types, relationships) and endpoints, so there's no judgment call
        # left to make for standard CRUD/auth/404/rate-limit coverage, and no
        # need to invent example data — sample values are synthesized from
        # each field's declared type, and fixtures are created for real via
        # the API itself (in FK dependency order) instead of guessed IDs. This
        # also sidesteps the failure mode that motivated the change: one
        # combined "tests + OpenAPI + README" completion routinely exceeded
        # 100k chars and got truncated with no way to repair itself. Docs
        # (README) still go through a small, separate LLM call — wrapped so a
        # failure in either can't sink the whole generation, since the API
        # itself is already fully built and working by this stage.
        if include_tests:
            self._p(f"crew:Stage 5/{total_stages} — Generating tests...")
            try:
                test_files = self._generate_tests(arch_result, language, auth_type, rate_limit)
                self.files.update(test_files)
                self._p(f"skill:Tests generated (deterministic) — {len(test_files)} files")
                if language == "java":
                    self._ensure_java_test_deps()
                else:
                    self._ensure_python_test_deps()
            except Exception as e:
                self._p(f"skill:Test generation failed, continuing without tests: {e}")

            self._p(f"crew:Stage 5/{total_stages} — Generating documentation...")
            from .api_prompts import DOCS_WRITER_SYSTEM, DOCS_WRITER_USER

            try:
                docs_result = self._call_llm(
                    DOCS_WRITER_SYSTEM,
                    DOCS_WRITER_USER.format(
                        architecture_json=architecture_json,
                        language=language,
                        auth_type=auth_type,
                    ),
                    max_tokens=8000,
                )
                docs_raw = docs_result.get("files", {})
                if isinstance(docs_raw, str):
                    # Observed directly: the model sometimes returns the whole
                    # README as one bare string under "files" instead of
                    # nesting it under a filename — unambiguous what it meant
                    # here (unlike the generic case _coerce_files guards
                    # against), so recover it rather than just dropping it.
                    docs_raw = {"README.md": docs_raw}
                docs_files = self._coerce_files(docs_raw, "Documentation")
                self.files.update(docs_files)
                self._p(f"skill:Documentation generated — {len(docs_files)} files")
            except Exception as e:
                self._p(f"skill:Documentation generation failed, continuing without it: {e}")
        else:
            self._p(f"crew:Stage 5/{total_stages} — Skipping tests (include_tests=false)")
        self._flush_to_disk()

        # ── Stage 6: Packaging ────────────────────────────────────────────────
        if include_docker:
            self._p(f"crew:Stage 6/{total_stages} — Generating deployment artifacts...")
            packaging_files = self._generate_packaging(arch_result, language, database)
            self.files.update(packaging_files)
            self._p(f"skill:Packaging generated — Dockerfile + docker-compose + health checks")
        else:
            self._p(f"crew:Stage 6/{total_stages} — Skipping packaging (include_docker=false)")

        # .env.example (placeholder) + a real .env (real generated credentials) so
        # the dev server we're about to start is immediately usable.
        self.files[".env.example"] = self._generate_env_example(language, auth_type, database, rate_limit)
        self.files[".env"] = self._generate_env_example(language, auth_type, database, rate_limit, real=True)

        # Final safety net, not a duplicate of the call earlier in Stage 3:
        # observed directly — a project's bootstrap call spontaneously wrote
        # its own com.api.config.SecurityConfig (a bean-name collision with
        # the deterministic com.api.security.SecurityConfig) and it survived
        # all the way to a runtime ConflictingBeanDefinitionException despite
        # the Stage-3 removal call. Whatever the exact reason it slipped
        # through there — this scan is idempotent and cheap, so running it
        # once more over the fully-final file set, right before generation
        # completes, closes the gap regardless of which stage introduced it.
        if language == "java":
            self._remove_conflicting_java_security_classes()
        self._flush_to_disk()

        if language == "java":
            self._verify_and_repair_java()
            self._ensure_java_entity_scan_covers_all_entities()
            self._flush_to_disk()
        elif language == "python":
            self._verify_and_repair_python()
            # _wire_python_models_init() (called once, right after Stage 2)
            # is the ONLY thing that makes `import src.models` in
            # database.py actually register every model on Base.metadata —
            # without it, create_all() silently creates zero tables, no
            # error anywhere, until the first real request hits "no such
            # table". Stage 3 (repositories/implementation) and the
            # boot-repair loop just above both run LLM calls that can touch
            # src/models/*.py afterward (the boot-repair widens its own
            # touched-files set to every model file whenever any one of them
            # is implicated) with no re-check that __init__.py still
            # reflects the real, final set of model files. Reproduced
            # directly: a real generation's boot-check hit "no such table"
            # and its own repair pass gave up ("no usable fix"), and the
            # shipped app's src/models/ directory had no __init__.py at
            # all. Cheap and idempotent — rebuild it fresh from whatever
            # model files actually exist in self.files right now, as the
            # last word before this returns, regardless of what any
            # upstream stage did to it.
            self._wire_python_models_init()
            self._flush_to_disk()

        return {
            "projectName": project_name,
            "title": title,
            "description": description,
            "files": self.files,
            "architecture": arch_result,
        }

    def refine(self, project_dir: Path, existing_architecture: dict, refine_prompt: str,
               api_options: dict) -> dict:
        """
        Update an existing generated API — additive only (new entities, new
        fields, new endpoints, new relationships between entities). Renaming
        or removing an existing field/table is explicitly out of scope: those
        are destructive against a database that may already hold real seeded
        data, and would need a real migration/backfill story this doesn't
        attempt.

        Mirrors the Web UI generator's own refine pattern (uigen_agent's
        generate_project + orchestrator.py's per-stage is_refinement checks):
        read what already exists, merge the requested change into the
        architecture while preserving everything untouched verbatim, then
        only regenerate the specific entities that are new or actually
        affected — everything else in self.files is carried over from disk
        unchanged, no LLM call at all. Same "keep vs. regenerate" split that
        pipeline applies per-page, applied here per-entity instead.
        """
        from .api_prompts import (
            API_ARCHITECT_REFINE_USER,
            SERVICES_ENGINEER_API_BATCH_USER,
            SERVICES_ENGINEER_API_REFINE_BATCH_USER,
            REPOSITORY_REFINE_BATCH_USER,
        )

        self.api_options = api_options
        language = api_options.get("language", "python")
        auth_type = api_options.get("auth_type", "none")
        rate_limit = api_options.get("rate_limit", 100)
        database = api_options.get("database", "sqlite")
        rate_limiting_str = f"{rate_limit} rpm" if rate_limit else "none"
        self.project_dir = project_dir
        self.artifacts = {}

        self._p("crew:Refine 1/4 — Loading existing project...")
        self.files = self._load_existing_files(project_dir)
        schema_path = "src/main/resources/schema.sql" if language == "java" else "schema.sql"
        # Everything already on disk counts as "shared contract" context for
        # every batch below — refine calls must never guess at an EXISTING
        # signature any more than a fresh generation's entity calls may guess
        # at another entity's repository.
        self._shared_contract_paths = set(self.files.keys())
        old_entities = {e.get("name"): e for e in existing_architecture.get("entities", []) if e.get("name")}
        old_endpoints = existing_architecture.get("endpoints", [])

        self._p("crew:Refine 2/4 — Merging architecture...")
        merge_prompt = API_ARCHITECT_REFINE_USER.format(
            existing_architecture_json=json.dumps(existing_architecture, indent=2),
            refine_prompt=refine_prompt,
            language=language,
            database=database,
        )
        new_architecture = self._architect_agent.generate(merge_prompt, stage="refine", max_tokens=16000, json_mode=True)
        new_architecture = self._recover_expected_shape(new_architecture, "entities", label="Architecture refine")
        shape_problems = self._architecture_shape_problems(new_architecture)
        if shape_problems:
            self._p(f"skill:Architecture refine response was malformed ({'; '.join(shape_problems)}) — "
                    f"retrying with a stricter instruction...")
            retry_prompt = merge_prompt + (
                "\n\nIMPORTANT: 'entities' MUST be a JSON array of entity objects (each with its own "
                "name/table/fields), never a single string or free-text description. The same applies "
                "to 'endpoints'. Structure the ENTIRE architecture as proper nested objects and arrays — "
                "do not summarize any part of it as plain text, no matter how many entities there are."
            )
            new_architecture = self._architect_agent.generate(retry_prompt, stage="refine", max_tokens=16000, json_mode=True)
            new_architecture = self._recover_expected_shape(new_architecture, "entities", label="Architecture refine (retry)")
            shape_problems = self._architecture_shape_problems(new_architecture)
            if shape_problems:
                raise RuntimeError(
                    f"API architecture refine response was malformed even after a retry: "
                    f"{'; '.join(shape_problems)}. This usually means the request is too complex for "
                    f"one JSON response — try fewer entities/pages, or split the request."
                )
        new_entities_list = new_architecture.get("entities", [])
        new_endpoints = new_architecture.get("endpoints", [])
        new_entities_by_name = {e.get("name"): e for e in new_entities_list if e.get("name")}

        added_entity_names = [n for n in new_entities_by_name if n not in old_entities]
        modified_entity_names = [
            n for n in new_entities_by_name
            if n in old_entities
            and json.dumps(new_entities_by_name[n].get("fields", []), sort_keys=True)
                != json.dumps(old_entities[n].get("fields", []), sort_keys=True)
        ]

        def _endpoint_key(ep):
            return (ep.get("method", "").upper(), ep.get("path", ""))
        old_endpoint_keys = {_endpoint_key(ep) for ep in old_endpoints}
        added_endpoints = [ep for ep in new_endpoints if _endpoint_key(ep) not in old_endpoint_keys]

        endpoint_owner_names = set()
        for ep in added_endpoints:
            for name, entity in new_entities_by_name.items():
                if self._endpoints_for_entity([ep], entity):
                    endpoint_owner_names.add(name)
                    break

        affected_entity_names = sorted(
            (set(modified_entity_names) | endpoint_owner_names) - set(added_entity_names)
        )

        if not added_entity_names and not affected_entity_names:
            self._p("skill:No new or changed entities detected in the merged architecture — nothing to regenerate")
            return {
                "architecture": existing_architecture, "files": self.files,
                "addedEntities": [], "modifiedEntities": [],
            }

        self._p(f"skill:Architecture merged — {len(added_entity_names)} new entity(ies), "
                f"{len(affected_entity_names)} existing entity(ies) affected")
        self._flush_to_disk()

        architecture_json = json.dumps(new_architecture, indent=2)
        schema_sql = self.files.get(schema_path, "")
        added_entities = [new_entities_by_name[n] for n in added_entity_names]
        affected_entities = [new_entities_by_name[n] for n in affected_entity_names]
        fk_by_entity = {e.get("name"): self._entity_fk_map(e) for e in new_entities_list}

        # ── Schema: new tables for new entities, new columns for modified ───
        self._p("crew:Refine 3/4 — Updating schema...")
        if added_entities:
            added_schema_order = self._topo_order_entities(added_entities, fk_by_entity)

            def _run_schema_batch(batch):
                nonlocal schema_sql
                batch_names = [e.get("name") for e in batch]
                label = ", ".join(batch_names)
                for attempt in range(2):
                    prompt = self._build_data_batch_prompt(new_architecture, batch, language, database, schema_sql)
                    result = self._data_architect_agent.generate(prompt, max_tokens=8000, json_mode=True)
                    batch_files = self._coerce_files(result.get("files", {}), f"Refine schema ({label})")
                    if batch_files:
                        new_schema = batch_files.pop(schema_path, batch_files.pop("schema.sql", ""))
                        self.files.update(batch_files)
                        if new_schema:
                            schema_sql = (schema_sql + "\n\n" + new_schema).strip()
                            self.files[schema_path] = schema_sql
                        self._p(f"skill:{label} schema/model generated — "
                                f"{len(batch_files) + (1 if new_schema else 0)} files")
                        self._flush_to_disk()
                        return batch_files
                    if attempt == 0:
                        self._p(f"skill:Schema for {label} returned no files, retrying once...")
                return None

            self._run_with_adaptive_batching(added_schema_order, _run_schema_batch, self._ENTITY_BATCH_SIZE)

        pending_migrations: list[str] = []
        for name in modified_entity_names:
            old_fields = {f.get("name") for f in old_entities[name].get("fields", [])}
            new_fields = [f for f in new_entities_by_name[name].get("fields", []) if f.get("name") not in old_fields]
            if not new_fields:
                continue
            pending_migrations.extend(
                self._apply_schema_field_additions(name, new_entities_by_name[name], new_fields, language, schema_path)
            )

        if language == "python" and pending_migrations:
            self.files["migrations_pending.sql"] = (
                self.files.get("migrations_pending.sql", "").rstrip() + "\n" + "\n".join(pending_migrations)
            ).strip() + "\n"
            self._p(f"skill:Recorded {len(pending_migrations)} ALTER TABLE statement(s) in "
                    f"migrations_pending.sql — Python has no auto-migration, these get applied "
                    f"directly to the live database after restart")
        self._flush_to_disk()

        # ── Repositories: new entities fresh, affected entities preserved+extended ──
        # Affected entities' repositories already exist and may be called, by exact
        # method signature, from other entities' service code that ISN'T being
        # regenerated in this refine pass — a from-scratch rewrite here can silently
        # change or drop a method those unrelated callers still depend on, which is
        # a real compile-time break the LLM can't see coming since it never sees
        # that calling code. So affected entities get the existing file content and
        # a preserve-only-add instruction, exactly like the service/controller step
        # below does for the same reason.
        self._p("crew:Refine 4/4 — Updating repository interfaces and implementation...")
        repo_system = self._repository_system(language)

        def _existing_repo_files_for(entity_names: list) -> str:
            parts = []
            for path, content in sorted(self.files.items()):
                base = path.rsplit("/", 1)[-1]
                is_repo_path = "/repository/" in path or "/repositories/" in path
                if is_repo_path and any(self._filename_matches_entity(base, n) for n in entity_names if n):
                    parts.append(f"--- {path} ---\n{content}")
            return "\n\n".join(parts)

        if added_entities:
            added_repo_order = self._topo_order_entities(added_entities, fk_by_entity)

            def _run_new_repo_batch(batch):
                batch_names = [e.get("name") for e in batch]
                label = ", ".join(batch_names)
                for attempt in range(2):
                    prompt = self._build_repository_batch_prompt(
                        refine_prompt, new_architecture, batch, schema_sql, language, database,
                    )
                    result = self._call_llm(repo_system, prompt, max_tokens=8000)
                    batch_files = self._coerce_files(result.get("files", {}), f"Refine repositories ({label})")
                    if batch_files:
                        self.files.update(batch_files)
                        self._shared_contract_paths |= set(batch_files.keys())
                        self._p(f"skill:{label} repository interfaces created — {len(batch_files)} files")
                        self._flush_to_disk()
                        return batch_files
                    if attempt == 0:
                        self._p(f"skill:Repositories for {label} returned no files, retrying once...")
                return None

            self._run_with_adaptive_batching(added_repo_order, _run_new_repo_batch, self._ENTITY_BATCH_SIZE)

        affected_repo_targets = [
            e for e in affected_entities if _existing_repo_files_for([e.get("name")]).strip()
        ]
        if affected_repo_targets:
            affected_repo_order = self._topo_order_entities(affected_repo_targets, fk_by_entity)

            def _run_affected_repo_batch(batch):
                batch_names = [e.get("name") for e in batch]
                label = ", ".join(batch_names)
                existing_repo_files = _existing_repo_files_for(batch_names)
                for attempt in range(2):
                    prompt = REPOSITORY_REFINE_BATCH_USER.format(
                        refine_prompt=refine_prompt,
                        existing_repo_files=existing_repo_files,
                        entities_json=json.dumps(batch, indent=2),
                        entities_full_json=json.dumps(new_entities_list, indent=2),
                        endpoints_json=json.dumps(new_endpoints, indent=2),
                        schema_sql=schema_sql,
                        language=language, database=database,
                    )
                    result = self._call_llm(repo_system, prompt, max_tokens=8000)
                    batch_files = self._coerce_files(result.get("files", {}), f"Refine repositories ({label})")
                    if batch_files:
                        self.files.update(batch_files)
                        self._shared_contract_paths |= set(batch_files.keys())
                        self._p(f"skill:{label} repository interfaces updated — {len(batch_files)} files")
                        self._flush_to_disk()
                        return batch_files
                    if attempt == 0:
                        self._p(f"skill:Repositories for {label} returned no files, retrying once...")
                return None

            self._run_with_adaptive_batching(affected_repo_order, _run_affected_repo_batch, self._ENTITY_BATCH_SIZE)

        # ── Service/controller: new entities fresh, affected entities preserved+extended ──
        if added_entities:
            added_impl_order = self._topo_order_entities(added_entities, fk_by_entity)

            def _run_new_entity_batch(batch):
                batch_names = [e.get("name") or f"Entity{j}" for j, e in enumerate(batch, 1)]
                label = ", ".join(batch_names)
                batch_endpoints = []
                for e in batch:
                    batch_endpoints.extend(self._endpoints_for_entity(new_endpoints, e))
                max_tok = min(16000 * len(batch) + 8000, 64000)
                last_err: Exception | None = None
                for attempt in range(2):
                    try:
                        prompt = SERVICES_ENGINEER_API_BATCH_USER.format(
                            architecture_json=architecture_json,
                            entities_json=json.dumps(batch, indent=2),
                            batch_endpoints_json=json.dumps(batch_endpoints, indent=2),
                            shared_contract_files=self._shared_contract_files_text(),
                            existing_files_summary=self._files_summary(),
                            language=language, auth_type=auth_type,
                            rate_limiting=rate_limiting_str, database=database,
                        )
                        result = self._services_agent.generate(prompt, max_tokens=max_tok, json_mode=True)
                        batch_files = self._coerce_files(result.get("files", {}), label)
                        if batch_files:
                            self.files.update(batch_files)
                            self._shared_contract_paths |= {
                                p for p in batch_files if "/repository/" in p or "/repositories/" in p
                            }
                            if language == "python":
                                self._wire_python_router(batch_files)
                            self._p(f"skill:{label} implemented — {len(batch_files)} files")
                            self._flush_to_disk()
                            return batch_files
                    except Exception as e:
                        last_err = e
                    if attempt == 0:
                        self._p(f"skill:{label} implementation hit an issue, retrying once: {last_err or 'no files returned'}")
                self._p(f"skill:{label} implementation failed after retry — {last_err or 'no files returned'}")
                return None

            self._run_with_adaptive_batching(
                added_impl_order, _run_new_entity_batch, self._ENTITY_BATCH_SIZE,
                on_final_failure=lambda batch: self._remove_orphaned_files_for(batch, language),
            )

        if affected_entities:
            affected_order = self._topo_order_entities(affected_entities, fk_by_entity)

            def _run_refine_entity_batch(batch):
                batch_names = [e.get("name") for e in batch]
                label = ", ".join(batch_names)
                batch_endpoints = []
                for e in batch:
                    batch_endpoints.extend(self._endpoints_for_entity(new_endpoints, e))
                existing_batch_files = self._existing_files_text_for_entities(batch_names)
                max_tok = min(16000 * len(batch) + 8000, 64000)
                for attempt in range(2):
                    prompt = SERVICES_ENGINEER_API_REFINE_BATCH_USER.format(
                        refine_prompt=refine_prompt,
                        existing_batch_files=existing_batch_files,
                        shared_contract_files=self._shared_contract_files_text(),
                        architecture_json=architecture_json,
                        entities_json=json.dumps(batch, indent=2),
                        batch_endpoints_json=json.dumps(batch_endpoints, indent=2),
                        language=language, auth_type=auth_type,
                        rate_limiting=rate_limiting_str, database=database,
                    )
                    result = self._services_agent.generate(prompt, max_tokens=max_tok, json_mode=True)
                    batch_files = self._coerce_files(result.get("files", {}), f"Refine {label}")
                    if batch_files:
                        self.files.update(batch_files)
                        if language == "python":
                            self._wire_python_router(batch_files)
                        self._p(f"skill:{label} updated — {len(batch_files)} file(s) changed")
                        self._flush_to_disk()
                        return batch_files
                    if attempt == 0:
                        self._p(f"skill:Refining {label} hit an issue, retrying once...")
                # A refine batch returning nothing is indistinguishable here
                # between "genuinely no files needed changing" and "the call
                # failed" — treat as a soft no-op rather than orphan-cleanup:
                # unlike a brand-new entity, there's no new model file whose
                # absence would leave a dangling repository reference; the
                # existing one is simply left untouched either way.
                return {}

            self._run_with_adaptive_batching(affected_order, _run_refine_entity_batch, self._ENTITY_BATCH_SIZE)

        if language == "java":
            self._fix_pom_xml_unescaped_entities()
            self._remove_conflicting_java_security_classes()
            self._fix_java_sqlite_timestamp_format()
            self._fix_java_bare_date_literals()
            self._fix_java_jpa_relationship_json_cycles()
            self._ensure_java_open_session_in_view()
            self._ensure_java_property_reference_exception_handled()
            self._ensure_java_hibernate_sqlite_dialect_dep()
            self._ensure_java_ddl_auto_update()
            self._ensure_java_pagination_property()
        self._flush_to_disk()

        if language == "java":
            self._verify_and_repair_java()
            self._ensure_java_entity_scan_covers_all_entities()
            self._flush_to_disk()
        elif language == "python":
            self._verify_and_repair_python()
            # _wire_python_models_init() (called once, right after Stage 2)
            # is the ONLY thing that makes `import src.models` in
            # database.py actually register every model on Base.metadata —
            # without it, create_all() silently creates zero tables, no
            # error anywhere, until the first real request hits "no such
            # table". Stage 3 (repositories/implementation) and the
            # boot-repair loop just above both run LLM calls that can touch
            # src/models/*.py afterward (the boot-repair widens its own
            # touched-files set to every model file whenever any one of them
            # is implicated) with no re-check that __init__.py still
            # reflects the real, final set of model files. Reproduced
            # directly: a real generation's boot-check hit "no such table"
            # and its own repair pass gave up ("no usable fix"), and the
            # shipped app's src/models/ directory had no __init__.py at
            # all. Cheap and idempotent — rebuild it fresh from whatever
            # model files actually exist in self.files right now, as the
            # last word before this returns, regardless of what any
            # upstream stage did to it.
            self._wire_python_models_init()
            self._flush_to_disk()

        return {
            "architecture": new_architecture,
            "files": self.files,
            "addedEntities": added_entity_names,
            "modifiedEntities": affected_entity_names,
        }

    def _load_existing_files(self, project_dir: Path) -> dict:
        """
        Read every current source file for an already-generated project into
        a self.files-shaped dict, for refine() to build on top of. Narrow on
        purpose about what counts as a source file — build artifacts, the
        live database, credentials, and platform-internal marker files must
        never be treated as regenerable content or get accidentally clobbered
        by a later self.files write.
        """
        include_ext = {".java", ".py", ".sql", ".properties", ".xml", ".txt", ".md", ".yml", ".yaml"}
        exclude_dirs = {"target", "node_modules", "__pycache__", ".git", ".venv", "venv"}
        files: dict[str, str] = {}
        for path in project_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in include_ext:
                continue
            if any(part in exclude_dirs for part in path.parts):
                continue
            if path.name.startswith("."):
                continue
            rel = path.relative_to(project_dir).as_posix()
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except Exception:
                continue
        return files

    @staticmethod
    def _filename_matches_entity(filename: str, entity_name: str) -> bool:
        """Whole-word-prefix match on a file's stem — 'Sale' matches
        'SaleRepository.java' but NOT 'SalespersonRepository.java', where
        naive substring matching would wrongly hit both since 'Sale' is a
        literal prefix of 'Salesperson' too."""
        stem = filename.rsplit(".", 1)[0]
        if not stem.startswith(entity_name):
            return False
        rest = stem[len(entity_name):]
        return rest == "" or rest[0].isupper() or not rest[0].isalpha()

    def _existing_files_text_for_entities(self, entity_names: list) -> str:
        """Full content of every CURRENT file belonging to these entities —
        given to the refine prompt as 'here's what exists, preserve it,
        change only what's requested'."""
        parts = []
        for path, content in sorted(self.files.items()):
            base = path.rsplit("/", 1)[-1]
            if any(self._filename_matches_entity(base, name) for name in entity_names if name):
                parts.append(f"--- {path} ---\n{content}")
        return "\n\n".join(parts)

    @staticmethod
    def _sql_type_for(field_type: str) -> str:
        return {
            "integer": "INTEGER", "float": "REAL", "number": "REAL", "decimal": "REAL",
            "boolean": "INTEGER", "datetime": "TEXT", "uuid": "TEXT", "string": "TEXT",
        }.get((field_type or "string").lower(), "TEXT")

    def _apply_schema_field_additions(self, entity_name: str, entity: dict, new_fields: list,
                                       language: str, schema_path: str) -> list[str]:
        """
        New columns on an EXISTING table for a modified entity. Java needs no
        SQL here at all: Hibernate's spring.jpa.hibernate.ddl-auto=update
        (already set for every generated Java API) adds new @Column fields to
        the live table automatically on the next restart — updating the
        entity class is enough. Python has no equivalent: SQLAlchemy's
        create_all() only creates missing TABLES, it never alters an existing
        one — so this returns ALTER TABLE statements for the caller to record
        and apply directly against the live .db after restart, the same
        "bypass the app's own lifecycle" approach seeding already uses for
        exactly the same underlying reason.
        """
        table = entity.get("table") or (self._snake(entity_name) + "s")
        alters = []
        for f in new_fields:
            col = self._snake(f.get("name", ""))
            if not col:
                continue
            alters.append(f"ALTER TABLE {table} ADD COLUMN {col} {self._sql_type_for(f.get('type', 'string'))};")
        if not alters:
            return []

        current_schema = self.files.get(schema_path, "")
        if current_schema:
            self.files[schema_path] = (
                current_schema.rstrip() + f"\n\n-- Refine: added column(s) to {table}\n" + "\n".join(alters) + "\n"
            )

        if language == "java":
            self._p(f"skill:{entity_name} — {len(alters)} new column(s) added to the entity class; "
                    f"Hibernate's ddl-auto=update applies them to the live table on next restart, no SQL to run")
            return []
        return alters

    # ── Helper methods ────────────────────────────────────────────────────────

    # Data-modeling system prompt (Java + Python branches) moved to
    # AgentPlatform/catalog/api_data_architect/config.yaml's `role` field
    # (verbatim) -- see __init__'s self._data_architect_agent.

    def _expected_model_path(self, entity_name: str, language: str) -> str:
        """Delegates to AgentPlatform.core.codegen_batching (single source of
        truth, shared with WebUIGenerator's own per-entity generation)."""
        from AgentPlatform.core.codegen_batching import expected_model_path
        return expected_model_path(entity_name, language)

    def _expected_route_path(self, entity_name: str, language: str) -> str:
        """Delegates to AgentPlatform.core.codegen_batching."""
        from AgentPlatform.core.codegen_batching import expected_route_path
        return expected_route_path(entity_name, language)

    def _build_data_batch_prompt(self, architecture: dict, batch: list, language: str,
                                  database: str, accumulated_schema: str) -> str:
        schema_path = "src/main/resources/schema.sql" if language == "java" else "schema.sql"
        batch_names = [e.get("name") for e in batch if e.get("name")]
        accumulated_block = (
            f"Tables ALREADY created by earlier batches — if any entity in THIS batch has a "
            f"foreign key into one of these tables, reference the REAL table/column names exactly "
            f"as already defined below, do not guess:\n{accumulated_schema}\n\n"
            if accumulated_schema else ""
        )
        return (
            f"Generate ONLY the model/entity class(es) and the `{schema_path}` CREATE TABLE "
            f"statement(s) for THESE entities: {', '.join(batch_names)} — no seed data (that's a "
            f"separate call afterward), and nothing for any other entity; those are handled in "
            f"separate batches, before or after this one.\n\n"
            f"{accumulated_block}"
            f"Entities in this batch:\n{json.dumps(batch, indent=2)}\n\n"
            f"Language: {language}\n"
            f"Database: {database}\n\n"
            f"Return as JSON: {{\"files\": {{\"path\": \"content\", ...}}}} — include `{schema_path}` "
            f"containing ONLY this batch's CREATE TABLE statement(s), plus this batch's model/"
            f"entity class file(s)."
        )

    def _seed_data_system(self, language: str) -> str:
        filename = "src/main/resources/data.sql" if language == "java" else "seed_data.sql"
        return (
            "You are a data architect writing ONLY seed data for an already-finalized schema — "
            f"plain SQL INSERT statements, nothing else, into exactly one file: `{filename}`. Do "
            "NOT regenerate schema.sql, entity classes, or any other file in this call — this call "
            "produces that ONE file and nothing else.\n\n"
            "Every INSERT must match the REAL schema given below EXACTLY: table names, column "
            "names, and column order — do not guess or assume a typical/conventional naming that "
            "might not match what was actually generated.\n"
            "Every foreign key value you insert MUST reference a row inserted EARLIER in this same "
            "file — insert parent tables before the child tables that reference them.\n"
            "Timestamp literals MUST use the space-separated SQL format "
            "('yyyy-MM-dd HH:mm:ss'), never the ISO 'T'-separated format "
            "('yyyy-MM-ddTHH:mm:ss') — the JDBC/SQLite driver that later reads these rows back "
            "only accepts the space-separated form.\n"
            "Any single quote inside a string literal MUST be escaped by doubling it "
            "('O''Brien', 'Client''s account', 'don''t'), never a single unescaped quote — this "
            "is not a style preference, an unescaped quote breaks the SQL parser at that exact "
            "point, and everything after it in the file (every remaining row and table) fails "
            "with a generic, hard-to-diagnose 'unrecognized token' error that names neither the "
            "offending row nor which value caused it.\n\n"
            f"Output JSON: {{\"files\": {{\"{filename}\": \"...plain SQL INSERT statements...\"}}}}"
        )

    def _build_seed_data_batch_prompt(self, user_prompt: str, architecture: dict, batch: list,
                                       language: str, database: str, schema_sql: str,
                                       accumulated_sql: str) -> str:
        filename = "src/main/resources/data.sql" if language == "java" else "seed_data.sql"
        batch_names = [e.get("name") for e in batch if e.get("name")]
        accumulated_block = (
            f"Rows ALREADY inserted by earlier batches — if any entity in THIS batch has a foreign "
            f"key into one of these tables, reference the REAL id value used below; do not invent a "
            f"new parent row or guess an id that isn't actually here:\n{accumulated_sql}\n\n"
            if accumulated_sql else ""
        )
        # Requirements routinely use relative date language for "live"/
        # "today" pages — "date: YYYY-MM-DD (today and yesterday only)",
        # "last 7 days", "current month" — with nothing in this prompt to
        # anchor what "today" actually IS, so the model falls back to
        # whatever date its own training happens to bias toward. Reproduced
        # directly: a real generation seeded hourly_metrics as 2024-10-14/15
        # while the real date was 2026-09-07, so every "today"/"this hour"
        # card on the app's live-floor-style page queried a date that
        # doesn't exist in the data and came back empty — every OTHER page
        # (not date-scoped the same way) looked fine, which is what made it
        # look like a page-specific bug rather than a seed-data one.
        from datetime import date as _date
        today_str = _date.today().isoformat()
        return (
            f"Today's real date is {today_str}. Anchor any relative date language in the "
            f"requirements below (\"today\", \"yesterday\", \"this week\", \"last N days\", "
            f"\"current month\", etc.) to this actual date, not an arbitrary guess — a page that "
            f"shows \"today's\" data will query for {today_str} specifically, so seed rows dated "
            f"anywhere else are invisible to it.\n\n"
            f"Generate ONLY the seed-data INSERT statements for THESE entities: "
            f"{', '.join(batch_names)} — do not generate rows for any other entity/table; those are "
            f"handled in separate batches, before or after this one.\n\n"
            f"The original requirements (READ CAREFULLY for THIS batch's specific seed-data "
            f"quantities/rules — e.g. \"seed 3 manufacturers\" — and follow them exactly for these "
            f"entities; if none are specified for these particular entities, generate at least 3-5 "
            f"realistic rows per table so the API returns non-empty results immediately):\n"
            f"{user_prompt}\n\n"
            f"The REAL schema you must insert into — table names, column names, column order, and "
            f"foreign key columns; use these exactly, do not guess:\n"
            f"{schema_sql}\n\n"
            f"{accumulated_block}"
            f"Entities in this batch (for reference — field types/relationships):\n"
            f"{json.dumps(batch, indent=2)}\n\n"
            f"Language: {language}\n"
            f"Database: {database}\n\n"
            f"Return as JSON: {{\"files\": {{\"{filename}\": \"...INSERT statements for ONLY "
            f"{', '.join(batch_names)}...\"}}}}"
        )

    def _repository_system(self, language: str) -> str:
        if language == "java":
            return (
                "You are a data-access-layer engineer. Generate ONLY Spring Data JPA repository "
                "interfaces — exactly one per entity given, each `extends JpaRepository<Entity, "
                "IdType>` — and nothing else in this call (no models, no services, no controllers, "
                "no DTOs). Base package: com.api.repository. Use `String` as the ID type unless the "
                "architecture explicitly declares `uuid` for that specific entity's own id field.\n\n"
                "For EVERY entity given to you, read ALL endpoints across the ENTIRE API below — not "
                "just the ones that entity itself owns — and add whatever derived-query method "
                "(findBy.../existsBy.../countBy...) another entity's endpoint will need to call on "
                "THIS repository. Concretely: if some endpoint needs 'the most recent matching row "
                "for each of a list of ids from another table', THIS repository needs a method "
                "like findByXIdInAndY(List<String>, ...) or similar — work through the original "
                "requirements' own description of each endpoint to figure out exactly which "
                "repositories need which extra methods, even for entities NOT given to you in this "
                "particular call (their own repository is being generated in a separate call, but "
                "endpoints described below may still need a method on one of YOUR repositories).\n\n"
                "This matters more than usual: entity implementation happens in SEPARATE calls "
                "afterward, each of which reuses these interfaces exactly as generated here and "
                "must not redeclare or guess at them — if a needed method is missing here, nothing "
                "downstream can add it.\n\n"
                "Spring Data JPA derives the ENTIRE query from the method NAME alone, using its own "
                "fixed keyword parser (findBy, And, Or, In, GreaterThan, OrderBy, etc.) — it has NO "
                "concept of 'Optional' as a naming keyword. If a method should return "
                "`Optional<Entity>`, put that ONLY in the return type — do NOT also add the word "
                "\"Optional\" to the method name itself (e.g. write `Optional<Sale> "
                "findByVehicleId(String vehicleId)`, NEVER `findByVehicleIdOptional(String "
                "vehicleId)`). Getting this wrong doesn't fail to compile — javac has no way to check "
                "it — it fails at runtime, at application startup, when Spring tries to parse the "
                "method name and misreads \"Optional\" as a property path segment.\n\n"
                "Any method that takes a `Pageable` parameter (for a cross-entity query another "
                "endpoint needs paginated, per the instruction above) MUST return "
                "`Page<Entity>`, `Slice<Entity>`, `Window<Entity>`, or `List<Entity>` — NEVER "
                "`Optional<Entity>` with a Pageable parameter. Spring Data validates this at "
                "application startup, not at compile time: 'Method has to have one of the "
                "following return types [...]'. If the query is meant to return at most one row, "
                "drop the Pageable parameter entirely instead.\n\n"
                "Every derived-query parameter type MUST match the ACTUAL type of the entity field "
                "it is compared against, not just String for anything date/number-shaped. Reproduced "
                "directly: findByDate(String date) against a field declared 'private LocalDate "
                "date;' compiles fine (javac has no idea what type Spring will eventually compare it "
                "against) but fails at application startup with a Hibernate SemanticException "
                "'Cannot compare left expression of type java.time.LocalDate with right expression "
                "of type java.lang.String' the moment Spring tries to build the query. Use the "
                "entity field's own declared type for the parameter -- LocalDate for a LocalDate "
                "field, LocalDateTime for a LocalDateTime field, Integer/Long for the matching "
                "numeric wrapper -- never guess String as a safe default.\n\n"
                "Output JSON: {\"files\": {\"src/main/java/com/api/repository/XRepository.java\": \"...\"}}"
            )
        return (
            "You are a data-access-layer engineer. Generate ONLY SQLAlchemy data-access helper "
            "functions — one module per entity given, under src/repositories/ — and nothing else "
            "in this call (no schemas, no services, no routes).\n\n"
            "Use PLAIN SYNCHRONOUS SQLAlchemy — a `Session` parameter, plain `def` functions, "
            "`db.execute(stmt).scalars()...` with NO `await` anywhere. This is a hard requirement: "
            "database.py (from an earlier, separate call) is always synchronous, and every one of "
            "these functions must match it — a sync/async mismatch doesn't fail at import time, "
            "only on the first real request.\n\n"
            "For EVERY entity given to you, read ALL endpoints across the ENTIRE API below — not "
            "just the ones that entity itself owns — and add whatever query function another "
            "entity's endpoint will need to call against THIS entity's table (e.g. 'find all rows "
            "matching a list of foreign-key ids, filtered by status'). Work through the original "
            "requirements' own description of each endpoint to figure out exactly which modules "
            "need which extra functions, even for entities NOT given to you in this particular "
            "call — entity implementation happens in SEPARATE calls afterward that reuse these "
            "exactly as generated here.\n\n"
            "Output JSON: {\"files\": {\"src/repositories/x.py\": \"...\"}}"
        )

    def _build_repository_batch_prompt(self, user_prompt: str, architecture: dict, batch: list,
                                        schema_sql: str, language: str, database: str) -> str:
        entities = architecture.get("entities", [])
        endpoints = architecture.get("endpoints", [])
        batch_names = [e.get("name") for e in batch if e.get("name")]
        # Nothing else in this prompt says WHERE each entity's model class
        # actually lives — the data-modeling stage names model files after
        # the ENTITY name (_expected_model_path: snake_case, e.g. entity
        # "HandoffNote" -> src/models/handoff_note.py), but this call is
        # never told that, and schema_sql only gives it the TABLE name
        # ("handoff_notes"). Reproduced directly: a repository guessed the
        # import path from the table name instead
        # (`from src.models.handoff_notes import HandoffNote`), which
        # doesn't exist, and the resulting import error's own repair pass
        # — shown only the broken repository file, with no way to discover
        # the real model's location — "fixed" it by writing an entire
        # SECOND model file at the guessed path rather than correcting the
        # import, leaving two classes both mapped to the same table.
        # Removing the ambiguity here is cheaper and more reliable than
        # catching the fallout after the fact.
        model_import_lines = []
        for e in entities:
            name = e.get("name")
            if not name:
                continue
            model_path = self._expected_model_path(name, language)
            if language == "java":
                pkg = model_path[len("src/main/java/"):-len(".java")].replace("/", ".")
                model_import_lines.append(f"- {name}: import {pkg};")
            else:
                module = model_path[:-3].replace("/", ".")
                model_import_lines.append(f"- {name}: from {module} import {name}")
        model_import_block = "\n".join(model_import_lines)
        return (
            f"Generate the repository/DAO interface for ONLY these entities: "
            f"{', '.join(batch_names)} — nothing for any other entity; those are handled in "
            f"separate batches, before or after this one. (You still need to read every endpoint "
            f"below, including ones for other entities, to catch cross-entity query needs on YOUR "
            f"repositories.)\n\n"
            f"Original requirements (read carefully — several endpoints below describe exactly "
            f"what cross-entity queries will be needed):\n{user_prompt}\n\n"
            f"This batch's entities:\n{json.dumps(batch, indent=2)}\n\n"
            f"All entities in the API (for reference — field types/relationships of entities NOT "
            f"in this batch):\n{json.dumps(entities, indent=2)}\n\n"
            f"The EXACT, already-decided import for every entity's model class — use these "
            f"verbatim whenever a repository needs to reference an entity's model (including this "
            f"batch's OWN entities), do NOT derive your own import path from the table name or "
            f"guess a different casing/pluralization:\n{model_import_block}\n\n"
            f"All endpoints in the API:\n{json.dumps(endpoints, indent=2)}\n\n"
            f"The real, already-finalized schema:\n{schema_sql}\n\n"
            f"Language: {language}\n"
            f"Database: {database}\n\n"
            f"Return as JSON: {{\"files\": {{\"path\": \"content\", ...}}}}"
        )

    def _generate_packaging(self, architecture: dict, language: str, database: str) -> dict:
        """Generate Dockerfile, docker-compose, and Makefile."""
        project_name = architecture.get("projectName", "api-app")
        files = {}

        if language == "python":
            files["Dockerfile"] = (
                "FROM python:3.12-slim AS builder\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "\n"
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages\n"
                "COPY --from=builder /usr/local/bin /usr/local/bin\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                "HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8000/health || exit 1\n"
                "CMD [\"uvicorn\", \"src.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n"
            )
        elif language == "java":
            files["Dockerfile"] = (
                "FROM maven:3.9-eclipse-temurin-21 AS builder\n"
                "WORKDIR /app\n"
                "COPY pom.xml .\n"
                "RUN mvn dependency:go-offline -B\n"
                "COPY src ./src\n"
                "RUN mvn package -DskipTests -B\n"
                "\n"
                "FROM eclipse-temurin:21-jre-alpine\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app/target/*.jar app.jar\n"
                "EXPOSE 8080\n"
                "HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:8080/health || exit 1\n"
                "ENTRYPOINT [\"java\", \"-jar\", \"app.jar\"]\n"
            )

        port = "8000" if language == "python" else "8080"
        db_service = ""
        if database == "postgresql":
            db_service = (
                "  db:\n"
                "    image: postgres:16-alpine\n"
                "    environment:\n"
                "      POSTGRES_DB: app\n"
                "      POSTGRES_USER: app\n"
                "      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}\n"
                "    ports:\n"
                "      - '5432:5432'\n"
                "    volumes:\n"
                "      - pgdata:/var/lib/postgresql/data\n"
                "\n"
            )

        # No redis service — rate limiting is in-memory (single-instance, "start
        # simple" per design decision), so nothing in the generated code actually
        # talks to Redis. Shipping an unused container would just be confusing.
        depends_on = "    depends_on:\n      - db\n" if database == "postgresql" else ""
        files["docker-compose.yml"] = (
            f"version: '3.8'\n"
            f"services:\n"
            f"  api:\n"
            f"    build: .\n"
            f"    ports:\n"
            f"      - '{port}:{port}'\n"
            f"    env_file: .env\n"
            f"{depends_on}"
            f"\n"
            f"{db_service}"
            f"{'volumes:\\n  pgdata:\\n' if database == 'postgresql' else ''}"
        )

        run_cmd = "uvicorn src.main:app --reload --port 8000" if language == "python" else "mvn spring-boot:run"
        test_cmd = "pytest tests/ -v" if language == "python" else "mvn test"

        files["Makefile"] = (
            f".PHONY: run test docker-up docker-down\n\n"
            f"run:\n"
            f"\t{run_cmd}\n\n"
            f"test:\n"
            f"\t{test_cmd}\n\n"
            f"docker-up:\n"
            f"\tdocker-compose up --build -d\n\n"
            f"docker-down:\n"
            f"\tdocker-compose down\n"
        )

        return files

    def _generate_env_example(self, language: str, auth_type: str, database: str,
                               rate_limit: int = 100, real: bool = False) -> str:
        """real=True generates an actually-usable credential (for .env); real=False
        writes a placeholder (for .env.example)."""
        # No APP_PORT here — the platform assigns each project's real port
        # dynamically (see api_runner.py's own PORT env var / --server.port
        # argument, tracked in .ports.json), and nothing generated ever reads
        # an APP_PORT variable at all. A hardcoded 8000/8080 here would be
        # dead AND wrong the moment two projects of the same language exist,
        # the same "looks authoritative but isn't" trap DATABASE_URL was for
        # Java — don't reintroduce it for a different variable.
        lines = [
            "# Application",
            "APP_ENV=development",
        ]
        # Java never reads DATABASE_URL — its connection config lives entirely
        # in application.properties/a Java @Bean DataSource, set at generation
        # time, not from the environment. Putting a DATABASE_URL here anyway
        # would just be a second, disconnected-looking value that happens to
        # LOOK authoritative but isn't — reproduced directly (a Java project's
        # .env said one .db filename, the app actually used a different one it
        # picked for itself). Only emit this section where it's actually true.
        if language == "python":
            lines += ["", "# Database"]
            # Python generation is instructed to use SQLAlchemy's plain
            # SYNCHRONOUS engine throughout (see api_data_architect's role) — an
            # async-driver URL scheme here (sqlite+aiosqlite / postgresql+asyncpg)
            # would silently reintroduce the exact sync/async mismatch that
            # instruction exists to prevent: create_engine() with an
            # aiosqlite/asyncpg URL doesn't fail at startup, it fails the first
            # time a real connection is attempted (MissingGreenlet:
            # "greenlet_spawn has not been called"), reproduced directly.
            if database == "postgresql":
                lines += [
                    "DATABASE_URL=postgresql://app:changeme@localhost:5432/app",
                    "DB_PASSWORD=changeme",
                ]
            else:
                lines += [f"DATABASE_URL=sqlite:///./{self._db_filename()}.db"]

        lines += ["", "# Security — rate limiting + usage metering are always on;", "# auth is none/basic (api_key/jwt fall back to LLM-authored security)",
                   f"API_AUTH_TYPE={auth_type}"]
        if auth_type == "basic":
            password = secrets.token_urlsafe(12) if real else "changeme"
            lines += [
                "API_BASIC_AUTH_USERNAME=admin",
                f"API_BASIC_AUTH_PASSWORD={password}",
            ]
        elif auth_type == "jwt":
            lines += [
                "JWT_SECRET_KEY=your-secret-key-change-in-production",
                "JWT_ALGORITHM=HS256",
                "JWT_EXPIRATION_MINUTES=30",
            ]
        elif auth_type == "api_key":
            lines += ["API_KEY_HEADER=X-API-Key"]

        lines += [
            "",
            "# Rate Limiting",
            f"RATE_LIMIT_RPM={rate_limit}",
            "",
            "# CORS",
            "CORS_ORIGINS=http://localhost:3000,http://localhost:8080",
        ]
        if language == "python":
            # Read once, deterministically, in src/database.py
            # (_ensure_python_database_py) and imported by every list route
            # — see MAX_PAGE_SIZE there for why this needs to be a single,
            # externally-adjustable source of truth rather than a literal
            # each route's own generation call picks independently.
            lines += [
                "",
                "# Pagination — max rows a single list request may return.",
                "# Every generated frontend page requests up to this many rows in one",
                "# call to fetch a full table; lowering this without also changing the",
                "# frontend will make those pages show partial data.",
                "MAX_PAGE_SIZE=1000",
            ]
        return "\n".join(lines) + "\n"

    def _ensure_shared_exceptions(self, language: str):
        """
        Defensive fallback for the bootstrap call's shared exception classes
        (see SERVICES_ENGINEER_API_BOOTSTRAP_USER). Every entity batch call is
        told these already exist and imports them without re-declaring them
        (see SERVICES_ENGINEER_API_BATCH_USER) — so if bootstrap doesn't
        actually generate them, whichever entity happens to need one first
        fails to compile/import with an error that looks like it's that
        entity's fault, when the real gap is upstream. Inject a minimal
        version whenever the corresponding bootstrap file is missing, same
        reasoning as the deterministic security middleware: this must exist
        every generation, not just when the LLM remembers to write it.
        """
        if language == "java":
            base = "src/main/java/com/api/exception/"
            if base + "ResourceNotFoundException.java" not in self.files:
                self.files[base + "ResourceNotFoundException.java"] = (
                    "package com.api.exception;\n\n"
                    "public class ResourceNotFoundException extends RuntimeException {\n"
                    "    public ResourceNotFoundException(String message) {\n"
                    "        super(message);\n"
                    "    }\n"
                    "}\n"
                )
            if base + "ConflictException.java" not in self.files:
                self.files[base + "ConflictException.java"] = (
                    "package com.api.exception;\n\n"
                    "public class ConflictException extends RuntimeException {\n"
                    "    public ConflictException(String message) {\n"
                    "        super(message);\n"
                    "    }\n"
                    "}\n"
                )
            if base + "GlobalExceptionHandler.java" not in self.files:
                self.files[base + "GlobalExceptionHandler.java"] = (
                    "package com.api.exception;\n\n"
                    "import org.springframework.http.HttpStatus;\n"
                    "import org.springframework.http.ResponseEntity;\n"
                    "import org.springframework.web.bind.MethodArgumentNotValidException;\n"
                    "import org.springframework.web.bind.annotation.ExceptionHandler;\n"
                    "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
                    "import java.util.HashMap;\n"
                    "import java.util.Map;\n\n"
                    "@RestControllerAdvice\n"
                    "public class GlobalExceptionHandler {\n\n"
                    "    @ExceptionHandler(ResourceNotFoundException.class)\n"
                    "    public ResponseEntity<Map<String, String>> handleNotFound(ResourceNotFoundException ex) {\n"
                    "        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(errorBody(ex.getMessage()));\n"
                    "    }\n\n"
                    "    @ExceptionHandler(ConflictException.class)\n"
                    "    public ResponseEntity<Map<String, String>> handleConflict(ConflictException ex) {\n"
                    "        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorBody(ex.getMessage()));\n"
                    "    }\n\n"
                    "    @ExceptionHandler(MethodArgumentNotValidException.class)\n"
                    "    public ResponseEntity<Map<String, String>> handleValidation(MethodArgumentNotValidException ex) {\n"
                    "        String message = ex.getBindingResult().getFieldErrors().stream()\n"
                    "                .findFirst()\n"
                    "                .map(f -> f.getField() + \" \" + f.getDefaultMessage())\n"
                    "                .orElse(\"Validation failed\");\n"
                    "        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorBody(message));\n"
                    "    }\n\n"
                    "    private Map<String, String> errorBody(String message) {\n"
                    "        Map<String, String> body = new HashMap<>();\n"
                    "        body.put(\"error\", message);\n"
                    "        return body;\n"
                    "    }\n"
                    "}\n"
                )
        else:
            if "src/exceptions.py" not in self.files:
                self.files["src/exceptions.py"] = (
                    "class ResourceNotFoundException(Exception):\n"
                    "    pass\n\n\n"
                    "class ConflictException(Exception):\n"
                    "    pass\n"
                )
            main_py = self.files.get("src/main.py", "")
            if main_py and "ResourceNotFoundException" not in main_py:
                self.files["src/main.py"] = main_py + (
                    "\n\n# --- Shared error handling (auto-generated, do not remove) ---\n"
                    "from fastapi import Request\n"
                    "from fastapi.responses import JSONResponse\n"
                    "from fastapi.exceptions import RequestValidationError\n"
                    "from starlette.exceptions import HTTPException as StarletteHTTPException\n"
                    "from src.exceptions import ResourceNotFoundException, ConflictException\n\n"
                    "@app.exception_handler(ResourceNotFoundException)\n"
                    "async def _handle_not_found(request: Request, exc: ResourceNotFoundException):\n"
                    "    return JSONResponse(status_code=404, content={\"error\": str(exc)})\n\n"
                    "@app.exception_handler(ConflictException)\n"
                    "async def _handle_conflict(request: Request, exc: ConflictException):\n"
                    "    return JSONResponse(status_code=400, content={\"error\": str(exc)})\n\n"
                    "@app.exception_handler(StarletteHTTPException)\n"
                    "async def _handle_http_exception(request: Request, exc: StarletteHTTPException):\n"
                    "    return JSONResponse(status_code=exc.status_code, content={\"error\": exc.detail})\n\n"
                    "@app.exception_handler(RequestValidationError)\n"
                    "async def _handle_validation_error(request: Request, exc: RequestValidationError):\n"
                    "    return JSONResponse(status_code=400, content={\"error\": str(exc.errors())})\n"
                )

    def _normalize_python_layout(self):
        """
        Defensive normalization: despite an explicit prompt requirement, the LLM
        has repeatedly still put the FastAPI entry point at the project root (with
        its own code under app/) instead of src/main.py — the same class of
        "prompt alone isn't a strong enough guarantee" problem this session hit
        with skill matching and the radar chart. Detect that and relocate
        everything under src/ so the Dockerfile/Makefile/dev-server launcher's
        hardcoded `uvicorn src.main:app` keeps working regardless of what the LLM
        actually produced.
        """
        if "src/main.py" in self.files:
            return  # already compliant

        candidates = [p for p in self.files if p.split("/")[-1] == "main.py"]
        if not candidates:
            self._p("skill:WARNING — no main.py found anywhere; dev server will likely fail to start")
            return
        # Prefer the shallowest match (root main.py over a deeply nested one).
        entry = min(candidates, key=lambda p: p.count("/"))

        # The LLM's own package root (e.g. "app") can be a DIFFERENT directory
        # than wherever main.py itself landed — e.g. main.py at the project root
        # with the rest of the code under app/. Detect it from the most common
        # top-level directory among generated .py files, ignoring scaffolding
        # dirs that are never the app's own package.
        IGNORED_TOP = {"tests", "test", "alembic", "seeds", "migrations", "src"}
        from collections import Counter
        top_dirs = Counter()
        for path in self.files:
            if not path.endswith(".py"):
                continue
            parts = path.split("/")
            if len(parts) > 1 and parts[0] not in IGNORED_TOP:
                top_dirs[parts[0]] += 1
        pkg_root = top_dirs.most_common(1)[0][0] if top_dirs else None

        moved = {}
        for path, content in self.files.items():
            if path == entry:
                new_path = "src/main.py"
            elif pkg_root and path.startswith(pkg_root + "/"):
                new_path = f"src/{path}"
            elif "/" not in path and path.endswith(".py"):
                # Other root-level modules sitting alongside a root main.py.
                new_path = f"src/{path}"
            else:
                moved[path] = content
                continue
            moved[new_path] = content
        self.files = moved

        if pkg_root:
            # Everything that imported `<pkg_root>.xxx` now needs `src.<pkg_root>.xxx`
            # — patch every generated .py file, not just the ones that moved (e.g.
            # alembic/env.py stays put but still imports from the package that moved).
            old_from, new_from = f"from {pkg_root}.", f"from src.{pkg_root}."
            old_import, new_import = f"import {pkg_root}.", f"import src.{pkg_root}."
            for path in list(self.files.keys()):
                if not path.endswith(".py"):
                    continue
                content = self.files[path]
                patched = content.replace(old_from, new_from).replace(old_import, new_import)
                if patched != content:
                    self.files[path] = patched

        self._p(f"skill:Normalized entry point ({entry} -> src/main.py, pkg_root={pkg_root}) — LLM didn't follow the required layout")

    def _ensure_dotenv_loaded_early(self):
        """
        Defensive fix — observed directly: DATABASE_URL (and anything else read via
        os.getenv(...) at module-import time, e.g. in a settings/database module
        imported near the top of main.py) was silently ignored, because nothing
        calls load_dotenv() before those imports run. security_bootstrap.py's own
        load_dotenv() call doesn't help here — it's imported at the END of main.py,
        which is far too late for code that already ran during main.py's own
        top-of-file imports. Prepending it to main.py itself fixes this for every
        module main.py imports, not just the deterministic security files.
        """
        if "src/main.py" not in self.files:
            return
        content = self.files["src/main.py"]
        if "load_dotenv" in content:
            return  # LLM already loads it somewhere — don't add a second call
        self.files["src/main.py"] = (
            "from dotenv import load_dotenv as _load_dotenv\n"
            "_load_dotenv()\n\n"
        ) + content

    def _generate_security_middleware(self, language: str, auth_type: str, rate_limit: int) -> dict:
        """
        Deterministic (non-LLM) rate-limit + usage-metering + optional basic-auth
        files, copied verbatim from AgentPlatform/catalog/api_security_engineer/
        templates/ — owned by the same agent that handles jwt/api_key auth via
        LLM (see __init__'s self._security_agent), just via a static copy
        instead of a generate() call for the none/basic auth types, since this
        infra must behave identically every generation, which a
        temperature-driven LLM call for "write me some security middleware"
        can't guarantee — see this project's plan notes on the ai-chat/
        radar-chart bugs that motivated moving this kind of guarantee out of
        prompts and into code.
        """
        templates_dir = self._security_agent.templates_dir
        files: dict[str, str] = {}

        if language == "java":
            java_src = templates_dir / "java"
            base = "src/main/java/com/api/security"
            for fname in ("RateLimitFilter.java", "UsageTrackingFilter.java", "UsageController.java", "HealthController.java", "UsageDb.java"):
                files[f"{base}/{fname}"] = (java_src / fname).read_text(encoding="utf-8")
            if auth_type == "basic":
                files[f"{base}/SecurityConfig.java"] = (java_src / "SecurityConfig.java").read_text(encoding="utf-8")
        else:
            py_src = templates_dir / "python"
            mw_dir = py_src / "middleware"
            for fname in ("__init__.py", "client_id.py", "rate_limit.py", "usage_tracking.py"):
                files[f"src/middleware/{fname}"] = (mw_dir / fname).read_text(encoding="utf-8")
            if auth_type == "basic":
                files["src/middleware/basic_auth.py"] = (mw_dir / "basic_auth.py").read_text(encoding="utf-8")
            files["src/security_bootstrap.py"] = (py_src / "security_bootstrap.py").read_text(encoding="utf-8")

        return files

    # ── Deterministic test generation ───────────────────────────────────────
    # Replaces the old LLM-based "Test Engineer" stage. The architecture JSON
    # already fully describes entities (fields, types, relationships) and
    # endpoints — there's no judgment call left for an LLM to make for
    # standard CRUD/auth/404/rate-limit coverage, and no need to invent
    # example data: sample values are synthesized deterministically from each
    # field's declared type, and fixtures are created for real via the API
    # itself (in FK dependency order) rather than hand-authored. This also
    # sidesteps the exact failure mode that motivated the change: one combined
    # "tests + OpenAPI spec + README" completion routinely exceeded 100k chars
    # and got truncated with no way to repair itself.

    _SKIP_PAYLOAD_FIELDS = {"id", "created_at", "createdat", "updated_at", "updatedat"}
    _RANDOM_EMAIL_MARKER = "__RANDOM_EMAIL__"
    _RANDOM_CODE_MARKER = "__RANDOM_CODE__"

    @staticmethod
    def _snake(name: str) -> str:
        """Delegates to AgentPlatform.core.codegen_batching."""
        from AgentPlatform.core.codegen_batching import snake_case
        return snake_case(name)

    @staticmethod
    def _split_path(path: str) -> list[str]:
        return [seg for seg in (path or "").strip("/").split("/") if seg]

    @staticmethod
    def _is_param_seg(seg: str) -> bool:
        return seg.startswith("{") and seg.endswith("}")

    @staticmethod
    def _norm(s: str) -> str:
        return "".join(ch for ch in (s or "").lower() if ch.isalnum())

    def _seed_column_values(self, seed_sql: str, table: str, column: str) -> list[str]:
        """Every value inserted into `column` for `table`'s rows in a seed
        SQL script — used to empirically verify column uniqueness (see
        _fix_invalid_one_to_one_relationships below) rather than guessing
        from architecture field metadata, which carries no uniqueness
        information at all. Same INSERT-parsing shape as
        _fix_java_bare_date_literals (top-level-quote-aware comma split),
        reused here for the same reason: a naive split on "," would misread
        a comma inside a quoted string value as a column boundary."""
        m = re.search(
            rf'INSERT INTO {re.escape(table)} \(([^)]+)\) VALUES((?:\s*\([^;]*?\)\s*[,;])+)',
            seed_sql,
        )
        if not m:
            return []
        columns = [c.strip().strip('"').strip('`') for c in m.group(1).split(",")]
        if column not in columns:
            return []
        col_idx = columns.index(column)
        body = m.group(2)

        def _split_top_level(s: str) -> list[str]:
            parts, buf, in_str, i = [], [], False, 0
            while i < len(s):
                ch = s[i]
                if in_str:
                    if ch == "'" and s[i:i + 2] == "''":
                        buf.append("''")
                        i += 2
                        continue
                    if ch == "'":
                        in_str = False
                    buf.append(ch)
                else:
                    if ch == "'":
                        in_str = True
                        buf.append(ch)
                    elif ch == ",":
                        parts.append("".join(buf))
                        buf = []
                        i += 1
                        continue
                    else:
                        buf.append(ch)
                i += 1
            parts.append("".join(buf))
            return parts

        values = []
        for tm in re.finditer(r"\(([^()]*)\)", body):
            row_values = _split_top_level(tm.group(1))
            if col_idx < len(row_values):
                values.append(row_values[col_idx].strip())
        return values

    def _entity_column_categories(self, model_source: str, language: str) -> dict[str, str]:
        """
        Map SQL column name -> coarse type category ('integer'/'real'/
        'text'/'blob'), read from the actual ORM model that Hibernate/
        SQLAlchemy will materialize into the real table — the ground truth
        schema.sql must agree with (see
        _reconcile_schema_types_with_entities, the caller).
        """
        categories: dict[str, str] = {}
        if language == "java":
            # Field declarations, each preceded SOMEWHERE by a
            # @Column(name="x") annotation — annotation order varies
            # (@Id/@GeneratedValue before @Column for an identity PK,
            # @NotBlank/@NotNull after it for a plain field), so rather than
            # assume one order, scan the text between consecutive field
            # declarations for the nearest @Column(name=...).
            field_matches = list(re.finditer(
                r"(?:private|protected|public)\s+([\w.]+)(?:<[\w.,\s<>]+>)?\s+(\w+)\s*;",
                model_source,
            ))
            window_start = 0
            for m in field_matches:
                window = model_source[window_start:m.start()]
                col_m = re.search(r'@Column\s*\(\s*name\s*=\s*"(\w+)"', window)
                if col_m:
                    java_type = m.group(1).rsplit(".", 1)[-1].lower()
                    category = self._JAVA_TYPE_CATEGORY.get(java_type)
                    if category:
                        categories[col_m.group(1)] = category
                window_start = m.end()
        else:
            # SQLAlchemy 2.0 declarative style: `name: Mapped[Type] =
            # mapped_column(...)` (or legacy `name = Column(Type, ...)`) —
            # the attribute name IS the column name, matching every model
            # this platform generates (no name= override in practice).
            for m in re.finditer(r"(\w+)\s*:\s*Mapped\[\s*(?:Optional\[\s*)?([\w.]+)", model_source):
                attr, py_type = m.group(1), m.group(2).rsplit(".", 1)[-1].lower()
                category = self._PYTHON_TYPE_CATEGORY.get(py_type)
                if category:
                    categories[attr] = category
            for m in re.finditer(r"(\w+)\s*=\s*Column\(\s*([\w.]+)", model_source):
                attr, py_type = m.group(1), m.group(2).rsplit(".", 1)[-1].lower()
                category = self._PYTHON_TYPE_CATEGORY.get(py_type)
                if category and attr not in categories:
                    categories[attr] = category
        return categories

    def _reconcile_schema_types_with_entities(self, schema_sql: str, entities: list, language: str) -> tuple[str, list[str]]:
        """
        schema.sql and its entity's ORM class are generated together in the
        same batch (_run_data_batch) but nothing checks they describe the
        SAME column types — reproduced directly: schema.sql declared `id
        TEXT PRIMARY KEY` while the Java entity declared `@Id private Long
        id` (GenerationType.IDENTITY). Hibernate/SQLAlchemy build the REAL
        table from the entity class (ddl-auto=update / create_all), never
        from schema.sql directly, so when the two disagree, the entity's
        type is what actually exists at runtime — but the seed-data stage
        that runs right after this one reads schema.sql as its ground
        truth, generating string ids to match schema.sql's (wrong) TEXT
        declaration, which then fails to insert into the real INTEGER
        column ("datatype mismatch"), leaving every table permanently
        empty with no retry.

        Deterministically corrects schema.sql's column types to match the
        entity — no LLM call needed, since the entity is unambiguous ground
        truth once read. Best-effort: an entity/table this can't confidently
        match (name derivation miss, unparseable model) is left untouched
        rather than guessed at. Returns (corrected_schema_sql, list of
        human-readable fix descriptions, empty if nothing disagreed).
        """
        if not schema_sql:
            return schema_sql, []
        from AgentPlatform.core.codegen_batching import sql_type_category
        fixes: list[str] = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name")
            if not name:
                continue
            table = entity.get("table") or (self._snake(name) + "s")
            model_source = self.files.get(self._expected_model_path(name, language))
            if not model_source:
                continue
            entity_categories = self._entity_column_categories(model_source, language)
            if not entity_categories:
                continue

            table_m = re.search(
                rf'CREATE TABLE(?:\s+IF NOT EXISTS)?\s+"?{re.escape(table)}"?\s*\(([\s\S]*?)\)\s*;',
                schema_sql, re.IGNORECASE,
            )
            if not table_m:
                continue
            block = table_m.group(1)

            for column, expected_category in entity_categories.items():
                col_m = re.search(
                    rf'(^|,)(\s*"?{re.escape(column)}"?\s+)(\w+)(?:\([^)]*\))?',
                    block, re.MULTILINE,
                )
                if not col_m:
                    continue
                declared_category = sql_type_category(col_m.group(3))
                if declared_category is None or declared_category == expected_category:
                    continue
                canonical = self._CANONICAL_SQL_TYPE[expected_category]
                block = block[:col_m.start()] + col_m.group(1) + col_m.group(2) + canonical + block[col_m.end():]
                fixes.append(
                    f"{table}.{column}: schema.sql declared {col_m.group(3).upper()} but the "
                    f"generated entity uses a {expected_category} type — corrected to {canonical} "
                    f"(the entity is what Hibernate/SQLAlchemy actually creates; seed data must "
                    f"match it, not schema.sql's original guess)"
                )
            if block != table_m.group(1):
                schema_sql = schema_sql[:table_m.start(1)] + block + schema_sql[table_m.end(1):]
        return schema_sql, fixes

    def _strip_invalid_java_relationship_field(self, java_source: str, target_entity_name: str) -> str | None:
        """
        Remove a @OneToOne/@ManyToOne relationship field (and its getter/
        setter) targeting `target_entity_name`, by the property-name
        convention this pipeline's own entity generation always follows
        (field named exactly like the target class, lowerCamelCase).

        Why this exists at all: _fix_invalid_one_to_one_relationships (the
        caller) drops the relationship from the abstract entities JSON, but
        that JSON only drives LATER stages (routes/services) — it does NOT
        get re-read by anything that regenerates entity classes, because
        those were already written in Stage 2a, one stage EARLIER than this
        check even runs (it needs real seed data to know the relationship
        is invalid, and seed data is Stage 2b). Left unscrubbed, the
        already-written .java file keeps the invalid @ManyToOne/@JoinColumn
        exactly as originally generated — reproduced directly: the build
        log correctly reported "Trade's 'belongs_to Position' ... Dropped",
        while Trade.java's real source still had
        `@ManyToOne @JoinColumn(name="client_name", referencedColumnName=
        "client_name")`, crashing every request that touched it with
        Hibernate's "More than one row with the given identifier was
        found" the moment seed data actually existed to trigger it (this
        was invisible for as long as seeding itself was separately broken
        and every table was empty).

        Best-effort and conservative like every other regex-based fixer in
        this file: returns None (caller keeps the original source
        untouched and says so) if the expected shape isn't found with
        confidence, rather than risk a partial/garbled edit.
        """
        prop = target_entity_name[0].lower() + target_entity_name[1:]
        field_pattern = re.compile(
            rf'(?:[ \t]*@[\w.]+(?:\([^)]*\))?\n)+[ \t]*private\s+{re.escape(target_entity_name)}\s+'
            rf'{re.escape(prop)}\s*;\n'
        )
        new_source, n_field = field_pattern.subn("", java_source)
        if n_field != 1:
            return None
        accessor_pattern = re.compile(
            rf'\n[ \t]*public\s+{re.escape(target_entity_name)}\s+get{re.escape(target_entity_name)}'
            rf'\s*\(\s*\)\s*\{{[^{{}}]*\}}'
            rf'\s*public\s+void\s+set{re.escape(target_entity_name)}'
            rf'\s*\(\s*{re.escape(target_entity_name)}\s+\w+\s*\)\s*\{{[^{{}}]*\}}\n'
        )
        new_source, n_accessors = accessor_pattern.subn("\n", new_source)
        if n_accessors != 1:
            return None
        return new_source

    def _fix_invalid_one_to_one_relationships(self, entities: list, seed_sql: str, language: str = "java") -> list[str]:
        """
        Drops any "has_one" OR "belongs_to" relationship whose target
        column isn't actually unique in the real seed data — mutates
        `entities` IN PLACE (the offending relationship and whatever
        relationship the other entity declares back at it, so Stage 3
        never encodes a one-sided, dangling reference) and returns the
        corrections made as human-readable strings, empty if every
        checked relationship held up.

        Also retroactively scrubs the now-invalid relationship field out of
        the entity's ALREADY-WRITTEN model source (Java only for now — see
        _strip_invalid_java_relationship_field's docstring for exactly why
        this is necessary and not redundant with the JSON mutation above).
        Python's equivalent (SQLAlchemy relationship()/ForeignKey) isn't
        handled here yet — not verified against a real generated example,
        so it's left alone rather than guessed at.

        Both "has_one" (E has exactly one TARGET via column F — becomes
        @OneToOne) and "belongs_to" (E points at exactly one TARGET via F
        — becomes @ManyToOne) carry the SAME requirement: F must be
        genuinely unique in TARGET's own table, or there's no way to know
        which of several matching rows is "the" one. Reproduced directly
        on the has_one case: RiskMetric declared has_one Position via
        client_name, but positions.client_name repeats 8-15x per client in
        the real seed data — the generated @OneToOne crashes at runtime
        with Hibernate's "More than one row with the given identifier was
        found", on every request that touches a Position (the inverse
        @OneToOne on Position defaults to EAGER fetch, so this fires from
        simply listing positions, nowhere near RiskMetric). The belongs_to
        case (Trade belongs_to Position via the same non-unique
        client_name) has the identical flaw — it just hadn't crashed YET
        in that generation because @ManyToOne can stay a lazy, un-queried
        proxy until something actually calls .getPosition(), unlike the
        inverse @OneToOne side. Left in place, it's a landmine for the
        next business-logic method or custom endpoint that touches it.

        Verified empirically against the actual generated seed rows —
        field metadata alone (name/type/required) carries no uniqueness
        information — rather than guessed from naming. Dropping a
        relationship on a false positive (e.g. seed data too small/skewed
        to reveal a real constraint) just means the two entities keep the
        shared column as a plain, independently-fetched field instead of a
        nested object — already the normal case for every one of this
        pipeline's own DTOs, so there's no code path that stops working.
        """
        if not seed_sql:
            return []
        entities_by_name = {e.get("name"): e for e in entities if isinstance(e, dict)}
        corrections = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            rels = entity.get("relationships") or []
            keep = []
            for rel in rels:
                rel_type = rel.get("type") if isinstance(rel, dict) else None
                if rel_type not in ("has_one", "belongs_to"):
                    keep.append(rel)
                    continue
                target_name = rel.get("entity")
                fk_col = rel.get("foreignKey")
                target = entities_by_name.get(target_name)
                if not target or not fk_col:
                    keep.append(rel)
                    continue
                target_table = target.get("table") or target_name
                values = self._seed_column_values(seed_sql, target_table, fk_col)
                if values and len(values) != len(set(values)):
                    note = ""
                    if language == "java":
                        model_path = self._expected_model_path(entity.get("name"), language)
                        source = self.files.get(model_path)
                        if source:
                            cleaned = self._strip_invalid_java_relationship_field(source, target_name)
                            if cleaned is not None:
                                self.files[model_path] = cleaned
                                note = f" ({model_path} cleaned up automatically)"
                            else:
                                note = (f" (WARNING: could not automatically clean up the now-invalid "
                                        f"@ManyToOne/@JoinColumn field in {model_path} — check it manually)")
                    corrections.append(
                        f"{entity.get('name')}'s '{rel_type} {target_name}' via '{fk_col}' is invalid — "
                        f"{target_table}.{fk_col} has duplicate values in the real seed data, so this "
                        f"isn't actually a to-one relationship (it would crash Hibernate at runtime, or is "
                        f"one query away from doing so). Dropped; both entities keep '{fk_col}' as a plain field{note}."
                    )
                    target["relationships"] = [
                        r for r in (target.get("relationships") or [])
                        if not (isinstance(r, dict) and r.get("entity") == entity.get("name")
                                and r.get("foreignKey") == fk_col)
                    ]
                    continue  # drop this relationship — don't add to `keep`
                keep.append(rel)
            entity["relationships"] = keep
        return corrections

    def _entity_fk_map(self, entity: dict) -> dict:
        """{field_name: target_entity_name} for this entity's own FK columns.
        Only "belongs_to" relationships mean THIS entity carries the FK
        column — "has_many"/"has_one" describe the INVERSE side (the OTHER
        entity holds the FK pointing back at this one). Treating every
        foreignKey-bearing relationship as this entity's own, regardless of
        type, misattributed child FKs to their own parents (e.g. Warehouse
        "has_many StockMovement via warehouse_id" was making Warehouse's own
        fixture require a warehouse_id — and, transitively, a circular pytest
        fixture dependency between Warehouse/Product/StockMovement)."""
        fk = {}
        for rel in entity.get("relationships") or []:
            if isinstance(rel, dict) and rel.get("type") == "belongs_to" and rel.get("foreignKey") and rel.get("entity"):
                fk[rel["foreignKey"]] = rel["entity"]
        return fk

    def _entity_resource_keys(self, entity: dict) -> set:
        """Normalized forms (with/without a trailing 's') of an entity's table
        and class name, used to match it against a URL path segment regardless
        of whether the architect wrote a singular or plural form of either."""
        keys = set()
        for raw in (entity.get("table", ""), entity.get("name", "")):
            n = self._norm(raw)
            if n:
                keys.add(n)
                keys.add(n.rstrip("s"))
                keys.add(n + "s")
        return keys

    def _endpoints_for_entity(self, endpoints: list, entity: dict) -> list:
        """
        Assign each architecture endpoint to the one entity whose
        controller/router should implement it, for the per-entity implementation
        call. The first non-version, non-param path segment names the owning
        resource — e.g. /api/v1/customers/{id}/vehicles belongs to Customers,
        even though it returns Vehicle data — matching how a REST framework
        groups routes by primary resource anyway.
        """
        entity_keys = self._entity_resource_keys(entity)
        matched = []
        for ep in endpoints:
            segs = [s for s in self._split_path(ep.get("path", "")) if not self._is_param_seg(s)]
            segs = [s for s in segs if s.lower() != "api" and not re.match(r"^v\d+$", s.lower())]
            if not segs:
                continue
            seg_norm = self._norm(segs[0])
            seg_keys = {seg_norm, seg_norm.rstrip("s"), seg_norm + "s"}
            if seg_keys & entity_keys:
                matched.append(ep)
        return matched

    def _run_custom_endpoint_batch(
        self, ordered_entities: list, all_endpoints: list, architecture_json: str,
        language: str, auth_type: str, rate_limiting_str: str, database: str,
        impl_paths: list, total_stages: int,
    ):
        """
        A custom/join/aggregate endpoint (e.g. GET /api/carrier-performance)
        doesn't belong to any single entity's resource path, so
        _endpoints_for_entity's per-entity matching — used to build each
        entity's own implementation batch — never selects it for ANY of
        them. Left unhandled, it's planned in architecture.endpoints and
        then never implemented at all. Reproduced directly: a real
        generation's architect planned 3 such endpoints, none of which
        existed anywhere in the generated tree. Computes the same matching
        the entity loop already used, then generates exactly the leftovers
        in one dedicated call.
        """
        from .api_prompts import SERVICES_ENGINEER_API_CUSTOM_ENDPOINTS_USER

        matched_ids = set()
        for e in ordered_entities:
            matched_ids |= {id(ep) for ep in self._endpoints_for_entity(all_endpoints, e)}
        unmatched_endpoints = [ep for ep in all_endpoints if id(ep) not in matched_ids]
        if not unmatched_endpoints:
            return

        self._p(f"crew:Stage 3/{total_stages} — Implementing {len(unmatched_endpoints)} "
                 f"custom/cross-entity endpoint(s)...")
        custom_prompt = SERVICES_ENGINEER_API_CUSTOM_ENDPOINTS_USER.format(
            architecture_json=architecture_json,
            shared_contract_files=self._shared_contract_files_text(),
            existing_files_summary=self._files_summary(),
            custom_endpoints_json=json.dumps(unmatched_endpoints, indent=2),
            language=language,
            auth_type=auth_type,
            rate_limiting=rate_limiting_str,
            database=database,
        )
        custom_files: dict = {}
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                custom_result = self._services_agent.generate(custom_prompt, max_tokens=16000, json_mode=True)
                custom_files = self._coerce_files(custom_result.get("files", {}), "Custom endpoints")
                if custom_files:
                    break
            except Exception as e:
                last_err = e
            if attempt == 0:
                self._p(f"skill:Custom endpoints implementation hit an issue, retrying once: {last_err or 'no files returned'}")
        if custom_files:
            if language == "python":
                self._fix_python_low_limit_ceiling(custom_files)
            else:
                self._fix_java_low_limit_ceiling(custom_files)
            self.files.update(custom_files)
            impl_paths.extend(custom_files.keys())
            if language == "python":
                self._wire_python_router(custom_files)
            self._p(f"skill:Custom endpoints implemented — {len(custom_files)} files")
            self._flush_to_disk()
        else:
            # Not a fatal error — every entity's own CRUD still works — but
            # loud, not silent, since this is exactly the class of gap that
            # used to leave a page's data permanently missing with no error
            # anywhere (no request ever fails; the route just never existed).
            self._p(f"skill:WARNING — {len(unmatched_endpoints)} custom endpoint(s) planned in the "
                     f"architecture were never implemented: "
                     f"{', '.join(ep.get('path', '?') for ep in unmatched_endpoints)} "
                     f"({last_err or 'no files returned'})")

    def _wire_python_router(self, entity_files: dict):
        """
        FastAPI, unlike Spring Boot, has no component scan — a router generated
        in its own call is otherwise never registered on `app`. This must be
        deterministic, not left to the call itself, for the same reason the
        security bootstrap append is deterministic: it must work identically
        every generation. The entity prompt only has to export a `router`
        variable at a known path; it never has to invent its own registration
        mechanism. entity_files may contain more than one entity's router when
        entities are implemented in batches rather than one call each — wire
        every router found, not just the first.
        """
        if "src/main.py" not in self.files:
            return
        router_paths = [
            p for p, c in entity_files.items()
            if p.startswith("src/routes/") and re.search(r"\brouter\s*=\s*APIRouter\(", c)
        ]
        for router_path in router_paths:
            module = router_path[:-3].replace("/", ".")
            alias = f"{self._snake(module.rsplit('.', 1)[-1])}_router"
            include_block = f"\nfrom {module} import router as {alias}\napp.include_router({alias})\n"
            if include_block not in self.files["src/main.py"]:
                self.files["src/main.py"] += include_block

    def _db_filename(self) -> str:
        """
        A project-specific default SQLite filename (e.g. "automotive_forecasting.db")
        instead of a generic "app.db" — the Java side already derives its
        own datasource filename from the project rather than a fixed
        literal, and there's no reason the Python side should look more
        generic. Derived once, deterministically, from the project's own
        folder slug — stripping the generator's own "-python-2"/"-java-1"/
        "-api-3" bookkeeping suffix, which isn't part of the actual domain
        name — and reused by BOTH _ensure_python_database_py's fallback and
        _generate_env_example's DATABASE_URL, specifically so the two can
        never independently drift apart the way a freehand LLM-picked name
        in one and a different LLM-picked (or missing) name in the other
        already has, more than once, in real generated projects.
        """
        name = self.project_dir.name if self.project_dir else "app"
        name = re.sub(r"-(?:python|java|api)(?:-\d+)?$", "", name)
        name = re.sub(r"-\d+$", "", name)
        return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "app"

    def _fix_python_typing_mapped_import(self, files: dict):
        """
        Reproduced directly across every model file in a real generation:
        `from typing import Mapped, Optional, List` — Optional/List really
        are in typing, but Mapped (and mapped_column, when also misplaced
        here) are SQLAlchemy 2.0 ORM names, not typing names, so the import
        raises ImportError the moment Python loads the very first model,
        before the app can do anything else — a hard crash at import time
        that took down the entire app, not a single endpoint. Splits the
        one bad import line into two correct ones rather than trusting the
        instruction alone to prevent it (see api_data_architect's role
        text) — same reasoning as every other deterministic fixup here.
        """
        sqlalchemy_orm_names = {"Mapped", "mapped_column"}

        def _split(m: re.Match) -> str:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            orm_names = [n for n in names if n in sqlalchemy_orm_names]
            typing_names = [n for n in names if n not in sqlalchemy_orm_names]
            if not orm_names:
                return m.group(0)
            lines = []
            if typing_names:
                lines.append(f"from typing import {', '.join(typing_names)}")
            lines.append(f"from sqlalchemy.orm import {', '.join(orm_names)}")
            return "\n".join(lines)

        for path, content in list(files.items()):
            if not path.endswith(".py") or "from typing import" not in content:
                continue
            fixed = re.sub(r"from typing import ([^\n(]+)", _split, content)
            if fixed != content:
                files[path] = fixed
                self._p(f"skill:Fixed a wrong 'from typing import Mapped' in {path.split('/')[-1]} "
                        f"— Mapped/mapped_column are SQLAlchemy ORM names, not typing names")
        self._fix_python_hallucinated_mapped_column(files)

    def _fix_python_hallucinated_mapped_column(self, files: dict):
        """
        A separate, deeper hallucination sometimes paired with the wrong
        typing-import above: inventing a fake module path (e.g. `from
        sqlalchemy.typing import Mapped as MappedType`) and using that
        alias as if it were mapped_column — `MappedType[int](primary_
        key=True)` — both subscripted AND called, which is valid syntax
        for neither Mapped (a type annotation only, never called) nor
        mapped_column (never subscripted). Reproduced directly on every
        single column of every model in one real generation. Strip the
        bogus import and rewrite every `<alias>[...](` call site to the
        real mapped_column(...), adding that import to sqlalchemy.orm if
        it isn't already there.
        """
        for path, content in list(files.items()):
            if not path.endswith(".py"):
                continue
            m = re.search(r"from\s+sqlalchemy(?:\.\w+)*\s+import\s+Mapped\s+as\s+(\w+)\n", content)
            if not m:
                continue
            alias = m.group(1)
            fixed = content.replace(m.group(0), "")
            # [^\]]* alone can't span a nested bracket group (e.g.
            # MappedType[Optional[str]](...) — reproduced directly, the
            # same file's "sector" column), so allow one level of nested
            # [...] explicitly instead of just excluding "]" outright.
            fixed = re.sub(
                rf"\b{re.escape(alias)}\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(",
                "mapped_column(",
                fixed,
            )
            orm_import = re.search(r"^from sqlalchemy\.orm import (.+)$", fixed, re.MULTILINE)
            if orm_import and "mapped_column" not in orm_import.group(1):
                fixed = fixed[:orm_import.start()] + orm_import.group(0) + ", mapped_column" + fixed[orm_import.end():]
            elif not orm_import:
                fixed = "from sqlalchemy.orm import mapped_column\n" + fixed
            if fixed != content:
                files[path] = fixed
                self._p(f"skill:Fixed a hallucinated '{alias}[...](...)' column-definition pattern in "
                        f"{path.split('/')[-1]} — rewritten to the real mapped_column(...)")

    def _fix_python_low_limit_ceiling(self, files: dict):
        """
        The frontend's shared useApi hook defaults to limit=500 — but
        several shared page templates (DataGrid, DetailPage, and both map
        skills) bypass that default entirely and explicitly request
        limit=1000 to fetch a table's full contents in one call. 500 was
        reproduced directly as NOT actually enough: a route with
        `le=500` looks fine by the hook's own default, but 422s the
        instant a DataGrid/DetailPage/map page calls it with limit=1000,
        since none of these page templates are visible to (or overridable
        by) the backend-generation call that picks this ceiling. 1000 is
        the one value every caller in this platform can safely use, so
        that's the floor every route must meet — never lowers one that's
        already >= 1000.
        """
        def _raise_ceiling(m: re.Match) -> str:
            return m.group(0) if int(m.group(1)) >= 1000 else "le=1000)"

        for path, content in list(files.items()):
            if not path.endswith(".py"):
                continue
            fixed = re.sub(r"le=(\d+)\)", _raise_ceiling, content)
            if fixed != content:
                files[path] = fixed
                self._p(f"skill:Raised a low 'limit' query-param ceiling in {path.split('/')[-1]} "
                        f"to 1000 — some page templates request limit=1000 directly, and anything "
                        f"lower than that gets a 422 rejected before the endpoint even runs")

    def _fix_python_zero_indexed_page_param(self, files: dict):
        """
        Some Python route generations invent their own 1-indexed `page`
        query param (`Query(1, ge=1)`, offset computed as `(page - 1) *
        limit`) instead of this platform's own `limit`/`offset` convention.
        Java's Spring Data convention is 0-indexed (page=0 is the first
        page), which is what the frontend's useApi hook always sends for
        Java compatibility (_withJavaPaginationAliases) — regardless of
        which backend language actually receives the request, since the
        hook has no way to know that in advance. Reproduced directly: a
        Python route's own `page: Query(1, ge=1)` rejected the frontend's
        `page=0` outright with a 422 before the route even ran, even though
        the same request's `limit` was perfectly valid — every page
        depending on that endpoint showed no data at all, with no error
        visible anywhere except the network tab.

        Rather than assume every future generation invents this exact
        scheme (or none at all), make ANY page number >= 0 safe: widen the
        validation floor from 1 to 0, and clamp the `page - 1` subtraction
        to never go negative — so page=0 (0-indexed, what Java-style callers
        send) and page=1 (1-indexed, this route's own native convention)
        both resolve to offset 0, "first page", whichever convention a
        given caller happens to use.
        """
        for path, content in list(files.items()):
            if not path.endswith(".py"):
                continue
            fixed = re.sub(r"(page:\s*int\s*=\s*Query\(\d+,\s*ge=)1(\))", r"\g<1>0\2", content)
            fixed = re.sub(r"\(page\s*-\s*1\)(\s*\*\s*limit)", r"max(page - 1, 0)\1", fixed)
            if fixed != content:
                files[path] = fixed
                self._p(f"skill:Widened a 1-indexed 'page' param's floor in {path.split('/')[-1]} "
                        f"and clamped its offset math — a page=0 request (0-indexed, what "
                        f"Java-style callers send) was previously rejected outright by this "
                        f"route's own ge=1 validation before it ever ran")

    def _fix_java_low_limit_ceiling(self, files: dict):
        """
        Java analogue of _fix_python_low_limit_ceiling — same root problem,
        worse failure mode. Java controllers commonly clamp an out-of-range
        page size instead of rejecting it outright (e.g.
        `PageRequest.of(page, Math.min(Math.max(size, 1), 200))`), so a
        frontend page requesting limit=1000 against a `200` ceiling doesn't
        even get an error — it just silently gets back 200 rows instead of
        the full table, which is easy to miss entirely (unlike Python's
        loud 422). Raises any `Math.min(Math.max(<var>, 1), N)`-shaped
        ceiling below 1000 up to 1000; never lowers one already >= 1000.
        """
        def _raise_ceiling(m: re.Match) -> str:
            return m.group(0) if int(m.group(2)) >= 1000 else f"{m.group(1)}1000{m.group(3)}"

        pattern = re.compile(r"(Math\.min\(Math\.max\([^,]+,\s*1\),\s*)(\d+)(\))")
        for path, content in list(files.items()):
            if not path.endswith(".java"):
                continue
            fixed = pattern.sub(_raise_ceiling, content)
            if fixed != content:
                files[path] = fixed
                self._p(f"skill:Raised a low page-size ceiling in {path.split('/')[-1]} to 1000 — "
                        f"some page templates request limit=1000 directly, and a lower ceiling "
                        f"silently truncates the result instead of erroring, which is easy to miss")

    def _ensure_python_database_py(self, database: str):
        """
        src/database.py is freehand LLM output from the bootstrap call, and
        it keeps coming back wrong in a different specific way each time —
        reproduced now across three separate generated projects: (1)
        Base.metadata.create_all() never called at all; (2) DATABASE_URL
        hardcoded as a literal string (e.g. "sqlite:///./automotive_forecasting.db")
        instead of read from the environment, silently ignoring whatever
        .env (itself already deterministically generated — see
        _generate_env_example) actually says; (3) both at once, in the same
        file. The boot-check repair loop exists as a safety net for
        genuinely novel bugs, not to regenerate the same handful of known-
        correct lines a fourth time — and it isn't even reliable here: a
        boot-check failure only triggers repair if the traceback text it
        captured still contains a recognizable exception marker by the time
        the (bounded) log tail is read, which isn't guaranteed. This file's
        correct shape never varies by project — only the dialect and which
        models exist, both already known by the time bootstrap finishes —
        so write it ourselves instead of trusting a fresh completion to
        reproduce it byte-correct every single time, the same reasoning
        _wire_python_router and _wire_python_models_init already apply to
        the other two structurally-fixed pieces of this same app.
        """
        pragma_block = (
            "@event.listens_for(engine, \"connect\")\n"
            "def _set_sqlite_pragma(dbapi_connection, connection_record):\n"
            "    if not DATABASE_URL.startswith(\"sqlite\"):\n"
            "        return\n"
            "    cursor = dbapi_connection.cursor()\n"
            "    cursor.execute(\"PRAGMA foreign_keys=ON\")\n"
            "    cursor.close()\n"
        )
        content = (
            "import os\n\n"
            "from sqlalchemy import create_engine, event\n"
            "from sqlalchemy.orm import DeclarativeBase, sessionmaker\n\n"
            f"DATABASE_URL = os.getenv(\"DATABASE_URL\", \"sqlite:///./{self._db_filename()}.db\")\n\n"
            "# Single source of truth for every list route's page-size ceiling —\n"
            "# see MAX_PAGE_SIZE in .env for why this must be read from the\n"
            "# environment (and imported here) rather than each route picking its\n"
            "# own literal independently.\n"
            "MAX_PAGE_SIZE = int(os.getenv(\"MAX_PAGE_SIZE\", \"1000\"))\n\n"
            "engine = create_engine(\n"
            "    DATABASE_URL,\n"
            "    connect_args={\"check_same_thread\": False} if DATABASE_URL.startswith(\"sqlite\") else {},\n"
            ")\n\n\n"
            f"{pragma_block}\n\n"
            "SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)\n\n\n"
            "class Base(DeclarativeBase):\n"
            "    pass\n\n\n"
            "def get_db():\n"
            "    db = SessionLocal()\n"
            "    try:\n"
            "        yield db\n"
            "    finally:\n"
            "        db.close()\n\n\n"
            "import src.models  # noqa: E402,F401  ensure all models are registered before create_all\n\n"
            "Base.metadata.create_all(bind=engine)\n"
        )
        self.files["src/database.py"] = content
        self._p("skill:Deterministically wrote src/database.py (DATABASE_URL read from the environment, "
                 "create_all wired) — not left to the bootstrap call's own freehand output")

    # A model file importing `Base` from anything other than src.database
    # (e.g. a self-authored `from src.models.base import Base`) registers
    # its table against a DIFFERENT declarative base's metadata — one
    # database.py's own `Base.metadata.create_all(bind=engine)` never sees.
    # See _wire_python_models_init's docstring for the full failure mode;
    # this is a sibling cause of the exact same silent symptom.
    _MODEL_BASE_IMPORT_RE = re.compile(r"^from\s+(?!src\.database\b)\S+\s+import\s+Base\s*$", re.MULTILINE)

    def _wire_python_models_init(self):
        """
        Deterministically guarantees every generated model's table actually
        gets created — two independent, silent failure modes converge on
        the identical symptom (a real .db file with some or all tables
        missing, zero errors until the first request hits "no such table"),
        so both are fixed here together:

        1. database.py's own mandatory `import src.models` line (see the
           create_all rule in api_data_architect's role) only registers a
           model class on Base.metadata if src/models/__init__.py actually
           imports that model's module — reproduced directly: database.py
           had a completely correct create_all(bind=engine) call, but
           src/models/__init__.py was left blank (the LLM's default when
           nothing tells it otherwise), so `import src.models` was a silent
           no-op. Base.metadata was empty, create_all() ran without error
           and created a real .db file, but with ZERO tables in it.

        2. A model file importing `Base` from somewhere other than
           src.database — typically a self-authored `src/models/base.py`
           with its own `Base = declarative_base()` — registers its table
           against a COMPLETELY DIFFERENT metadata object, one
           database.py's create_all() never touches. Reproduced directly:
           3 models existed, all 3 correctly imported by __init__.py, but
           only 1 (the one importing Base from src.database) got a real
           table — the other 2 imported Base from a stray models/base.py
           instead, so create_all() silently never saw them. Per-file, not
           per-app: different model-generation batches (different LLM
           calls) made different, uncoordinated assumptions about where
           Base lives, since nothing told them to always use the one
           database.py already defines.

        Neither is left to whichever model-generation batch happened to run
        last, for the same reason _wire_python_router is deterministic: it
        must see every model file that exists, from every batch, every time.
        """
        model_paths = sorted(
            p for p in self.files
            if p.startswith("src/models/") and p.endswith(".py") and not p.endswith("__init__.py")
        )
        if not model_paths:
            return

        for p in model_paths:
            content = self.files[p]
            fixed = self._MODEL_BASE_IMPORT_RE.sub("from src.database import Base", content)
            if fixed != content:
                self.files[p] = fixed
                self._p(f"skill:Fixed {p} to import Base from src.database — it was importing a "
                        f"separate declarative base whose metadata database.py's create_all() never "
                        f"sees, so this model's table would have silently never been created")

        lines = [f"import src.models.{p[len('src/models/'):-3].replace('/', '.')}  # noqa: F401"
                 for p in model_paths]
        self.files["src/models/__init__.py"] = "\n".join(lines) + "\n"

    @staticmethod
    def _first_enum_option(description: str) -> str | None:
        """Best-effort: the architecture schema has no structured enum field,
        but the architect LLM's free-text description routinely spells one
        out anyway (e.g. "Movement reason: purchase, sale, adjustment, or
        transfer") — a generic "test" placeholder for a field like that fails
        the real implementation's own validation, which very likely DOES
        enforce the enum. Only fires on ≥2 short comma/or-separated tokens, to
        avoid misfiring on ordinary prose descriptions."""
        import re as _re
        if not description:
            return None
        tail = description.split(":", 1)[-1] if ":" in description else description
        tail = _re.sub(r"\bor\b", ",", tail)
        parts = [p.strip().strip(".") for p in tail.split(",")]
        parts = [p for p in parts if p and _re.match(r"^[a-zA-Z_-]{2,20}$", p)]
        return parts[0] if len(parts) >= 2 else None

    def _sample_value(self, field_name: str, field_type: str, description: str = ""):
        """A deterministic placeholder for one field, keyed off its declared
        type and a few common name patterns — no LLM, no invented examples."""
        t = (field_type or "string").lower()
        name = (field_name or "").lower()
        if t == "boolean":
            return True
        if t == "integer":
            return 1
        if t in ("float", "number", "decimal"):
            return 9.99
        if t == "datetime":
            return "2026-01-01T00:00:00Z"
        if t == "uuid":
            return None  # server-generated — never sent in a create payload
        enum_guess = self._first_enum_option(description)
        if enum_guess and t == "string":
            return enum_guess
        if "email" in name:
            # Marker, not a literal — a static "test@example.com" would collide
            # on any second test run against the same persisted SQLite file if
            # this field happens to carry a uniqueness constraint (the
            # architecture schema has no explicit "unique" flag to check, so
            # this is deliberately generous: harmless if the field isn't
            # actually unique, avoids a real collision if it is). Swapped for
            # a real runtime-random expression when the payload is rendered
            # into source (see _RANDOM_EMAIL_MARKER usages below).
            return f"{self._RANDOM_EMAIL_MARKER}{field_name}"
        if "sku" in name or "code" in name:
            # Same reasoning as the email case above — sku/code fields are
            # the most likely of all to carry a real uniqueness constraint.
            return f"{self._RANDOM_CODE_MARKER}{field_name}"
        if "location" in name or "address" in name:
            return "Test Location"
        if "name" in name or "title" in name:
            return "Test Name"
        return "test"

    def _build_payload(self, entity: dict, fk_map: dict, fixture_of) -> dict:
        """Build a create-payload dict for one entity. FK fields resolve to
        `fixture_of(target_entity)` — a caller-supplied lookup so Python can
        use pytest fixture references and Java can use already-created ids."""
        payload = {}
        fields = [f for f in (entity.get("fields") or []) if isinstance(f, dict)]
        seen = set()
        for f in fields:
            fname = f.get("name")
            if not fname or fname.lower() in self._SKIP_PAYLOAD_FIELDS:
                continue
            seen.add(fname)
            if fname in fk_map:
                payload[fname] = fixture_of(fk_map[fname])
                continue
            val = self._sample_value(fname, f.get("type"), f.get("description", ""))
            if val is not None:
                payload[fname] = val
        # FK columns the architect only mentioned via relationships, not in
        # `fields` — still needed for the create call to satisfy the real
        # schema's foreign key constraint.
        for fk_field, target in fk_map.items():
            if fk_field not in seen and fk_field.lower() not in self._SKIP_PAYLOAD_FIELDS:
                payload[fk_field] = fixture_of(target)
        return payload

    def _required_field_to_omit(self, entity: dict, fk_map: dict) -> str | None:
        for f in entity.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fname = f.get("name", "")
            if f.get("required") and fname.lower() not in self._SKIP_PAYLOAD_FIELDS and fname not in fk_map:
                return fname
        return None

    def _id_field_type(self, entity: dict) -> str:
        for f in entity.get("fields") or []:
            if isinstance(f, dict) and f.get("name", "").lower() == "id":
                return (f.get("type") or "uuid").lower()
        return "uuid"

    def _crud_paths_for_entity(self, entity: dict, endpoints: list) -> dict:
        """Match this entity to its list/create/get/update/delete paths by
        exact path SHAPE (segment count + which segments are {params}), not
        just substring — so /products/{id}/stock-by-warehouse (an extra
        segment past {id}) correctly falls through as a custom endpoint
        instead of being mistaken for the plain get-by-id route."""
        table_norm = self._norm(entity.get("table") or entity.get("name") or "")
        candidates = []
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            segs = self._split_path(ep.get("path", ""))
            if not segs:
                continue
            # Find this entity's collection segment — the first non-param
            # segment whose normalized text matches the table/entity name.
            coll_idx = next((i for i, s in enumerate(segs) if not self._is_param_seg(s) and self._norm(s) == table_norm), None)
            if coll_idx is None:
                continue
            candidates.append((ep, segs, coll_idx))
        if not candidates:
            return {}

        result = {"list": None, "create": None, "get": None, "update": None, "delete": None, "matched": set()}
        for ep, segs, coll_idx in candidates:
            method = (ep.get("method") or "GET").upper()
            trailing = segs[coll_idx + 1:]
            is_collection_shape = coll_idx == len(segs) - 1
            is_item_shape = len(trailing) == 1 and self._is_param_seg(trailing[0])
            if is_collection_shape and method == "GET":
                result["list"] = ep
            elif is_collection_shape and method == "POST":
                result["create"] = ep
            elif is_item_shape and method == "GET":
                result["get"] = ep
            elif is_item_shape and method in ("PUT", "PATCH"):
                result["update"] = ep
            elif is_item_shape and method == "DELETE":
                result["delete"] = ep
            else:
                continue
            result["matched"].add(id(ep))
        return result

    def _generate_tests(self, architecture: dict, language: str, auth_type: str, rate_limit) -> dict:
        entities = [e for e in (architecture.get("entities") or []) if isinstance(e, dict)]
        endpoints = [e for e in (architecture.get("endpoints") or []) if isinstance(e, dict)]
        if language == "java":
            return self._generate_java_tests(entities, endpoints, auth_type, rate_limit)
        return self._generate_python_tests(entities, endpoints, auth_type, rate_limit)

    def _substitute_python_random_markers(self, payload_src: str) -> str:
        """Swap _RANDOM_EMAIL_MARKER/_RANDOM_CODE_MARKER placeholders (quoted
        strings from json.dumps) for real Python expressions that generate a
        fresh random value at test-run time — a static literal would collide
        with a same-value row left over from an earlier run of the same
        suite against the same persisted SQLite file."""
        import re as _re

        payload_src = _re.sub(
            rf'"{self._RANDOM_EMAIL_MARKER}(\w+)"',
            'f"test-{uuid.uuid4().hex[:8]}@example.com"',
            payload_src,
        )
        payload_src = _re.sub(
            rf'"{self._RANDOM_CODE_MARKER}(\w+)"',
            lambda m: f'f"TEST-{m.group(1).upper()}-{{uuid.uuid4().hex[:8]}}"',
            payload_src,
        )
        return payload_src

    def _generate_python_tests(self, entities: list, endpoints: list, auth_type: str, rate_limit) -> dict:
        import json as _json

        files = {}
        crud_by_entity = {e.get("name", f"Entity{i}"): self._crud_paths_for_entity(e, endpoints) for i, e in enumerate(entities)}
        fk_by_entity = {e.get("name", f"Entity{i}"): self._entity_fk_map(e) for i, e in enumerate(entities)}
        entity_by_name = {e.get("name", f"Entity{i}"): e for i, e in enumerate(entities)}

        matched_ep_ids = set()
        for c in crud_by_entity.values():
            matched_ep_ids |= c.get("matched", set())
        custom_endpoints = [ep for ep in endpoints if id(ep) not in matched_ep_ids]

        # ── conftest.py — client/auth fixtures + one create-fixture per
        # entity that has a create endpoint, wired to its FK dependencies via
        # plain pytest fixture parameters (pytest resolves the dependency
        # order itself; no topological sort needed on this side).
        conftest = ['"""',
            "Deterministic test fixtures, generated directly from the API's architecture",
            "document (entities + endpoints) — not LLM-authored. Sample values come from",
            "each field's declared type; fixtures are created for real via the API itself",
            "(in FK dependency order, resolved automatically by pytest) so foreign-key",
            "fields always reference real rows instead of guessed IDs.",
            '"""',
            "import base64",
            "import os",
            "",
            "import pytest",
            "from dotenv import load_dotenv",
            "from fastapi.testclient import TestClient",
            "",
            "load_dotenv()",
            "",
            "from src.main import app",
            "",
            'AUTH_TYPE = os.environ.get("API_AUTH_TYPE", "none")',
            "",
            "",
            "@pytest.fixture(scope=\"session\")",
            "def client():",
            "    return TestClient(app)",
            "",
            "",
            "@pytest.fixture(scope=\"session\")",
            "def auth_headers():",
            '    if AUTH_TYPE != "basic":',
            "        return {}",
            '    username = os.environ.get("API_BASIC_AUTH_USERNAME", "admin")',
            '    password = os.environ.get("API_BASIC_AUTH_PASSWORD", "changeme")',
            '    token = base64.b64encode(f"{username}:{password}".encode()).decode()',
            '    return {"Authorization": f"Basic {token}"}',
            "",
            "",
            "def extract_id(body):",
            '    """Response envelopes vary by generation (bare object vs {"data": {...}})',
            "    — find the first dict with an 'id' key rather than assuming one fixed shape.\"\"\"",
            "    if isinstance(body, dict):",
            '        if "id" in body:',
            '            return body["id"]',
            "        for v in body.values():",
            "            found = extract_id(v)",
            "            if found is not None:",
            "                return found",
            "    return None",
            "",
        ]

        def fixture_ref(entity_name: str) -> str:
            return f"__FIXTURE__{self._snake(entity_name)}"

        conftest.insert(conftest.index("import base64") + 1, "import uuid")

        for name, entity in entity_by_name.items():
            crud = crud_by_entity[name]
            create_ep = crud.get("create")
            if not create_ep:
                continue
            snake = self._snake(name)
            fk_map = fk_by_entity[name]
            dep_params = sorted({self._snake(t) for t in fk_map.values() if crud_by_entity.get(t, {}).get("create")})
            payload = self._build_payload(entity, fk_map, fixture_ref)
            payload_src = _json.dumps(payload, indent=8)
            # Swap the fixture-ref markers for real Python identifiers (json.dumps
            # quoted them as strings since it doesn't know they're code).
            for t in fk_map.values():
                marker = f'"{fixture_ref(t)}"'
                payload_src = payload_src.replace(marker, self._snake(t))
            payload_src = self._substitute_python_random_markers(payload_src)
            sig = ", ".join(["client", "auth_headers"] + dep_params)
            conftest += [
                "",
                "@pytest.fixture",
                f"def {snake}({sig}):",
                f'    payload = {payload_src}',
                f'    resp = client.post("{create_ep["path"]}", json=payload, headers=auth_headers)',
                f'    assert resp.status_code in (200, 201), f"Failed to create fixture {name}: {{resp.text}}"',
                "    return extract_id(resp.json())",
            ]
        files["tests/conftest.py"] = "\n".join(conftest) + "\n"

        # ── test_health.py — always present (the /health route itself is
        # deterministic, added by security_bootstrap.py regardless of auth).
        files["tests/test_health.py"] = "\n".join([
            "def test_health_check(client):",
            '    resp = client.get("/health")',
            "    assert resp.status_code == 200",
            "",
        ]) + "\n"

        # ── test_auth.py — one unauthenticated-request check, using the
        # first protected endpoint found (any GET collection endpoint).
        if auth_type == "basic":
            first_protected = next((ep for ep in endpoints if (ep.get("method") or "GET").upper() == "GET"), None)
            if first_protected:
                files["tests/test_auth.py"] = "\n".join([
                    "def test_unauthenticated_request_is_rejected(client):",
                    f'    resp = client.get("{first_protected["path"]}")',
                    "    assert resp.status_code == 401",
                    "",
                    "",
                    "def test_wrong_credentials_are_rejected(client):",
                    "    import base64",
                    '    token = base64.b64encode(b"wrong:creds").decode()',
                    f'    resp = client.get("{first_protected["path"]}", headers={{"Authorization": f"Basic {{token}}"}})',
                    "    assert resp.status_code == 401",
                    "",
                    "",
                    "def test_correct_credentials_are_accepted(client, auth_headers):",
                    f'    resp = client.get("{first_protected["path"]}", headers=auth_headers)',
                    "    assert resp.status_code == 200",
                    "",
                ]) + "\n"

        # ── test_rate_limit.py — best-effort: fire past the limit on the
        # cheapest endpoint available and expect at least one 429.
        try:
            rl = int(rate_limit)
        except (TypeError, ValueError):
            rl = 0
        if rl > 0:
            # Prefer a plain GET collection endpoint (cheap, no side effects if
            # hammered repeatedly); fall back to any GET, then to anything at all.
            gets = [ep for ep in endpoints if (ep.get("method") or "GET").upper() == "GET"]
            any_get = next((ep for ep in gets if not any(self._is_param_seg(s) for s in self._split_path(ep["path"]))), None)
            any_get = any_get or (gets[0] if gets else None) or (endpoints[0] if endpoints else None)
            if any_get:
                # "zzz" prefix keeps this file collected dead last by pytest's
                # default alphabetical order — rate limiting is keyed by
                # username (see client_id.py) when auth is basic, and there's
                # only ever one valid username, so this test's own deliberate
                # overload would otherwise poison every other test's shared
                # rate-limit bucket for the rest of the session if it ran
                # first. Re-running the suite again inside the same
                # rate-limit window will still see this same interaction —
                # an inherent limitation of testing rate-limiting against a
                # single shared identity, not something file ordering fully
                # solves, just the common case of running the suite once.
                files["tests/test_zzz_rate_limit.py"] = "\n".join([
                    "def test_exceeding_rate_limit_returns_429(client, auth_headers):",
                    f'    path = "{any_get["path"]}"',
                    f"    statuses = [client.get(path, headers=auth_headers).status_code for _ in range({rl + 5})]",
                    "    assert 429 in statuses, f\"Expected a 429 after exceeding the rate limit, got: {statuses}\"",
                    "",
                ]) + "\n"

        # ── per-entity CRUD test files ───────────────────────────────────────
        def item_path(ep_path: str, replacement) -> str:
            """Replace an item endpoint's single trailing {param} segment with
            `replacement` (either an f-string placeholder like '{product}' or
            a literal dummy value) — whatever the param's own name happens to
            be, since the architecture doesn't always call it {id}."""
            segs = self._split_path(ep_path)
            new_segs = [str(replacement) if self._is_param_seg(s) else s for s in segs]
            return "/" + "/".join(new_segs)

        for name, entity in entity_by_name.items():
            crud = crud_by_entity[name]
            snake = self._snake(name)
            fk_map = fk_by_entity[name]
            lines = []
            has_any = False
            not_found_id = 999999999 if self._id_field_type(entity) == "integer" else "00000000-0000-0000-0000-000000000000"

            if crud.get("create"):
                has_any = True
                dep_params = sorted({self._snake(t) for t in fk_map.values() if crud_by_entity.get(t, {}).get("create")})
                payload = self._build_payload(entity, fk_map, fixture_ref)
                payload_src = _json.dumps(payload, indent=4)
                for t in fk_map.values():
                    marker = f'"{fixture_ref(t)}"'
                    payload_src = payload_src.replace(marker, self._snake(t))
                payload_src = self._substitute_python_random_markers(payload_src)
                sig = ", ".join(["client", "auth_headers"] + dep_params)
                lines += [
                    f"def test_create_{snake}_happy_path({sig}):",
                    f"    payload = {payload_src}",
                    f'    resp = client.post("{crud["create"]["path"]}", json=payload, headers=auth_headers)',
                    "    assert resp.status_code in (200, 201)",
                    "",
                    "",
                ]
                omit = self._required_field_to_omit(entity, fk_map)
                if omit:
                    lines += [
                        f"def test_create_{snake}_missing_required_field({sig}):",
                        f"    payload = {payload_src}",
                        f'    del payload["{omit}"]',
                        f'    resp = client.post("{crud["create"]["path"]}", json=payload, headers=auth_headers)',
                        "    assert resp.status_code in (400, 422)",
                        "",
                        "",
                    ]

            if crud.get("list"):
                has_any = True
                lines += [
                    f"def test_list_{snake}(client, auth_headers):",
                    f'    resp = client.get("{crud["list"]["path"]}", headers=auth_headers)',
                    "    assert resp.status_code == 200",
                    "",
                    "",
                ]

            if crud.get("get") and crud.get("create"):
                has_any = True
                get_path_ok = item_path(crud["get"]["path"], "{" + snake + "}")
                get_path_404 = item_path(crud["get"]["path"], not_found_id)
                lines += [
                    f"def test_get_{snake}_by_id(client, auth_headers, {snake}):",
                    f'    resp = client.get(f"{get_path_ok}", headers=auth_headers)',
                    "    assert resp.status_code == 200",
                    "",
                    "",
                    f"def test_get_{snake}_not_found(client, auth_headers):",
                    f'    resp = client.get("{get_path_404}", headers=auth_headers)',
                    "    assert resp.status_code == 404",
                    "",
                    "",
                ]

            if crud.get("delete") and crud.get("create"):
                has_any = True
                delete_path_ok = item_path(crud["delete"]["path"], "{" + snake + "}")
                lines += [
                    f"def test_delete_{snake}(client, auth_headers, {snake}):",
                    f'    resp = client.delete(f"{delete_path_ok}", headers=auth_headers)',
                    "    assert resp.status_code in (200, 204)",
                    "",
                ]

            if has_any:
                header = f'"""Deterministic tests for {name}, generated from the architecture document."""\nimport uuid\n\n'
                files[f"tests/test_{snake}.py"] = header + "\n".join(lines).rstrip() + "\n"

        # ── smoke tests for anything that didn't match a standard CRUD shape ─
        if custom_endpoints:
            lines = ['"""Smoke tests for endpoints that don\'t match plain CRUD shape — best-effort:', "just confirms they don't error out (< 500), not full business-rule coverage.\"\"\"", ""]
            for i, ep in enumerate(custom_endpoints):
                method = (ep.get("method") or "GET").upper()
                path = ep.get("path", "")
                resolved = path
                for seg in self._split_path(path):
                    if self._is_param_seg(seg):
                        resolved = resolved.replace(seg, "00000000-0000-0000-0000-000000000000", 1)
                py_method = method.lower()
                lines += [
                    f"def test_custom_endpoint_{i}_{py_method}_does_not_error(client, auth_headers):",
                    f'    resp = client.{py_method}("{resolved}", headers=auth_headers)' if method in ("GET", "DELETE") else
                    f'    resp = client.{py_method}("{resolved}", json={{}}, headers=auth_headers)',
                    "    assert resp.status_code < 500",
                    "",
                    "",
                ]
            files["tests/test_custom_endpoints.py"] = "\n".join(lines).rstrip() + "\n"

        files["pytest.ini"] = "[pytest]\ntestpaths = tests\n"
        return files

    def _topo_order_entities(self, entities: list, fk_by_entity: dict) -> list:
        """Parent entities before children, by FK dependency. Only needed for
        Java — pytest resolves fixture dependency order automatically via
        function parameters, but JUnit fixture-creation helpers are plain
        static methods that must be emitted (and call each other) in order."""
        by_name = {e.get("name"): e for e in entities}
        ordered, seen = [], set()

        def visit(name, stack):
            if name in seen or name not in by_name or name in stack:
                return
            for target in fk_by_entity.get(name, {}).values():
                visit(target, stack | {name})
            seen.add(name)
            ordered.append(by_name[name])

        for e in entities:
            visit(e.get("name"), set())
        return ordered

    @staticmethod
    def _java_literal(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _generate_java_tests(self, entities: list, endpoints: list, auth_type: str, rate_limit) -> dict:
        """
        Same coverage and same field-name assumptions as the Python generator
        (create/list/get/update/delete + validation + not-found + auth +
        rate-limit + custom-endpoint smoke tests), built from the architecture
        document instead of an LLM. One real gap unique to Java: the Services
        Engineer stage may not always spell a field the same way the architect
        did (e.g. JSON property "productId" vs the architecture's declared
        "product_id") since Jackson's default naming isn't enforced by prompt
        — same best-effort tradeoff as the existing table/path-name heuristics
        elsewhere in this file, not a guarantee.
        """
        files = {}
        crud_by_entity = {e.get("name", f"Entity{i}"): self._crud_paths_for_entity(e, endpoints) for i, e in enumerate(entities)}
        fk_by_entity = {e.get("name", f"Entity{i}"): self._entity_fk_map(e) for i, e in enumerate(entities)}
        entity_by_name = {e.get("name", f"Entity{i}"): e for i, e in enumerate(entities)}
        ordered_entities = self._topo_order_entities(entities, fk_by_entity)

        matched_ep_ids = set()
        for c in crud_by_entity.values():
            matched_ep_ids |= c.get("matched", set())
        custom_endpoints = [ep for ep in endpoints if id(ep) not in matched_ep_ids]

        def java_body_lines(entity: dict, fk_map: dict, var_name: str) -> list:
            def fixture_of(target_entity):
                return f"__VAR__{self._snake(target_entity)}Id"
            payload = self._build_payload(entity, fk_map, fixture_of)
            lines = [f"Map<String, Object> {var_name} = new LinkedHashMap<>();"]
            for k, v in payload.items():
                if isinstance(v, str) and v.startswith("__VAR__"):
                    lines.append(f'{var_name}.put("{k}", {v[len("__VAR__"):]});')
                elif isinstance(v, str) and v.startswith(self._RANDOM_EMAIL_MARKER):
                    # A static literal would collide with a same-value row left
                    # over from an earlier run of the same suite against the
                    # same persisted SQLite file if this field turns out to be
                    # uniqueness-constrained (the architecture schema has no
                    # explicit "unique" flag to check either way).
                    lines.append(f'{var_name}.put("{k}", "test-" + java.util.UUID.randomUUID().toString().substring(0, 8) + "@example.com");')
                elif isinstance(v, str) and v.startswith(self._RANDOM_CODE_MARKER):
                    field_upper = v[len(self._RANDOM_CODE_MARKER):].upper()
                    lines.append(f'{var_name}.put("{k}", "TEST-{field_upper}-" + java.util.UUID.randomUUID().toString().substring(0, 8));')
                else:
                    lines.append(f'{var_name}.put("{k}", {self._java_literal(v)});')
            return lines

        # ── TestFixtures.java — static create-helpers, parent entities first ──
        fixtures_lines = [
            "package com.api;",
            "",
            "import org.springframework.boot.test.web.client.TestRestTemplate;",
            "import org.springframework.http.HttpEntity;",
            "import org.springframework.http.HttpHeaders;",
            "import org.springframework.http.ResponseEntity;",
            "",
            "import java.util.LinkedHashMap;",
            "import java.util.Map;",
            "",
            "/**",
            " * Deterministic fixture creation, generated from the architecture document —",
            " * creates real rows via the API itself (in FK dependency order) instead of",
            " * guessing IDs, so tests exercise real foreign-key relationships.",
            " */",
            "public class TestFixtures {",
            "",
            "    @SuppressWarnings(\"unchecked\")",
            "    public static Object extractId(Object body) {",
            "        if (body instanceof Map) {",
            "            Map<String, Object> map = (Map<String, Object>) body;",
            '            if (map.containsKey("id")) return map.get("id");',
            "            for (Object v : map.values()) {",
            "                Object found = extractId(v);",
            "                if (found != null) return found;",
            "            }",
            "        }",
            "        return null;",
            "    }",
        ]
        for entity in ordered_entities:
            name = entity.get("name", "Entity")
            crud = crud_by_entity[name]
            if not crud.get("create"):
                continue
            snake = self._snake(name)
            fk_map = fk_by_entity[name]
            fixtures_lines += ["", f"    public static String create{name}(TestRestTemplate restTemplate, HttpHeaders headers) {{"]
            for target in {t for t in fk_map.values() if crud_by_entity.get(t, {}).get("create")}:
                fixtures_lines.append(f"        String {self._snake(target)}Id = create{target}(restTemplate, headers);")
            for line in java_body_lines(entity, fk_map, "body"):
                fixtures_lines.append(f"        {line}")
            fixtures_lines += [
                f'        ResponseEntity<Map> resp = restTemplate.postForEntity("{crud["create"]["path"]}", new HttpEntity<>(body, headers), Map.class);',
                "        return String.valueOf(extractId(resp.getBody()));",
                "    }",
            ]
        fixtures_lines.append("}")
        files["src/test/java/com/api/TestFixtures.java"] = "\n".join(fixtures_lines) + "\n"

        # ── BaseApiTest.java — shared Spring context + auth header builder ────
        files["src/test/java/com/api/BaseApiTest.java"] = "\n".join([
            "package com.api;",
            "",
            "import org.springframework.beans.factory.annotation.Autowired;",
            "import org.springframework.boot.test.context.SpringBootTest;",
            "import org.springframework.boot.test.web.client.TestRestTemplate;",
            "import org.springframework.http.HttpHeaders;",
            "",
            "import java.util.Base64;",
            "",
            "/**",
            " * Deterministic API tests, generated from the architecture document — not",
            " * LLM-authored. No explicit `classes=` on @SpringBootTest: Spring Boot",
            " * auto-detects the @SpringBootApplication class via classpath scanning, so",
            " * this works regardless of what the Services Engineer stage named it.",
            " */",
            "@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)",
            "public abstract class BaseApiTest {",
            "",
            "    @Autowired",
            "    protected TestRestTemplate restTemplate;",
            "",
            "    protected HttpHeaders authHeaders() {",
            "        HttpHeaders headers = new HttpHeaders();",
            '        String authType = System.getenv().getOrDefault("API_AUTH_TYPE", "none");',
            '        if ("basic".equals(authType)) {',
            '            String username = System.getenv().getOrDefault("API_BASIC_AUTH_USERNAME", "admin");',
            '            String password = System.getenv().getOrDefault("API_BASIC_AUTH_PASSWORD", "changeme");',
            '            String token = Base64.getEncoder().encodeToString((username + ":" + password).getBytes());',
            '            headers.set("Authorization", "Basic " + token);',
            "        }",
            "        return headers;",
            "    }",
            "}",
        ]) + "\n"

        # ── HealthTest.java ────────────────────────────────────────────────────
        files["src/test/java/com/api/HealthTest.java"] = "\n".join([
            "package com.api;",
            "",
            "import org.junit.jupiter.api.Test;",
            "import org.springframework.http.HttpEntity;",
            "import org.springframework.http.HttpMethod;",
            "import org.springframework.http.ResponseEntity;",
            "",
            "import static org.assertj.core.api.Assertions.assertThat;",
            "",
            "class HealthTest extends BaseApiTest {",
            "    @Test",
            "    void healthCheckReturns200() {",
            '        ResponseEntity<String> resp = restTemplate.exchange("/health", HttpMethod.GET, new HttpEntity<>(new org.springframework.http.HttpHeaders()), String.class);',
            "        assertThat(resp.getStatusCode().value()).isEqualTo(200);",
            "    }",
            "}",
        ]) + "\n"

        # ── AuthTest.java ──────────────────────────────────────────────────────
        if auth_type == "basic":
            first_protected = next((ep for ep in endpoints if (ep.get("method") or "GET").upper() == "GET"), None)
            if first_protected:
                files["src/test/java/com/api/AuthTest.java"] = "\n".join([
                    "package com.api;",
                    "",
                    "import org.junit.jupiter.api.Test;",
                    "import org.springframework.http.HttpEntity;",
                    "import org.springframework.http.HttpHeaders;",
                    "import org.springframework.http.HttpMethod;",
                    "import org.springframework.http.ResponseEntity;",
                    "",
                    "import java.util.Base64;",
                    "",
                    "import static org.assertj.core.api.Assertions.assertThat;",
                    "",
                    "class AuthTest extends BaseApiTest {",
                    "    @Test",
                    "    void unauthenticatedRequestIsRejected() {",
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{first_protected["path"]}", HttpMethod.GET, new HttpEntity<>(new HttpHeaders()), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(401);",
                    "    }",
                    "",
                    "    @Test",
                    "    void wrongCredentialsAreRejected() {",
                    "        HttpHeaders headers = new HttpHeaders();",
                    '        headers.set("Authorization", "Basic " + Base64.getEncoder().encodeToString("wrong:creds".getBytes()));',
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{first_protected["path"]}", HttpMethod.GET, new HttpEntity<>(headers), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(401);",
                    "    }",
                    "",
                    "    @Test",
                    "    void correctCredentialsAreAccepted() {",
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{first_protected["path"]}", HttpMethod.GET, new HttpEntity<>(authHeaders()), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(200);",
                    "    }",
                    "}",
                ]) + "\n"

        # ── RateLimitTest.java ─────────────────────────────────────────────────
        try:
            rl = int(rate_limit)
        except (TypeError, ValueError):
            rl = 0
        if rl > 0:
            gets = [ep for ep in endpoints if (ep.get("method") or "GET").upper() == "GET"]
            any_get = next((ep for ep in gets if not any(self._is_param_seg(s) for s in self._split_path(ep["path"]))), None)
            any_get = any_get or (gets[0] if gets else None) or (endpoints[0] if endpoints else None)
            if any_get:
                # Forced last via junit-platform.properties (alphabetical class
                # ordering) below + this "Zzz" name — rate limiting is keyed by
                # username when auth is basic, and there's only ever one valid
                # username, so this test's own deliberate overload would
                # otherwise poison every other test's shared rate-limit bucket
                # if it ran first. Same inherent limitation as the Python side:
                # re-running the suite again inside the same rate-limit window
                # will still interact with it, just not on a normal single run.
                files["src/test/resources/junit-platform.properties"] = (
                    "junit.jupiter.testclass.order.default="
                    "org.junit.jupiter.api.ClassOrderer$ClassName\n"
                )
                files["src/test/java/com/api/ZzzRateLimitTest.java"] = "\n".join([
                    "package com.api;",
                    "",
                    "import org.junit.jupiter.api.Test;",
                    "import org.springframework.http.HttpEntity;",
                    "import org.springframework.http.HttpMethod;",
                    "",
                    "import static org.assertj.core.api.Assertions.assertThat;",
                    "",
                    "class ZzzRateLimitTest extends BaseApiTest {",
                    "    @Test",
                    "    void exceedingRateLimitReturns429() {",
                    "        boolean sawRateLimited = false;",
                    f"        for (int i = 0; i < {rl + 5}; i++) {{",
                    f'            int status = restTemplate.exchange("{any_get["path"]}", HttpMethod.GET, new HttpEntity<>(authHeaders()), String.class).getStatusCode().value();',
                    "            if (status == 429) { sawRateLimited = true; break; }",
                    "        }",
                    '        assertThat(sawRateLimited).as("expected a 429 after exceeding the rate limit").isTrue();',
                    "    }",
                    "}",
                ]) + "\n"

        # ── per-entity CRUD test classes ───────────────────────────────────────
        def java_item_path(ep_path: str, replacement: str) -> str:
            segs = self._split_path(ep_path)
            new_segs = [replacement if self._is_param_seg(s) else s for s in segs]
            return "/" + "/".join(new_segs)

        for entity in ordered_entities:
            name = entity.get("name", "Entity")
            crud = crud_by_entity[name]
            fk_map = fk_by_entity[name]
            body_lines = []

            lines = [
                "package com.api;",
                "",
                "import org.junit.jupiter.api.Test;",
                "import org.springframework.http.HttpEntity;",
                "import org.springframework.http.HttpMethod;",
                "import org.springframework.http.ResponseEntity;",
                "",
                "import java.util.LinkedHashMap;",
                "import java.util.Map;",
                "",
                "import static org.assertj.core.api.Assertions.assertThat;",
                "",
                f"class {name}Test extends BaseApiTest {{",
            ]
            has_any = False

            if crud.get("create"):
                has_any = True
                lines += ["    @Test", f"    void create{name}HappyPath() {{"]
                for line in java_body_lines(entity, fk_map, "body"):
                    lines.append(f"        {line}")
                lines += [
                    f'        ResponseEntity<Map> resp = restTemplate.postForEntity("{crud["create"]["path"]}", new HttpEntity<>(body, authHeaders()), Map.class);',
                    "        assertThat(resp.getStatusCode().value()).isIn(200, 201);",
                    "    }",
                    "",
                ]
                omit = self._required_field_to_omit(entity, fk_map)
                if omit:
                    lines += ["    @Test", f"    void create{name}MissingRequiredField() {{"]
                    for line in java_body_lines(entity, fk_map, "body"):
                        lines.append(f"        {line}")
                    lines += [
                        f'        body.remove("{omit}");',
                        f'        ResponseEntity<Map> resp = restTemplate.postForEntity("{crud["create"]["path"]}", new HttpEntity<>(body, authHeaders()), Map.class);',
                        "        assertThat(resp.getStatusCode().value()).isIn(400, 422);",
                        "    }",
                        "",
                    ]

            if crud.get("list"):
                has_any = True
                lines += [
                    "    @Test",
                    f"    void list{name}() {{",
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{crud["list"]["path"]}", HttpMethod.GET, new HttpEntity<>(authHeaders()), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(200);",
                    "    }",
                    "",
                ]

            if crud.get("get") and crud.get("create"):
                has_any = True
                snake = self._snake(name)
                get_path_ok = java_item_path(crud["get"]["path"], f'" + {snake}Id + "')
                get_path_404 = java_item_path(crud["get"]["path"], "00000000-0000-0000-0000-000000000000")
                lines += [
                    "    @Test",
                    f"    void get{name}ById() {{",
                    f"        String {snake}Id = TestFixtures.create{name}(restTemplate, authHeaders());",
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{get_path_ok}", HttpMethod.GET, new HttpEntity<>(authHeaders()), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(200);",
                    "    }",
                    "",
                    "    @Test",
                    f"    void get{name}NotFound() {{",
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{get_path_404}", HttpMethod.GET, new HttpEntity<>(authHeaders()), String.class);',
                    "        assertThat(resp.getStatusCode().value()).isEqualTo(404);",
                    "    }",
                    "",
                ]

            if crud.get("delete") and crud.get("create"):
                has_any = True
                snake = self._snake(name)
                delete_path_ok = java_item_path(crud["delete"]["path"], f'" + {snake}Id + "')
                lines += [
                    "    @Test",
                    f"    void delete{name}() {{",
                    f"        String {snake}Id = TestFixtures.create{name}(restTemplate, authHeaders());",
                    f'        ResponseEntity<Void> resp = restTemplate.exchange("{delete_path_ok}", HttpMethod.DELETE, new HttpEntity<>(authHeaders()), Void.class);',
                    "        assertThat(resp.getStatusCode().value()).isIn(200, 204);",
                    "    }",
                ]

            lines.append("}")
            if has_any:
                files[f"src/test/java/com/api/{name}Test.java"] = "\n".join(lines) + "\n"

        # ── CustomEndpointsTest.java — smoke tests for anything non-CRUD-shaped ─
        if custom_endpoints:
            lines = [
                "package com.api;",
                "",
                "import org.junit.jupiter.api.Test;",
                "import org.springframework.http.HttpEntity;",
                "import org.springframework.http.HttpMethod;",
                "import org.springframework.http.ResponseEntity;",
                "",
                "import java.util.LinkedHashMap;",
                "import java.util.Map;",
                "",
                "import static org.assertj.core.api.Assertions.assertThat;",
                "",
                "/** Best-effort: just confirms these don't error out (< 500), not full business-rule coverage. */",
                "class CustomEndpointsTest extends BaseApiTest {",
            ]
            for i, ep in enumerate(custom_endpoints):
                method = (ep.get("method") or "GET").upper()
                resolved = java_item_path(ep.get("path", ""), "00000000-0000-0000-0000-000000000000") if any(
                    self._is_param_seg(s) for s in self._split_path(ep.get("path", ""))
                ) else ep.get("path", "")
                needs_body = method in ("POST", "PUT", "PATCH")
                lines += ["    @Test", f"    void customEndpoint{i}DoesNotError() {{"]
                if needs_body:
                    lines.append("        Map<String, Object> body = new LinkedHashMap<>();")
                    entity_arg = "new HttpEntity<>(body, authHeaders())"
                else:
                    entity_arg = "new HttpEntity<>(authHeaders())"
                lines += [
                    f'        ResponseEntity<String> resp = restTemplate.exchange("{resolved}", HttpMethod.{method}, {entity_arg}, String.class);',
                    "        assertThat(resp.getStatusCode().value()).isLessThan(500);",
                    "    }",
                    "",
                ]
            lines.append("}")
            files["src/test/java/com/api/CustomEndpointsTest.java"] = "\n".join(lines) + "\n"

        return files

    def _ensure_python_deps(self, database: str):
        """
        Defensive dependency completion — same "prompt alone isn't a strong
        enough guarantee" pattern as _normalize_python_layout. Observed in
        practice: (1) the LLM uses SQLAlchemy's async engine (as instructed) but
        doesn't reliably list the async driver package it requires, (2)
        requirements.txt doesn't reliably include python-dotenv even though
        security_bootstrap.py (added deterministically) needs it, and (3) exact
        `==` pins to older versions can lack a prebuilt wheel for whatever Python
        happens to be running the dev server, forcing a from-source build (e.g.
        pydantic-core needing a Rust toolchain) that fails offline/sandboxed.
        Relaxing to `>=` lets pip resolve to whatever wheel-available version
        actually works here, without changing what the LLM intended to use.
        """
        if "requirements.txt" not in self.files:
            return
        import re as _re
        import sys as _sys
        all_source = "\n".join(v for k, v in self.files.items() if k.endswith(".py"))
        req = _re.sub(r"==", ">=", self.files["requirements.txt"])

        # Strip hallucinated pip packages for stdlib modules — observed
        # directly: "sqlite3-python>=1.0.0" (sqlite3 is stdlib, never a pip
        # package) aborts `pip install -r requirements.txt` on that one
        # invalid line, which blocks every OTHER real dependency in the same
        # file from installing too, not just the bogus one.
        stdlib = getattr(_sys, "stdlib_module_names", frozenset())
        kept_lines, removed = [], []
        for line in req.splitlines():
            stripped = line.strip()
            pkg = _re.split(r"[<>=\[;]", stripped, 1)[0].strip() if stripped and not stripped.startswith("#") else ""
            normalized = pkg.replace("-", "_").lower()
            base = normalized[:-len("_python")] if normalized.endswith("_python") else normalized
            if pkg and base in stdlib:
                removed.append(pkg)
                continue
            kept_lines.append(line)
        if removed:
            req = "\n".join(kept_lines)
            self._p(f"skill:Removed non-existent stdlib pseudo-package(s) from requirements.txt: {', '.join(removed)}")

        added = []

        if "create_async_engine" in all_source:
            if database == "postgresql" and "asyncpg" not in req:
                added.append("asyncpg>=0.29.0")
            elif database != "postgresql" and "aiosqlite" not in req:
                added.append("aiosqlite>=0.20.0")

        if "dotenv" not in req:
            added.append("python-dotenv>=1.0.0")

        final_req = req.rstrip() + ("\n" + "\n".join(added) + "\n" if added else "\n")
        if final_req != self.files["requirements.txt"]:
            self.files["requirements.txt"] = final_req
            if added:
                self._p(f"skill:Added missing dependencies to requirements.txt: {', '.join(added)}")
            self._p("skill:Relaxed exact `==` version pins to `>=` in requirements.txt (avoids from-source builds on newer/different Python)")

    def _ensure_python_test_deps(self):
        """pytest + httpx (needed by fastapi.testclient.TestClient) for the
        deterministic test suite — added the same defensive way as the other
        Python dependency completion, not left to whatever the LLM's own
        requirements.txt happened to include."""
        if "requirements.txt" not in self.files:
            return
        req = self.files["requirements.txt"]
        added = [pkg for pkg in ("pytest>=8.0.0", "httpx>=0.27.0") if pkg.split(">=")[0] not in req]
        if added:
            self.files["requirements.txt"] = req.rstrip() + "\n" + "\n".join(added) + "\n"
            self._p(f"skill:Added test dependencies to requirements.txt: {', '.join(added)}")

    def _ensure_java_test_deps(self):
        """spring-boot-starter-test (brings JUnit 5 + AssertJ transitively)
        for the deterministic test suite, injected the same way as the other
        pom.xml dependency completion if the LLM's own pom.xml didn't already
        include it (most spring-boot-starter-parent projects do by default,
        but that's a convention, not a guarantee)."""
        if "pom.xml" not in self.files:
            return
        pom = self.files["pom.xml"]
        if "spring-boot-starter-test" in pom or "</dependencies>" not in pom:
            return
        dep = (
            "        <dependency>\n"
            "            <groupId>org.springframework.boot</groupId>\n"
            "            <artifactId>spring-boot-starter-test</artifactId>\n"
            "            <scope>test</scope>\n"
            "        </dependency>\n"
        )
        self.files["pom.xml"] = pom.replace("</dependencies>", dep + "    </dependencies>")
        self._p("skill:Added spring-boot-starter-test to pom.xml")

    def _ensure_java_security_deps(self, auth_type: str):
        """
        Inject sqlite-jdbc (always, for usage metering) and spring-boot-starter-
        security (only for basic auth) into the LLM-generated pom.xml if not
        already present — the deterministic security filters need these
        regardless of what database/auth the LLM's own Stage 1-3 output chose.
        """
        if "pom.xml" not in self.files:
            return
        pom = self.files["pom.xml"]
        deps_to_add = []
        if auth_type == "basic" and "spring-boot-starter-security" not in pom:
            deps_to_add.append(
                "        <dependency>\n"
                "            <groupId>org.springframework.boot</groupId>\n"
                "            <artifactId>spring-boot-starter-security</artifactId>\n"
                "        </dependency>\n"
            )
        if "sqlite-jdbc" not in pom:
            deps_to_add.append(
                "        <dependency>\n"
                "            <groupId>org.xerial</groupId>\n"
                "            <artifactId>sqlite-jdbc</artifactId>\n"
                "            <version>3.45.3.0</version>\n"
                "        </dependency>\n"
            )
        if deps_to_add and "</dependencies>" in pom:
            self.files["pom.xml"] = pom.replace("</dependencies>", "".join(deps_to_add) + "    </dependencies>")

    def _ensure_java_seed_data_disabled_in_spring(self):
        """
        Seeding is no longer Spring's job — api_runner.py seeds the SQLite file
        directly via Python's stdlib sqlite3 once the app is confirmed up
        (see ApiCrewOrchestrator/api_runner.seed_database), specifically to get
        off of Spring's own data.sql auto-run: it needed BOTH
        spring.sql.init.mode=always AND spring.jpa.defer-datasource-
        initialization=true set correctly (observed directly: seeded tables
        came up empty with only one of the two set — SQLite isn't in Spring's
        "embedded database" auto-detect list, and separately, JPA's ddl-auto
        creates tables AFTER Spring would otherwise run data.sql). Force
        spring.sql.init.mode=never here — overriding whatever the LLM wrote,
        since it was still told to generate data.sql and may default to the
        old "always" convention out of habit — so Spring never attempts its
        own run and double-inserts alongside the platform's separate seeding.
        """
        props_path = "src/main/resources/application.properties"
        if props_path not in self.files:
            return
        props = self.files[props_path]
        import re as _re
        if _re.search(r"^spring\.sql\.init\.mode\s*=", props, _re.MULTILINE):
            fixed = _re.sub(r"^spring\.sql\.init\.mode\s*=.*$", "spring.sql.init.mode=never", props, flags=_re.MULTILINE)
        else:
            fixed = props.rstrip() + "\n\n# Seeding is done by the platform directly against the .db file, not by Spring\nspring.sql.init.mode=never\n"
        if fixed != props:
            self.files[props_path] = fixed
            self._p("skill:Disabled Spring's own data.sql auto-run (spring.sql.init.mode=never) — "
                    "the platform seeds the database directly after startup instead")

    def _ensure_java_sqlite_foreign_keys_enabled(self):
        """
        SQLite disables foreign-key enforcement per connection by default —
        without this, a bad seed-data batch or a real API call can insert a
        row referencing a parent id that doesn't exist, and SQLite just lets
        it happen silently (observed directly: a Customer seed batch failed
        and got dropped, and the separately-generated Order seed batch still
        inserted rows referencing customer ids that were never created,
        because nothing enforced the foreign key at insert time). The Xerial
        sqlite-jdbc driver accepts this as a query parameter on the JDBC URL,
        so force it deterministically onto whatever URL the LLM wrote —
        relying on a prompt instruction for one easy-to-forget query string
        risks it being silently dropped again, the exact failure mode this
        fixes.
        """
        props_path = "src/main/resources/application.properties"
        if props_path not in self.files:
            return
        props = self.files[props_path]
        import re as _re
        match = _re.search(r"spring\.datasource\.url\s*=\s*jdbc:sqlite:(\S+)", props)
        if not match or "foreign_keys" in match.group(1):
            return
        old_url = match.group(0)
        sep = "&" if "?" in match.group(1) else "?"
        fixed = props.replace(old_url, old_url + f"{sep}foreign_keys=true")
        if fixed != props:
            self.files[props_path] = fixed
            self._p("skill:Enabled SQLite foreign-key enforcement on the JDBC URL — "
                     "a bad foreign key now fails loudly instead of silently succeeding")

    def _fix_java_bare_date_literals(self):
        """
        org.sqlite.jdbc3.JDBC3ResultSet.getDate() uses the SAME strict
        datetime parser as getTimestamp() — it requires the full
        'yyyy-MM-dd HH:mm:ss[.SSS]' pattern even for a genuine LocalDate
        column, so a bare '2024-05-28' seed literal (the correct, ordinary
        way to write a plain date) throws java.text.ParseException the
        moment any endpoint reads that row back through Hibernate.
        Reproduced directly. Scoped to only the LocalDate-mapped columns
        of each entity (found by parsing its own model file) — a blanket
        rewrite of every bare-date-shaped string anywhere in data.sql
        would also corrupt genuinely TEXT-typed date columns some
        entities intentionally use (e.g. a field declared `private
        String lastTraded;` for a column meant to stay a plain date
        string), which must NOT gain a time suffix.
        """
        date_columns_by_table: dict[str, set] = {}
        for path, content in self.files.items():
            if not path.startswith("src/main/java/com/api/model/") or not path.endswith(".java"):
                continue
            table_m = re.search(r'@Table\(name\s*=\s*"([^"]+)"', content)
            if not table_m:
                continue
            cols = set()
            for m in re.finditer(
                r'@Column\(name\s*=\s*"([^"]+)"[^)]*\)\s*\n\s*private\s+LocalDate\s+\w+;',
                content,
            ):
                cols.add(m.group(1))
            if cols:
                date_columns_by_table[table_m.group(1)] = cols
        if not date_columns_by_table:
            return

        path = "src/main/resources/data.sql"
        if path not in self.files:
            return
        content = self.files[path]

        def _split_top_level(s: str) -> list[str]:
            # SQL-literal-aware split on commas — tracks single-quoted
            # strings (with '' as an escaped quote inside one) so a comma
            # inside a text value is never mistaken for a value separator.
            parts, buf, in_str, i = [], [], False, 0
            while i < len(s):
                ch = s[i]
                if in_str:
                    if ch == "'" and s[i:i + 2] == "''":
                        buf.append("''")
                        i += 2
                        continue
                    if ch == "'":
                        in_str = False
                    buf.append(ch)
                else:
                    if ch == "'":
                        in_str = True
                        buf.append(ch)
                    elif ch == ",":
                        parts.append("".join(buf))
                        buf = []
                        i += 1
                        continue
                    else:
                        buf.append(ch)
                i += 1
            parts.append("".join(buf))
            return parts

        def _fix_insert(m: re.Match) -> str:
            table, col_list, body = m.group(1), m.group(2), m.group(3)
            date_cols = date_columns_by_table.get(table)
            if not date_cols:
                return m.group(0)
            columns = [c.strip() for c in col_list.split(",")]
            date_positions = {i for i, c in enumerate(columns) if c in date_cols}
            if not date_positions:
                return m.group(0)

            def _fix_tuple(tm: re.Match) -> str:
                values = _split_top_level(tm.group(1))
                changed = False
                for i in date_positions:
                    if i < len(values):
                        v = values[i].strip()
                        dm = re.fullmatch(r"'(\d{4}-\d{2}-\d{2})'", v)
                        if dm:
                            values[i] = f"'{dm.group(1)} 00:00:00.000'"
                            changed = True
                return "(" + ",".join(values) + ")" if changed else tm.group(0)

            fixed_body = re.sub(r"\(([^()]*)\)", _fix_tuple, body)
            return f"INSERT INTO {table} ({col_list}) VALUES{fixed_body}"

        fixed = re.sub(
            r'INSERT INTO (\w+) \(([^)]+)\) VALUES((?:\s*\([^;]*?\)\s*[,;])+)',
            _fix_insert,
            content,
            flags=re.DOTALL,
        )
        if fixed != content:
            self.files[path] = fixed
            self._p("skill:Rewrote bare DATE literals in data.sql (LocalDate-mapped columns only) to "
                     "the full timestamp format SQLite-JDBC's own date parser requires even for plain dates")

    def _fix_java_jpa_relationship_json_cycles(self):
        """
        Every @OneToMany/@ManyToOne/@OneToOne/@ManyToMany relationship field
        gets @JsonIgnore added, so Jackson never walks the relationship at
        serialization time.

        Reproduced directly: a Student entity's @OneToMany assignments/
        officeHours pointed back at each child's own @ManyToOne student
        field, with no cycle-breaking annotation anywhere in the generated
        model package. The controller returns the raw Student entity (not
        StudentDto, which exists but goes unused for GET responses) —
        Jackson recurses student -> assignments -> each assignment's
        student -> that student's assignments -> ... until a real
        StackOverflowError, which crashes mid-response and ships a
        truncated, invalid-JSON body straight to the browser (confirmed
        from the real crash: a repeating CollectionSerializer/BeanSerializer
        cycle in the stack trace).

        Safe to do unconditionally on every relationship field, not just
        the specific pair that crashed: every entity already has its own
        hand-written DTO with no relationship fields, and every
        relationship already gets its own dedicated paginated endpoint
        (e.g. GET /api/students/{id}/assignments) — so nothing anywhere
        actually depends on an entity embedding a nested relationship
        array in its own JSON. Uses the fully-qualified annotation name
        inline rather than adding an import line, so this can't collide
        with or duplicate an existing import.
        """
        rel_annotations = ("@OneToMany", "@ManyToOne", "@OneToOne", "@ManyToMany")
        for path, content in list(self.files.items()):
            if not (path.startswith("src/main/java/com/api/model/") and path.endswith(".java")):
                continue
            if not any(a in content for a in rel_annotations):
                continue
            lines = content.split("\n")
            new_lines = []
            changed = False
            prev_stripped = ""
            for line in lines:
                stripped = line.strip()
                if any(stripped.startswith(a) for a in rel_annotations) and "JsonIgnore" not in prev_stripped:
                    indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f"{indent}@com.fasterxml.jackson.annotation.JsonIgnore")
                    changed = True
                new_lines.append(line)
                prev_stripped = stripped
            if changed:
                self.files[path] = "\n".join(new_lines)
                self._p(f"skill:Added @JsonIgnore to relationship field(s) in {path.split('/')[-1]} "
                        f"to prevent a Jackson infinite-recursion crash on bidirectional JPA relationships")

    def _fix_java_sqlite_timestamp_format(self):
        """
        Defensive fix — observed directly: data.sql seeds a timestamp column
        with an ISO-8601 "T"-separated literal (e.g. '2024-01-16T14:00:00.000').
        The INSERT itself succeeds (SQLite stores it as plain text regardless
        of format), but org.sqlite.jdbc3.JDBC3ResultSet.getTimestamp() throws
        a java.text.ParseException the moment any endpoint tries to read that
        row back through Hibernate — the SQLite JDBC driver's own timestamp
        parser only accepts a space-separated 'yyyy-MM-dd HH:mm:ss[.SSS]'
        format, not the ISO "T" separator. This is exactly the kind of
        formatting detail a freehand LLM completion gets close but not
        byte-exact on, so rewrite every ISO timestamp literal in data.sql
        deterministically rather than relying on a prompt instruction.
        """
        path = "src/main/resources/data.sql"
        if path not in self.files:
            return
        import re as _re
        content = self.files[path]
        fixed = _re.sub(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})", r"\1 \2", content)
        if fixed != content:
            self.files[path] = fixed
            self._p("skill:Rewrote ISO 'T'-separated timestamps in data.sql to the space-separated format SQLite-JDBC's own timestamp parser expects")

    def _ensure_java_property_reference_exception_handled(self):
        """
        Every Spring Data `Pageable` parameter binds a client-supplied
        `sort` query value directly onto a property lookup with zero
        validation — reproduced directly: Swagger UI's "Try it out"
        defaults an unedited string parameter to the literal placeholder
        text "string", and submitting that as `sort=string` threw
        PropertyReferenceException, which nothing in the generated
        GlobalExceptionHandler caught, so it fell through to the generic
        Exception handler as an opaque "An unexpected error occurred" 500
        — a real, unhelpful robustness gap, not a bug limited to one
        project. Deterministic, not left to the LLM's own
        GlobalExceptionHandler (which reliably covers validation/parse
        errors but has no reason to know about this Spring Data-specific
        exception unless told): append a handler that reports the actual
        invalid field name and a 400, the same shape as every other
        handler already in the file.
        """
        path = "src/main/java/com/api/exception/GlobalExceptionHandler.java"
        if path not in self.files:
            return
        content = self.files[path]
        if "PropertyReferenceException" in content:
            return
        content = content.replace(
            "import org.springframework.http.ResponseEntity;",
            "import org.springframework.data.mapping.PropertyReferenceException;\n"
            "import org.springframework.http.ResponseEntity;",
            1,
        )
        handler_method = (
            "\n    @ExceptionHandler(PropertyReferenceException.class)\n"
            "    public ResponseEntity<Map<String, String>> handlePropertyReference(PropertyReferenceException ex) {\n"
            "        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorBody(\n"
            "                \"Invalid sort field: '\" + ex.getPropertyName() + \"'. Use a real field name "
            "(e.g. \\\"id\\\") or omit the sort parameter.\"));\n"
            "    }\n"
        )
        last_brace = content.rstrip().rfind("}")
        if last_brace == -1:
            return
        content = content[:last_brace] + handler_method + content[last_brace:]
        self.files[path] = content
        self._p("skill:Added a PropertyReferenceException handler to GlobalExceptionHandler — an invalid "
                 "?sort= field now returns a clear 400 instead of an opaque 500")

    def _ensure_java_entity_scan_covers_all_entities(self):
        """
        Reproduced directly on a real generation: the boot-check repair loop,
        fixing Forecast.java's compile errors, created a brand-new file under
        com.api.entity instead of editing the existing com.api.model.Forecast
        in place — ForecastRepository/Service/Controller all got re-pointed
        at the new one, but JpaConfig's @EntityScan(basePackages =
        "com.api.model") was never updated to match. Hibernate then refuses
        to treat com.api.entity.Forecast as a managed type ("Not a managed
        type"), which crashes the ENTIRE Spring context at boot — every
        other entity's endpoints 500 too, not just Forecast's, since the
        whole app never starts, not just the broken one. Rather than trying
        to detect and reconcile every way a repair pass could scatter entity
        classes across packages, just widen the scan to the app's one fixed
        root package (com.api) unconditionally — Spring Boot's own docs treat
        this as the safe default when package layout isn't guaranteed, and it
        costs nothing: an inert leftover duplicate class (like the
        now-orphaned com.api.model.Forecast here) just becomes dead weight
        Hibernate maps but nothing queries through, not a new bug.
        """
        for path, content in self.files.items():
            if "@EntityScan" not in content:
                continue
            fixed = re.sub(
                r'@EntityScan\(basePackages\s*=\s*"[^"]*"\)',
                '@EntityScan(basePackages = "com.api")',
                content,
            )
            if fixed != content:
                self.files[path] = fixed
                self._p("skill:Widened @EntityScan to cover all of com.api — a repair pass had "
                         "left an entity in a package the scan didn't cover, which crashes the "
                         "whole app at boot with 'Not a managed type'")
            return

    def _ensure_java_hibernate_sqlite_dialect_dep(self):
        """
        Hibernate has no built-in SQLite dialect — the LLM correctly writes
        `database-platform: org.hibernate.community.dialect.SQLiteDialect`
        into application.yaml/.yml/.properties (a real class, part of
        Hibernate's own official `hibernate-community-dialects` artifact),
        but reproduced directly, THREE times, with three DIFFERENT wrong
        answers across three separate generations: pom.xml instead declared
        a non-existent Maven coordinate for it — once
        io.github.pavlovroman:hibernate-sqlite-dialect, once
        org.hibernate.dialect:hibernate-dialect:6.3.0.Final, once
        com.zsoltfabok:sqlite-dialect:0.1.2 — every one of which fails
        dependency resolution outright and blocks the ENTIRE build before a
        single class even compiles. Since the wrong guess isn't consistent,
        matching on the CONCEPT rather than a specific wrong name: any
        dependency block mentioning "dialect" together with either
        "hibernate" or "sqlite" that isn't the one real artifact — the
        zsoltfabok case has "dialect" and "sqlite" in the
        groupId/artifactId but no "hibernate" at all in the tags themselves
        (only in a comment outside the <dependency> block), so requiring
        BOTH "hibernate" and "dialect" missed it. Only acts when the SQLite
        community dialect class is actually referenced, so this stays a
        no-op for projects using JPA without it (e.g. postgresql).
        """
        config_text = "".join(self.files.get(p, "") for p in (
            "src/main/resources/application.yaml",
            "src/main/resources/application.yml",
            "src/main/resources/application.properties",
        ))
        if "org.hibernate.community.dialect" not in config_text:
            return
        if "pom.xml" not in self.files:
            return
        pom = self.files["pom.xml"]

        def _drop_if_wrong(m: re.Match) -> str:
            block = m.group(0)
            if "hibernate-community-dialects" in block:
                return block
            lower = block.lower()
            if "dialect" in lower and ("hibernate" in lower or "sqlite" in lower):
                return ""
            return block

        fixed_pom = re.sub(r"<dependency>.*?</dependency>", _drop_if_wrong, pom, flags=re.DOTALL)
        if "hibernate-community-dialects" not in fixed_pom:
            if "</dependencies>" not in fixed_pom:
                return
            dep = (
                "        <dependency>\n"
                "            <groupId>org.hibernate.orm</groupId>\n"
                "            <artifactId>hibernate-community-dialects</artifactId>\n"
                "        </dependency>\n"
            )
            fixed_pom = fixed_pom.replace("</dependencies>", dep + "    </dependencies>")
        if fixed_pom != pom:
            self.files["pom.xml"] = fixed_pom
            self._p("skill:Fixed pom.xml — corrected the SQLite Hibernate dialect dependency "
                     "coordinate to the real one (org.hibernate.orm:hibernate-community-dialects)")

    def _fix_pom_xml_unescaped_entities(self):
        """
        Reproduced directly: a real generation's pom.xml <description> tag
        contained the app's own description text verbatim -- "CampusIQ -
        Student Success & Academic Intelligence" -- with a bare, un-escaped
        "&", which isn't valid XML (a literal "&" must be written "&amp;"
        inside element text). Maven can't even parse the POM at that
        point, so the ENTIRE build fails before a single class compiles --
        not a Java code bug at all, an XML-escaping bug in whichever LLM
        call wrote pom.xml, but the effect is total: nothing downstream
        (compile, boot, every other pom.xml fixup that does its own
        .replace() against this file) works until this is valid XML
        again. Escapes any "&" not already part of a real entity/
        character reference.
        """
        pom = self.files.get("pom.xml")
        if not pom:
            return
        fixed = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", pom)
        if fixed != pom:
            self.files["pom.xml"] = fixed
            self._p("skill:Fixed pom.xml — escaped a bare '&' in its text content "
                     "(e.g. in <description>) that made the whole file invalid XML, "
                     "which blocks Maven from reading the project at all")

    def _ensure_java_docs_dep(self):
        """
        Inject springdoc-openapi into the LLM-generated pom.xml if not already
        present — gives every Java API a free Swagger UI at /swagger-ui.html,
        the platform's built-in testing harness, matching FastAPI's built-in
        /docs on the Python side. Applies regardless of auth_type.
        """
        if "pom.xml" not in self.files:
            return
        pom = self.files["pom.xml"]
        if "springdoc-openapi" in pom or "</dependencies>" not in pom:
            return
        dep = (
            "        <dependency>\n"
            "            <groupId>org.springdoc</groupId>\n"
            "            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>\n"
            "            <version>2.6.0</version>\n"
            "        </dependency>\n"
        )
        self.files["pom.xml"] = pom.replace("</dependencies>", dep + "    </dependencies>")

    def _ensure_java_open_session_in_view(self):
        """
        Service methods routinely fetch one entity via a repository call, then
        traverse a @ManyToOne(fetch = LAZY) association a few lines later in
        the same method (e.g. CustomerService.getCustomerVehicles: looks up a
        VehicleModel, then calls model.getManufacturer().getName() to build a
        DTO field) — each individual Spring Data repository call is its own
        transaction, so by the time that later line runs, the session from the
        lookup that loaded the lazy proxy has already closed, and the request
        500s with "could not initialize proxy ... no Session". Reproduced
        directly against a live generated API. The LLM consistently writes
        spring.jpa.open-in-view=false into application.properties as a
        "best practice" (it's the one thing Spring Boot itself nags about in
        its startup logs if left unset) — which is exactly backwards for code
        shaped like this: Spring Boot's own actual default is true, and it's
        what keeps one Hibernate session open for the full request so a lazy
        association is still fetchable wherever it's touched. Force it back to
        true deterministically rather than hoping the LLM leaves it alone —
        first tried adding jackson-datatype-hibernate6 to null out unfetched
        proxies during Jackson serialization, but that's the wrong layer: this
        code calls the getter itself mid-request, not via passive
        serialization, and a nulled-out manufacturer name is a worse answer
        than a real one anyway.
        """
        props_path = "src/main/resources/application.properties"
        if props_path not in self.files:
            return
        props = self.files[props_path]
        import re as _re
        if _re.search(r"^spring\.jpa\.open-in-view\s*=\s*true\s*$", props, _re.MULTILINE):
            return
        if _re.search(r"^spring\.jpa\.open-in-view\s*=", props, _re.MULTILINE):
            fixed = _re.sub(r"^spring\.jpa\.open-in-view\s*=.*$", "spring.jpa.open-in-view=true", props, flags=_re.MULTILINE)
        else:
            fixed = props.rstrip() + "\n\n# Kept open so a lazy association touched later in a service method\n# (not just during Jackson serialization) doesn't throw LazyInitializationException\nspring.jpa.open-in-view=true\n"
        self.files[props_path] = fixed
        self._p("skill:Forced spring.jpa.open-in-view=true — a lazy Hibernate association is now "
                 "fetchable for the life of the request instead of throwing LazyInitializationException "
                 "once the triggering repository call's own transaction closes")

    def _ensure_java_ddl_auto_update(self):
        """
        Hibernate's ddl-auto mode controls whether it creates/updates tables
        from the entity classes ("update") or only VALIDATES an
        already-existing schema against them, never creating anything
        ("validate"/"none") — and nothing else in this pipeline ever runs
        schema.sql against the live .db file (Spring's own auto-init is
        deliberately disabled, see _ensure_java_seed_data_disabled_in_spring;
        WebUIGenerator's integration seeds data separately, after the app is
        already up, which itself requires the tables to already exist).
        Reproduced directly: the LLM sometimes writes ddl-auto: validate as a
        "safer for production" default, which is exactly wrong here — with
        nothing else able to create the schema, that crashes the app at
        EVERY boot with SchemaManagementException: missing table. Force it
        to "update" deterministically, across whichever config file format
        the LLM chose (application.properties key=value, or
        application.yml/.yaml's nested key: value).
        """
        for filename in ("application.properties", "application.yml", "application.yaml"):
            path = f"src/main/resources/{filename}"
            if path not in self.files:
                continue
            content = self.files[path]
            if filename == "application.properties":
                pattern = r"^spring\.jpa\.hibernate\.ddl-auto\s*=\s*(\S+)\s*$"
            else:
                pattern = r"^(\s*)ddl-auto:\s*(\S+)\s*$"
            m = re.search(pattern, content, re.MULTILINE)
            if m:
                current_value = m.group(1) if filename == "application.properties" else m.group(2)
                if current_value == "update":
                    return
                if filename == "application.properties":
                    fixed = re.sub(pattern, "spring.jpa.hibernate.ddl-auto=update", content, flags=re.MULTILINE)
                else:
                    fixed = re.sub(pattern, r"\1ddl-auto: update", content, flags=re.MULTILINE)
            elif filename == "application.properties":
                fixed = content.rstrip() + "\nspring.jpa.hibernate.ddl-auto=update\n"
            else:
                # yaml with no ddl-auto key at all — don't guess where to
                # insert it under whatever nesting the LLM chose.
                return
            self.files[path] = fixed
            self._p(f"skill:Forced Hibernate ddl-auto to 'update' in {filename} — nothing else in this "
                     f"pipeline creates the schema, so any other mode (validate/none/create-drop) crashes "
                     f"the app at startup with a 'missing table' SchemaManagementException")
            return

    def _ensure_java_pagination_property(self):
        """
        Mirrors Python's MAX_PAGE_SIZE (.env + src/database.py) — a single,
        externally-adjustable ceiling for list-endpoint page size, instead of
        each controller's own call picking (and possibly disagreeing on) a
        hardcoded literal. Controllers are told to constructor-inject
        `@Value("${app.pagination.max-size:1000}")` (see
        api_services_engineer's role text), which resolves to 1000 even if
        this property is never explicitly present — so this is a
        transparency/adjustability addition (so the value is visible and
        editable in application.properties, the same way RATE_LIMIT_RPM-
        equivalent settings already are), not a correctness requirement the
        app would break without. Idempotent — does nothing if already
        present, at any value (an explicit choice, even a lower one, is left
        alone rather than overridden).
        """
        for filename in ("application.properties", "application.yml", "application.yaml"):
            path = f"src/main/resources/{filename}"
            if path not in self.files:
                continue
            content = self.files[path]
            if filename == "application.properties":
                if re.search(r"^app\.pagination\.max-size\s*=", content, re.MULTILINE):
                    return
                self.files[path] = content.rstrip() + "\napp.pagination.max-size=1000\n"
            else:
                if re.search(r"^\s*max-size:\s*\d+\s*$", content, re.MULTILINE):
                    return
                # yaml with no existing key — don't guess where to nest it
                # under whatever structure the LLM chose; the @Value
                # default (1000) still applies either way.
                return
            self._p(f"skill:Added app.pagination.max-size=1000 to {filename} — the same "
                     f"externally-adjustable page-size ceiling Python projects get via "
                     f"MAX_PAGE_SIZE in .env")
            return

    _RESERVED_JAVA_SECURITY_CLASSNAMES = {
        "RateLimitFilter", "UsageTrackingFilter", "HealthController",
        "SecurityConfig", "UsageController", "UsageDb",
    }

    # Bean *method* names the deterministic SecurityConfig.java template itself
    # defines (see AgentPlatform/catalog/api_security_engineer/templates/java/
    # SecurityConfig.java). Spring registers
    # a @Bean by its method name, not by the class that declares it — the LLM is
    # free to name its own config class anything (SecurityConfiguration,
    # WebSecurityConfig, ...) and still produce a same-named filterChain()/
    # userDetailsService() bean that collides with the deterministic one at
    # context-startup (BeanDefinitionOverrideException), so classname matching
    # alone misses it.
    _RESERVED_JAVA_BEAN_METHOD_NAMES = {"filterChain", "userDetailsService"}

    def _remove_conflicting_java_security_classes(self):
        """
        Defensive removal — despite an explicit prompt instruction not to, the LLM
        has still written its own rate-limiting/health/usage/security-config
        classes elsewhere in the tree (e.g. com.api.filter.RateLimitFilter, or a
        com.api.config.SecurityConfiguration with its own filterChain() bean).
        Spring derives a bean's registration key from the class's simple name (for
        classname collisions) or from the @Bean method's own name (for bean-name
        collisions), so either one collides with the deterministic com.api.security.*
        equivalent at context-startup time even though they're different files in
        different packages — a ConflictingBeanDefinitionException, not a compile
        error, so it wouldn't be caught until the app actually tries to start.
        Delete any such duplicates before the deterministic ones are added.

        Also removes any OTHER file that imports one of the deleted classes (e.g. a
        FilterConfig that manually registers the LLM's own RateLimitFilter via
        FilterRegistrationBean) — leaving it in place would just trade a startup
        exception for a compile error referencing a now-missing class.

        Name-based matching alone isn't enough — observed directly: an LLM wrote
        its own full Basic Auth config (@EnableWebSecurity class, its own
        SecurityFilterChain and InMemoryUserDetailsManager beans) under
        deliberately different class/method names specifically to dodge the
        name-collision rule above, leaving TWO independent, non-colliding auth
        configs that don't crash Spring at startup but silently fight over which
        one actually authenticates each request — indistinguishable from a
        genuine wrong-password bug from the outside. So also remove any file
        declaring @EnableWebSecurity, or a @Bean method whose return type is
        SecurityFilterChain/UserDetailsService/InMemoryUserDetailsManager,
        regardless of what the class or method is named.
        """
        reserved_dir = "src/main/java/com/api/security/"
        removed_fqns = []
        to_remove = []
        for path, content in self.files.items():
            if not path.endswith(".java"):
                continue
            classname = path.rsplit("/", 1)[-1][:-5]
            # Skip only our OWN deterministic files by exact name — not the whole
            # directory. The LLM is just as free to drop a rogue file into
            # com.api.security itself (observed directly: BasicAuthSecurityConfig
            # sitting right next to the deterministic SecurityConfig), so a blanket
            # directory skip would hide exactly the files this method exists to catch.
            if path.startswith(reserved_dir) and classname in self._RESERVED_JAVA_SECURITY_CLASSNAMES:
                continue
            has_reserved_classname = classname in self._RESERVED_JAVA_SECURITY_CLASSNAMES
            has_reserved_bean = "@Bean" in content and any(
                re.search(rf"\b{name}\s*\(", content) for name in self._RESERVED_JAVA_BEAN_METHOD_NAMES
            )
            has_own_security_config = "@EnableWebSecurity" in content or (
                "@Bean" in content and re.search(
                    r"\b(?:public|protected)\s+(?:SecurityFilterChain|UserDetailsService|"
                    r"InMemoryUserDetailsManager)\s+\w+\s*\(",
                    content,
                )
            )
            if has_reserved_classname or has_reserved_bean or has_own_security_config:
                to_remove.append(path)
                pkg_match = re.search(r"^package\s+([\w.]+);", content, re.MULTILINE)
                if pkg_match:
                    removed_fqns.append(f"{pkg_match.group(1)}.{classname}")

        if removed_fqns:
            for path, content in self.files.items():
                if path in to_remove or not path.endswith(".java"):
                    continue
                if any(f"import {fqn};" in content for fqn in removed_fqns):
                    to_remove.append(path)

        for path in to_remove:
            del self.files[path]
        if to_remove:
            self._p(f"skill:Removed {len(to_remove)} LLM-authored file(s) conflicting with "
                    f"deterministic security classes: {', '.join(to_remove)}")
