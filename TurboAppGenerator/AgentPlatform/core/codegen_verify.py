"""
Deterministic verification + LLM-repair loop for freshly-generated per-entity
code, shared between WebAPIGenerator's ApiCrewOrchestrator and (once wired
up) WebUIGenerator's own per-entity ORM generation.

Extracted verbatim from WebAPIGenerator/api_agents/api_orchestrator.py (the
original, proven implementation) as a mixin rather than free functions,
since these ~25 methods call each other extensively and all share the same
small contract: the including class must provide `self._p` (progress
logging), `self._call_llm` (system+user -> JSON dict), `self._coerce_files`
(dict -> validated {path: content}), `self.files` (dict[str, str], mutated
in place), `self.project_dir` (Path | None), and `self._flush_to_disk`
(writes self.files to self.project_dir). Any orchestrator exposing that
contract can inherit CodegenVerifyMixin to get the full boot-check-and-repair
pipeline (Java: static check -> mvn compile -> Spring Boot boot; Python:
static check -> pip install -> import check -> uvicorn boot) for free.

Entry points: verify_and_repair_java() / verify_and_repair_python().
"""

import json
import os
import re
from pathlib import Path


class CodegenVerifyMixin:
    def _verify_and_repair_java(self):
        """
        Single entry point for all deterministic Java safety nets, in the
        order that makes sense: the cheap static check runs first (no LLM
        call, no Maven invocation), then a boot check is pointless if the
        code doesn't even compile, so compile-check comes before it.

        Then it runs ONE MORE TIME, after everything else — compile-check
        and boot-check are both LLM repair passes, each shown only a
        failing file and its own error, with no idea the static check's
        specific structural facts (mappedBy naming, FK-target-must-be-PK-
        or-UNIQUE) exist to begin with. Either can touch a relationship/FK
        declaration while fixing something unrelated and reintroduce
        exactly what the static check already found and fixed once. It's
        purely additive and a no-op when nothing's wrong, so running it
        twice costs nothing when the repairs above never touched a model.
        """
        self._static_check_and_repair_java()
        if self._compile_check_and_repair_java():
            self._boot_check_and_repair_java()
        self._static_check_and_repair_java()

    def _static_check_and_repair_java(self):
        """
        Purely additive — runs before compile/boot checks and changes
        nothing if it finds nothing. JPA's equivalent of Python/SQLAlchemy's
        back_populates mismatch: @OneToMany/@OneToOne/@ManyToMany(mappedBy =
        "x") must name a real FIELD (not just any identifier) on the other
        entity. Same reasoning as the Python version — this is a structural
        name-matching fact, cheaper and more reliable to verify by parsing
        the actual generated code than by waiting for the Spring context to
        fail at boot. Regex-based rather than a real Java parser, so it's
        deliberately conservative: only flags a mismatch when both the
        target entity and its field list were confidently extracted, to
        avoid a false positive nudging a repair call at an already-correct
        file — verified directly against several real, already-working
        generated projects' entity files before trusting it.
        """
        problems = list(self._static_check_java_relationships())
        touched: set[str] = set()
        if problems:
            touched |= {p for p in self.files if p.startswith("src/main/java/com/api/model/") and p.endswith(".java")}

        id_type_problems = self._static_check_java_dto_id_types()
        if id_type_problems:
            problems += id_type_problems
            touched |= {p for p in self.files if p.startswith("src/main/java/com/api/model/") and p.endswith(".java")}
            touched |= {p for p in self.files if p.startswith("src/main/java/com/api/dto/") and p.endswith(".java")}
            touched |= {p for p in self.files if p.startswith("src/main/java/com/api/service/") and p.endswith(".java")}

        if not problems:
            return
        self._p(f"skill:Static check found {len(problems)} structural issue(s) before starting the app:")
        for p in problems:
            self._p(f"skill:  - {p}")
        diagnosis = (
            "Structural mismatches found by static analysis of the generated code (not a compile "
            "or runtime error yet, but each one WILL cause a Spring Boot startup failure, or a "
            "silent wrong-value response with no error at all):\n"
            + "\n".join(f"- {p}" for p in problems)
        )
        ok = self._call_java_repair_llm(
            "static-analysis", diagnosis, touched,
            extra_system="Fix each listed mismatch precisely as described. For a mappedBy "
                         "mismatch, change whichever side's mappedBy string doesn't match the "
                         "other side's real field name. For an id-type mismatch, change the "
                         "DTO's id field (and its getter/setter) to the SAME type as the "
                         "entity's real @Id field — never the other way around, the entity's "
                         "type is what SQLite/Hibernate actually uses — and make sure the "
                         "service's entity-to-DTO mapping copies the id value directly "
                         "(e.g. dto.setId(entity.getId())) instead of converting it, discarding "
                         "it, or leaving it unset.",
        )
        if ok:
            self._flush_to_disk()

    def _static_check_java_dto_id_types(self) -> list[str]:
        """
        Confirms every entity's DTO declares its `id` field with the EXACT
        same type as the entity's own @Id field. This platform's own rule
        (String for SQLite ids — see api_services_engineer's role text) is
        already stated explicitly in the prompt, but isn't always followed:
        Long and String are both perfectly valid field types on their own,
        so a DTO declaring the wrong one doesn't fail to compile or boot —
        it just leaves the service layer's entity->DTO mapping with no
        valid way to copy the real id value across. Reproduced directly,
        twice in the same generation: one service invented a converter that
        unconditionally `return null`s ("ID is stored as a String...not
        reliable, so we simply return null-safe 0" — followed by `return
        null`, not 0), the other two services simply never called
        `dto.setId(...)` at all. Every single API response returned
        `"id": null` for every row, with nothing anywhere — no compile
        error, no boot error, no exception — ever surfacing it.
        """
        entity_files = {p: c for p, c in self.files.items()
                        if p.startswith("src/main/java/com/api/model/") and p.endswith(".java")}
        problems = []
        for path, content in entity_files.items():
            entity_name = Path(path).stem
            id_m = re.search(
                r"@Id\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)\s+([\w.]+)\s+\w+\s*;",
                content,
            )
            if not id_m:
                continue
            entity_id_type = id_m.group(1).rsplit(".", 1)[-1]
            dto_path = f"src/main/java/com/api/dto/{entity_name}Dto.java"
            dto_content = self.files.get(dto_path)
            if not dto_content:
                continue
            dto_id_m = re.search(r"(?:private|protected|public)\s+([\w.]+)\s+id\s*;", dto_content)
            if not dto_id_m:
                continue
            dto_id_type = dto_id_m.group(1).rsplit(".", 1)[-1]
            if dto_id_type != entity_id_type:
                problems.append(
                    f"{dto_path}: id field is declared as {dto_id_type}, but {path}'s @Id "
                    f"field is {entity_id_type} — these must match exactly, or the service "
                    f"layer's entity->DTO mapping has no valid way to copy the real id value "
                    f"across (every response ends up returning \"id\": null)."
                )
        return problems

    def _static_check_java_relationships(self) -> list[str]:
        """
        For every @OneToMany/@OneToOne/@ManyToMany(mappedBy = "x") found,
        confirms the target entity (from the immediately-following field's
        declared generic/plain type) actually has a field literally named x
        — AND that field isn't the target's own @Id primary key. Reproduced
        directly: Position declared `@OneToMany(mappedBy = "id")` pointing
        at Trade/RiskMetric — both genuinely have a field named "id" (their
        own primary key), so the original name-only check passed, but
        mappedBy inherently means "the field on the other side that owns
        the reference back to me", which a plain @Id primary key can never
        be. Hibernate's metadata build chokes on this nonsensical mapping
        during SessionFactory init, which aborted schema generation for
        every entity — not just the two with the bad relationship — while
        the rest of the app still booted and served requests, so every
        table came back "no such table" with no boot failure and no
        compile error to point at it.
        """
        entity_files = {p: c for p, c in self.files.items()
                        if p.startswith("src/main/java/com/api/model/") and p.endswith(".java")}

        class_fields: dict[str, set[str]] = {}
        class_id_field: dict[str, str] = {}
        for path, content in entity_files.items():
            class_name = Path(path).stem
            class_fields[class_name] = set(
                re.findall(r"(?:private|protected|public)\s+[\w.]+(?:<[\w.,\s<>]+>)?\s+(\w+)\s*;", content)
            )
            id_m = re.search(
                r"@Id\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:private|protected|public)\s+[\w.]+\s+(\w+)\s*;",
                content,
            )
            if id_m:
                class_id_field[class_name] = id_m.group(1)

        problems = []
        for path, content in entity_files.items():
            class_name = Path(path).stem
            for m in re.finditer(
                r'@(?:OneToMany|OneToOne|ManyToMany)\s*\([^)]*?mappedBy\s*=\s*"(\w+)"[^)]*\)'
                r'\s*(?:@\w+(?:\([^)]*\))?\s*)*'  # any other annotations before the field itself
                r'(?:private|protected|public)\s+[\w.]+<\s*([\w.]+)\s*>\s+(\w+)\s*;'
                r'|'
                r'@(?:OneToOne)\s*\([^)]*?mappedBy\s*=\s*"(\w+)"[^)]*\)'
                r'\s*(?:@\w+(?:\([^)]*\))?\s*)*'
                r'(?:private|protected|public)\s+([\w.]+)\s+(\w+)\s*;',
                content,
            ):
                if m.group(1) is not None:
                    mapped_by, target_type, field_name = m.group(1), m.group(2), m.group(3)
                else:
                    mapped_by, target_type, field_name = m.group(4), m.group(5), m.group(6)
                target_type = target_type.rsplit(".", 1)[-1]
                target_fields = class_fields.get(target_type)
                if target_fields is None:
                    continue  # target entity file not found among what we have — don't guess, skip
                if mapped_by not in target_fields:
                    problems.append(
                        f"{path}: {class_name}.{field_name} has mappedBy=\"{mapped_by}\", expecting "
                        f"{target_type} to have a field named \"{mapped_by}\", but it doesn't "
                        f"(found: {', '.join(sorted(target_fields)) or 'none'})."
                    )
                elif mapped_by == class_id_field.get(target_type):
                    problems.append(
                        f"{path}: {class_name}.{field_name} has mappedBy=\"{mapped_by}\", but "
                        f"{target_type}.{mapped_by} is {target_type}'s own @Id primary key, not a "
                        f"relationship field pointing back to {class_name} — mappedBy must name a "
                        f"@ManyToOne/@JoinColumn field on {target_type} that references {class_name}, "
                        f"never {target_type}'s own primary key. If {target_type} has no such field at "
                        f"all, remove this @OneToMany/@OneToOne relationship from {class_name} entirely "
                        f"instead of inventing an invalid mappedBy for it."
                    )
        return problems

    def _compile_check_and_repair_java(self, max_attempts: int = 4) -> bool:
        """
        Model/repository/service/controller code is freeform LLM output with
        no shared template to guard ahead of time — observed directly: a
        project "generated successfully" with entities declaring `Long` ids
        while every repository interface declared `JpaRepository<Entity,
        String>`, a mismatch that only surfaces as a wall of javac errors,
        never as a runtime symptom you'd catch by hitting an endpoint. Rather
        than enumerate every way the LLM's own code can be internally
        inconsistent, just try to build it for real right here and, on
        failure, hand javac's own error output back to the LLM for a
        targeted repair — the same signal a human would use — bounded to a
        few attempts so a genuinely unrepairable failure doesn't loop
        forever. Runs after every stage that writes Java source has already
        completed and flushed to disk, in both generate() and refine().
        Returns whether the project compiles clean by the time this returns.
        """
        if not self.project_dir:
            return False
        self._p("crew:Verifying the generated Java project compiles...")
        for attempt in range(1, max_attempts + 1):
            ok, errors = self._run_mvn_compile()
            if ok:
                if attempt > 1:
                    self._p(f"skill:Build compiles cleanly after {attempt - 1} automatic repair pass(es)")
                else:
                    self._p("skill:Build compiles cleanly")
                return True
            self._p(f"skill:Compile check failed (attempt {attempt}/{max_attempts}) — "
                     f"{len(errors)} error line(s) found")
            if attempt == max_attempts:
                break
            if not self._repair_java_compile_errors(errors):
                self._p("skill:Automatic repair produced no usable fix — giving up")
                break
            self._flush_to_disk()
        self._p("skill:WARNING — the generated project may still not compile; check "
                 "api_server.log after Start, or run `mvn compile` in the project directory, "
                 "for what still needs fixing")
        return False

    def _run_mvn_compile(self) -> tuple[bool, list[str]]:
        """
        Run `mvn compile` (deliberately not `test-compile` — matches
        api_runner's own -Dmaven.test.skip=true at actual startup; LLM test
        code compiling cleanly is a separate quality concern from "does the
        app build") against self.project_dir. Best-effort: any failure to
        even invoke Maven (not found, timeout) is treated as a pass — this
        check exists to catch LLM code bugs, not to gate generation on the
        local machine's own tool availability.
        """
        import subprocess
        from agents.uigen_agent import resolve_java_maven_env
        env = dict(os.environ)
        try:
            mvn_cmd = resolve_java_maven_env(env, self.project_dir)
            result = subprocess.run(
                [mvn_cmd, "compile", "-q"],
                cwd=str(self.project_dir), env=env, capture_output=True, text=True, timeout=180,
            )
        except Exception as e:
            self._p(f"skill:Could not run compile check ({e}) — skipping")
            return True, []
        if result.returncode == 0:
            return True, []
        output = (result.stdout or "") + (result.stderr or "")
        error_lines = [line for line in output.splitlines() if line.startswith("[ERROR]")]
        return False, error_lines or [output[-4000:]]

    def _widen_java_repair_context(self, touched_paths: set[str], cap: int = 15) -> set[str]:
        """
        Given the specific files an error already points at, pull in each
        one's own model/repository/dto imports too — observed directly: a
        service flagged by javac imports the repository whose declared ID
        type actually caused the mismatch, but that repository interface's
        OWN line is never flagged (an interface with no method bodies has
        nothing for javac — or a runtime Spring error — to point at), so
        without this the LLM never sees the file that actually needs fixing
        and "fixes" the wrong side instead, just shuffling the same problem
        into new call sites. Bounded so a file with many imports can't blow
        up the repair prompt's size.
        """
        related: set[str] = set()
        for p in touched_paths:
            content = self.files.get(p, "")
            for m in re.finditer(r"import\s+com\.api\.(model|repository|dto)\.(\w+);", content):
                candidate = f"src/main/java/com/api/{m.group(1)}/{m.group(2)}.java"
                if candidate in self.files:
                    related.add(candidate)
        all_paths = touched_paths | related
        if len(all_paths) > cap:
            all_paths = touched_paths | set(list(related)[: max(0, cap - len(touched_paths))])
        return all_paths

    def _call_java_repair_llm(self, kind: str, error_text: str, all_paths: set[str],
                               extra_system: str = "", role: str = "Java/Spring Boot") -> bool:
        """
        Shared repair call for every deterministic verify-and-repair safety
        net (Java compile-check, Java boot-check, Python import-check) — same
        shape (errors + current file content in, corrected files out), just a
        different error source and target language. Returns True if the LLM
        returned at least one usable fix, which the caller has already
        merged into self.files by the time this returns.
        """
        files_block = "\n\n".join(
            f"--- {p} ---\n{self.files[p]}" for p in sorted(all_paths) if p in self.files
        )
        if not files_block:
            return False

        system = (
            f"You are a {role} engineer fixing a {kind} error in an already-generated "
            "project. You are given the error and the CURRENT content of the files it implicates "
            "PLUS the model/repository/dto files they depend on, so you can see which side of a "
            "mismatch or conflict is actually correct before choosing which file to change. "
            f"{extra_system} Fix ONLY what the error requires — do not redesign, rename, or "
            "restructure anything else, and do not touch any file not shown to you."
        )
        user = (
            f"Error:\n{error_text}\n\n"
            f"Current file contents (files implicated by the error, plus their model/repository/dto "
            f"dependencies for context):\n{files_block}\n\n"
            f"Return JSON: {{\"files\": {{\"path\": \"full corrected file content\", ...}}}} — "
            f"include only files you actually changed, each with its complete corrected content."
        )
        # Retry once on an unusable response before giving up — reproduced
        # directly: the LLM correctly diagnosed a real, repairable bug (a
        # Spring Data query method with an invalid return type) but
        # returned the fix as a bare string instead of the requested
        # {"files": {...}} shape. That's the exact same transient response-
        # shape miss this codebase already retries once for elsewhere (seed
        # data batches under _run_seed_batch) — not a sign the LLM couldn't
        # figure out the fix. Without this, the caller's own (far more
        # expensive) recompile/reboot attempt budget absorbed the failure
        # for nothing: the loop just gave up immediately instead of using
        # one of its remaining attempts to try again.
        for attempt in range(2):
            try:
                result = self._call_llm(system, user, max_tokens=16000)
            except Exception as e:
                self._p(f"skill:Repair call failed: {e}")
                continue
            raw = result.get("files", {})
            if isinstance(raw, str):
                # Reproduced directly on a multi-file repair (runtime/boot
                # kind): the model wrapped the WHOLE files object as a JSON
                # string instead of a real object — the single-target wrap
                # below only ever helps when exactly one file is targeted,
                # so a multi-file miss like this was silently dropped every
                # attempt, retries included. Try parsing it as JSON first;
                # only fall back to the single-target wrap if that fails.
                try:
                    parsed, _end = json.JSONDecoder().raw_decode(raw.strip())
                except (json.JSONDecodeError, ValueError):
                    parsed = None
                if isinstance(parsed, dict) and parsed:
                    raw = parsed
                elif len(all_paths) == 1:
                    raw = {next(iter(all_paths)): raw}
            fixed = self._coerce_files(raw, f"{kind.capitalize()} repair")
            if fixed:
                self.files.update(fixed)
                self._p(f"skill:Repair pass updated {len(fixed)} file(s): {', '.join(sorted(fixed))}")
                return True
            if attempt == 0:
                self._p(f"skill:{kind.capitalize()} repair response was unusable, retrying once...")
        return False

    def _repair_java_compile_errors(self, error_lines: list[str]) -> bool:
        """
        Extract the specific source files javac's own error output names and
        hand them (plus their model/repository/dto dependencies) to the
        shared repair call — far more reliable than asking the LLM to
        regenerate the whole project blind, and cheap enough (a handful of
        files, not the full project) to run more than once.
        """
        touched_paths: set[str] = set()
        for line in error_lines:
            m = re.search(r"([A-Za-z]:[\\/][^:]+?\.java):\[\d+,\d+\]", line)
            if not m:
                continue
            try:
                rel = Path(m.group(1)).relative_to(self.project_dir).as_posix()
            except ValueError:
                continue
            touched_paths.add(rel)
        if not touched_paths:
            return False
        all_paths = self._widen_java_repair_context(touched_paths)
        errors_block = "\n".join(error_lines)[:6000]
        return self._call_java_repair_llm(
            "compile", errors_block, all_paths,
            extra_system=(
                "(e.g. an entity's declared @Id type vs. its repository's "
                "JpaRepository<Entity, ...> type param). If the error is a method "
                "'cannot override ... return type X is not compatible with Y' from a class "
                "that extends a concrete third-party class (e.g. extending org.sqlite."
                "SQLiteDataSource to add behavior), do not just change the override's return "
                "type or delegate to a same-class overload — that still leaves an invalid "
                "override with an incompatible (widened) return type and will fail identically. "
                "Switch to composition instead: hold the third-party class as a private field, "
                "implement the plain interface (e.g. javax.sql.DataSource) directly rather than "
                "extending the concrete class, and delegate each interface method to the field."
            ),
        )

    def _boot_check_and_repair_java(self, max_attempts: int = 3) -> bool:
        """
        mvn compile only validates javac-level correctness. Spring's own
        ApplicationContext startup does a separate, later round of
        validation — JPA query-method return-type rules, ambiguous
        @RequestMapping routes registered by two different controllers, bean
        autowiring conflicts, and more — that only surfaces once the app
        actually boots, never as a compile error. Observed directly, twice
        in one morning, on two different freshly-generated projects (a
        Pageable/Optional query-method shape violation, and two separate
        controllers both mapping the exact same route). Rather than
        enumerate every one of these ahead of time, actually start the app
        for real on a throwaway port and repair off whatever exception
        Spring itself throws — same mechanism as the compile-check, one
        layer up the stack, run only after compilation is already confirmed
        clean (see _verify_and_repair_java).
        """
        if not self.project_dir:
            return False
        self._p("crew:Verifying the generated Java project actually starts...")
        for attempt in range(1, max_attempts + 1):
            ok, error_text = self._run_java_boot_check()
            if ok:
                if attempt > 1:
                    self._p(f"skill:App boots cleanly after {attempt - 1} automatic repair pass(es)")
                else:
                    self._p("skill:App boots cleanly")
                return True
            self._p(f"skill:Boot check failed (attempt {attempt}/{max_attempts})")
            if attempt == max_attempts:
                break
            if not self._repair_java_boot_error(error_text):
                self._p("skill:Automatic repair produced no usable fix — giving up")
                break
            self._flush_to_disk()
            # The boot fix just edited Java files too — recheck compilation
            # before spending another full boot attempt (much slower) on
            # code that can't even build. max_attempts=2 (not 1): reproduced
            # directly — a boot repair fixed the Pageable/Optional violation
            # it was asked to but introduced 14 new compile errors doing it,
            # and the OLD max_attempts=1 here meant this recheck could only
            # ever detect that and give up, never actually repair it, since
            # with a 1-attempt budget the loop's own "if attempt ==
            # max_attempts: break" fires before any repair call is made.
            if not self._compile_check_and_repair_java(max_attempts=2):
                self._p("skill:Boot repair broke compilation — giving up")
                break
        self._p("skill:WARNING — the generated project may still fail to start; check "
                 "api_server.log after Start for what still needs fixing")
        return False

    def _run_java_boot_check(self, timeout: int = 75) -> tuple[bool, str]:
        """
        Start the app for real on a throwaway port — never the project's own
        assigned port, since this runs during generate()/refine() itself,
        before any real Start call, and must not collide with or disturb an
        already-running instance of a DIFFERENT project. Startup success =
        either /health responds or "Started Application" appears in the log
        (mirrors api_runner.wait_for_api's own success signals); failure =
        the process exits on its own first. A timeout with the process still
        running and neither signal seen is treated as a pass — this check
        exists to catch LLM code bugs like the ones above, not to penalize a
        slow-but-working boot on a loaded machine.

        Startup succeeding is NOT the same as the app actually working —
        reproduced directly: a real generation's Spring context started
        cleanly (this check alone would have said "pass") while every
        single list endpoint 500'd on its very first real request, because
        the service layer handed Jackson a raw JPA entity instead of a DTO.
        A bug that only fires when a route actually runs is invisible to
        "did the process boot", the same blind spot Python's own boot check
        closed by hitting real endpoints — mirrored here: once startup is
        confirmed, discover routes via springdoc's /v3/api-docs and hit
        every no-path-param GET. Best-effort only — if /v3/api-docs itself
        isn't reachable (unusual auth setup, springdoc not on the
        classpath for some reason), that's not treated as a failure; it
        just means this extra layer of coverage is skipped for this run,
        same floor as before this existed.
        """
        import json as _json
        import subprocess
        import tempfile
        import time as _time
        import urllib.error as _ue
        import urllib.request as _ur
        from agents.uigen_agent import _port_is_free, resolve_java_maven_env
        from api_agents.api_runner import _kill_port

        port = 19000
        while not _port_is_free(port):
            port += 1

        env = dict(os.environ)
        try:
            mvn_cmd = resolve_java_maven_env(env, self.project_dir)
        except Exception as e:
            self._p(f"skill:Could not resolve Maven for the boot check ({e}) — skipping")
            return True, ""

        auth_header = None
        env_file = self.project_dir / ".env"
        if env_file.exists():
            env_text = env_file.read_text(encoding="utf-8")
            if "API_AUTH_TYPE=basic" in env_text:
                import base64 as _b64
                creds_user, creds_pass = "admin", "changeme"
                for line in env_text.splitlines():
                    if line.startswith("API_BASIC_AUTH_USERNAME="):
                        creds_user = line.split("=", 1)[1].strip()
                    elif line.startswith("API_BASIC_AUTH_PASSWORD="):
                        creds_pass = line.split("=", 1)[1].strip()
                auth_header = "Basic " + _b64.b64encode(f"{creds_user}:{creds_pass}".encode()).decode()

        def _probe_endpoints(port: int, log_path: Path) -> tuple[bool, str]:
            headers = {"Authorization": auth_header} if auth_header else {}
            try:
                req = _ur.Request(f"http://127.0.0.1:{port}/v3/api-docs", headers=headers)
                spec = _json.loads(_ur.urlopen(req, timeout=5).read())
            except Exception:
                return True, ""  # docs unreachable — skip this extra layer, not a failure
            paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
            for path, methods in paths.items():
                if "{" in path or not isinstance(methods, dict) or "get" not in methods:
                    continue
                try:
                    req = _ur.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
                    _ur.urlopen(req, timeout=8)
                except _ue.HTTPError as e:
                    if e.code >= 500:
                        log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
                        return False, log_text[-6000:]
                except Exception:
                    pass
            return True, ""

        log_path = Path(tempfile.gettempdir()) / f"boot_check_{self.project_dir.name}_{port}.log"
        proc = None
        try:
            with open(log_path, "w", encoding="utf-8") as log_file:
                cmd = [mvn_cmd, "spring-boot:run", "-Dmaven.test.skip=true",
                       f"-Dspring-boot.run.arguments=--server.port={port}"]
                kwargs: dict = {"cwd": str(self.project_dir), "env": env,
                                 "stdout": log_file, "stderr": log_file}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen(cmd, **kwargs)

            deadline = _time.time() + timeout
            started = False
            while _time.time() < deadline:
                if proc.poll() is not None:
                    break
                try:
                    _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                    started = True
                    break
                except _ue.HTTPError:
                    started = True
                    break
                except Exception:
                    pass
                log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
                if "Started Application" in log_text:
                    started = True
                    break
                _time.sleep(1)

            if started:
                return _probe_endpoints(port, log_path)

            if proc.poll() is None:
                return True, ""  # inconclusive — still starting, not a failure

            log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
            return False, log_text[-6000:]
        finally:
            if proc is not None and proc.poll() is None:
                if os.name == "nt":
                    # mvn.cmd forks the real Spring Boot JVM as a CHILD
                    # process — proc.terminate() only kills the immediate
                    # mvn.cmd/cmd.exe process, leaving that JVM running as
                    # an orphan that still holds log_path open. Reproduced
                    # directly: on a failed boot (nothing ever bound the
                    # port, so _kill_port below finds nothing), the
                    # unlink() then raised an unhandled WinError 32 and
                    # crashed the whole generation job. /T kills the
                    # process's entire tree, not just its top PID.
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                        capture_output=True, timeout=10)
                    except Exception:
                        pass
                else:
                    try:
                        proc.terminate()
                        proc.wait(timeout=8)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            _kill_port(port)
            # Best-effort even after the tree-kill above: Windows doesn't
            # always release a just-killed process's file handles the
            # instant taskkill returns. A lingering handle for one extra
            # moment must never crash the generation over a temp log file.
            for _attempt in range(3):
                try:
                    log_path.unlink(missing_ok=True)
                    break
                except OSError:
                    _time.sleep(0.5)

    def _repair_java_boot_error(self, error_text: str) -> bool:
        """
        Spring's own startup failures reference class/bean names, not
        file:[line,col] positions the way javac does, so touched files are
        found by matching fully-qualified com.api.* class references in the
        exception text against self.files, plus lowerCamelCase bean names
        (Spring derives these from the class name, e.g.
        'vehicleProgramController' for VehicleProgramController — the
        ambiguous-route error we hit names exactly this way) against every
        controller/service/repository/config file, then widened the same
        way as a compile repair.
        """
        if not error_text.strip():
            return False
        touched_paths: set[str] = set()
        for m in re.finditer(r"com\.api\.(\w+)\.(\w+)", error_text):
            candidate = f"src/main/java/com/api/{m.group(1)}/{m.group(2)}.java"
            if candidate in self.files:
                touched_paths.add(candidate)
        for m in re.finditer(r"\b([a-z][a-zA-Z0-9]*(?:Controller|Service|Repository|Config))\b", error_text):
            class_name = m.group(1)[0].upper() + m.group(1)[1:]
            for pkg in ("controller", "service", "repository", "config", "security"):
                candidate = f"src/main/java/com/api/{pkg}/{class_name}.java"
                if candidate in self.files:
                    touched_paths.add(candidate)
        if not touched_paths:
            return False
        all_paths = self._widen_java_repair_context(touched_paths)
        return self._call_java_repair_llm(
            "startup", error_text[:6000], all_paths,
            extra_system="(e.g. two different controllers mapping the exact same "
                         "@RequestMapping route, or a repository query method whose "
                         "return type violates Spring Data's rules for a Pageable parameter)",
        )

    def _verify_and_repair_python(self):
        """
        Single entry point for all Python safety nets, in the order that
        makes sense: the cheap, deterministic static check runs first (no
        LLM call, no subprocess, catches a couple of specific structural
        mismatches with certainty), then the import-check, then the
        boot-check — each one only expensive enough to run once the
        cheaper one ahead of it hasn't already found the problem.

        Then it runs ONE MORE TIME, after everything else — the import-
        check and boot-check are both LLM repair passes, each shown only a
        failing file and its own error, with no idea the static check's
        specific structural facts (back_populates naming, FK-target-must-
        be-PK-or-UNIQUE) exist to begin with. Either can touch a
        relationship/FK declaration while fixing something unrelated and
        reintroduce exactly what the static check already found and fixed
        once. It's purely additive and a no-op when nothing's wrong, so
        running it twice costs nothing when the repairs above never
        touched a model.
        """
        if not self.project_dir:
            return
        self._static_check_and_repair_python()
        self._pip_install_requirements()
        if self._import_check_and_repair_python():
            self._boot_check_and_repair_python()
        self._static_check_and_repair_python()

    def _static_check_and_repair_python(self):
        """
        Purely additive — runs before anything else and changes nothing if
        it finds nothing. Two specific bug classes are structural NAME-
        MATCHING facts, not judgment calls, and are cheaper and more
        reliable to verify by parsing the actual generated code than by
        waiting for a real request to crash (or asking an LLM reviewer to
        notice — a reviewer can miss the exact same typo the author made):
        (1) a SQLAlchemy relationship's back_populates="X" not matching a
        real attribute named X on the other model (reproduced directly:
        Dealership.salespersons vs Salesperson's back_populates=
        "salespeople" — one word off, compiled and imported fine, only
        crashed on the first real request); (2) database.py's engine style
        (sync/async) not matching .env's DATABASE_URL driver scheme
        (reproduced directly: sync database.py, but .env still had the old
        sqlite+aiosqlite:// URL — MissingGreenlet on the first real
        connection). Never touches .env — the fix direction is always to
        make database.py match the platform's one canonical convention
        (plain synchronous SQLAlchemy), never to change .env credentials.
        """
        problems = self._static_check_python_relationships()
        problems += self._static_check_python_fk_unique()
        url_problem = self._static_check_python_db_url()
        if url_problem:
            problems.append(url_problem)
        if not problems:
            return
        self._p(f"skill:Static check found {len(problems)} structural issue(s) before starting the app:")
        for p in problems:
            self._p(f"skill:  - {p}")
        diagnosis = (
            "Structural mismatches found by static analysis of the generated code (not a runtime "
            "error yet, but each one WILL cause one on the first real request):\n"
            + "\n".join(f"- {p}" for p in problems)
        )
        touched = {p for p in self.files if p.startswith("src/models/") and p.endswith(".py")}
        touched.add("src/database.py")
        ok = self._call_java_repair_llm(
            "static-analysis", diagnosis, touched,
            extra_system=(
                "Fix each listed mismatch precisely as described. For a back_populates mismatch, "
                "change whichever side's string doesn't match the other side's real attribute name "
                "— don't guess at a different cause. For a ForeignKey/unique mismatch, add "
                "unique=True to the TARGET column's own mapped_column(...) call (never remove or "
                "change the ForeignKey(...) declaration itself). For a database.py/DATABASE_URL "
                "mismatch, ALWAYS fix it by making database.py use plain synchronous SQLAlchemy "
                "(create_engine, Session, sessionmaker) — never suggest or imply a change to .env, "
                "which is not shown to you and must not be touched."
            ),
            role="Python/FastAPI/SQLAlchemy",
        )
        if ok:
            self._flush_to_disk()

    def _static_check_python_relationships(self) -> list[str]:
        """
        Parses every src/models/*.py file with Python's own ast module (not
        regex) and cross-references every relationship(...)'s back_populates
        against the actual attributes defined on its target class. Exact —
        no false positives from formatting differences, since this is the
        same parser Python itself uses.
        """
        import ast

        model_files = {p: c for p, c in self.files.items()
                        if p.startswith("src/models/") and p.endswith(".py")}
        class_relationship_attrs: dict[str, set[str]] = {}
        entries: list[tuple[str, str, str | None, str | None, str]] = []

        for path, content in model_files.items():
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                attrs_here = class_relationship_attrs.setdefault(node.name, set())
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                            and isinstance(stmt.targets[0], ast.Name):
                        attr_name = stmt.targets[0].id
                        call = stmt.value
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        attr_name = stmt.target.id
                        call = stmt.value
                    else:
                        continue
                    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id == "relationship"):
                        continue
                    attrs_here.add(attr_name)
                    target_name = None
                    if call.args and isinstance(call.args[0], ast.Constant) \
                            and isinstance(call.args[0].value, str):
                        target_name = call.args[0].value.rsplit(".", 1)[-1]
                    back_populates = None
                    for kw in call.keywords:
                        if kw.arg == "back_populates" and isinstance(kw.value, ast.Constant):
                            back_populates = kw.value.value
                    entries.append((node.name, attr_name, target_name, back_populates, path))

        problems = []
        for class_name, attr_name, target_name, back_populates, path in entries:
            if not (target_name and back_populates):
                continue
            target_attrs = class_relationship_attrs.get(target_name)
            if target_attrs is None:
                problems.append(
                    f"{path}: {class_name}.{attr_name} = relationship(\"{target_name}\", "
                    f"back_populates=\"{back_populates}\") references class \"{target_name}\", but no "
                    f"model class with that name was found among the generated model files."
                )
            elif back_populates not in target_attrs:
                problems.append(
                    f"{path}: {class_name}.{attr_name} = relationship(\"{target_name}\", "
                    f"back_populates=\"{back_populates}\") expects {target_name} to have a "
                    f"relationship attribute literally named \"{back_populates}\", but it doesn't "
                    f"(found: {', '.join(sorted(target_attrs)) or 'none'})."
                )
        return problems

    def _static_check_python_fk_unique(self) -> list[str]:
        """
        Parses every src/models/*.py file with Python's own ast module and
        confirms every ForeignKey("table.column") target column is EITHER
        that table's primary key or explicitly declared `unique=True`.
        SQLite requires this of any real FOREIGN KEY constraint — create_all()
        builds the live table straight from this ForeignKey(...) call (not
        from schema.sql, which is a separate, largely cosmetic artifact for
        this pipeline), so a target column that's merely indexed rather than
        unique doesn't fail to import or to create the table — it fails the
        moment a real row is inserted, with SQLite's own generic "foreign
        key mismatch", which names neither the missing UNIQUE nor which
        column needs it. Reproduced directly: a carrier/shipment
        relationship matched by carrier NAME (a business key, not the
        numeric primary key) declared `ForeignKey("carriers.name")`, but
        `Carrier.name` had only `index=True`, not `unique=True` — every
        single seed insert failed, and the Java version of the same app
        avoided it only by chance (that generation's own schema never added
        the FK constraint at all).
        """
        import ast

        model_files = {p: c for p, c in self.files.items()
                        if p.startswith("src/models/") and p.endswith(".py")}

        # table_name -> class_name, class_name -> {column_name: is_unique_or_pk}
        table_to_class: dict[str, str] = {}
        class_columns: dict[str, dict[str, bool]] = {}
        # (path, class_name, column_name, target_table, target_column)
        fk_entries: list[tuple[str, str, str, str, str]] = []

        for path, content in model_files.items():
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                columns_here = class_columns.setdefault(node.name, {})
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                            and isinstance(stmt.targets[0], ast.Name):
                        target_name_node = stmt.targets[0]
                        value = stmt.value
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        target_name_node = stmt.target
                        value = stmt.value
                    else:
                        continue
                    attr_name = target_name_node.id
                    if attr_name == "__tablename__" and isinstance(value, ast.Constant) \
                            and isinstance(value.value, str):
                        table_to_class[value.value] = node.name
                        continue
                    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                            and value.func.id == "mapped_column"):
                        continue
                    is_unique_or_pk = False
                    fk_target: str | None = None
                    for kw in value.keywords:
                        if kw.arg in ("unique", "primary_key") and isinstance(kw.value, ast.Constant) \
                                and kw.value.value is True:
                            is_unique_or_pk = True
                    for arg in value.args:
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                                and arg.func.id == "ForeignKey" and arg.args \
                                and isinstance(arg.args[0], ast.Constant) \
                                and isinstance(arg.args[0].value, str):
                            fk_target = arg.args[0].value
                    columns_here[attr_name] = is_unique_or_pk
                    if fk_target and "." in fk_target:
                        target_table, target_column = fk_target.split(".", 1)
                        fk_entries.append((path, node.name, attr_name, target_table, target_column))

        problems = []
        for path, class_name, attr_name, target_table, target_column in fk_entries:
            target_class = table_to_class.get(target_table)
            if target_class is None:
                continue  # target table not found among what we have — don't guess, skip
            target_is_unique_or_pk = class_columns.get(target_class, {}).get(target_column)
            if target_is_unique_or_pk is None:
                continue  # target column not found — a different check's job
            if not target_is_unique_or_pk:
                problems.append(
                    f"{path}: {class_name}.{attr_name} declares ForeignKey(\"{target_table}."
                    f"{target_column}\"), but {target_class}.{target_column} is neither the "
                    f"primary key nor declared unique=True — SQLite rejects any FOREIGN KEY "
                    f"whose target isn't one of those two, failing with 'foreign key mismatch' "
                    f"the moment a row is inserted. Add unique=True to {target_class}."
                    f"{target_column}'s mapped_column(...)."
                )
        return problems

    def _static_check_python_db_url(self) -> str | None:
        """
        Reads the REAL .env this project will actually run with (not just
        database.py's own os.getenv(...) fallback default, which a real
        deployed value silently overrides) and confirms its DATABASE_URL
        driver scheme agrees with whether database.py's engine is async or
        sync.
        """
        db_content = self.files.get("src/database.py", "")
        if not db_content:
            return None
        uses_async = "create_async_engine" in db_content or "AsyncSession" in db_content

        env_content = self.files.get(".env", "")
        if not env_content and self.project_dir:
            env_path = self.project_dir / ".env"
            if env_path.exists():
                try:
                    env_content = env_path.read_text(encoding="utf-8")
                except OSError:
                    env_content = ""
        m = re.search(r"^DATABASE_URL\s*=\s*(\S+)", env_content, re.MULTILINE)
        if not m:
            return None
        url = m.group(1)
        url_is_async = "+aiosqlite" in url or "+asyncpg" in url

        if uses_async and not url_is_async:
            return (f"src/database.py uses an ASYNC SQLAlchemy engine (create_async_engine/"
                    f"AsyncSession) but .env's DATABASE_URL ({url}) is a plain SYNC driver URL.")
        if url_is_async and not uses_async:
            return (f"src/database.py uses a plain SYNC SQLAlchemy engine but .env's DATABASE_URL "
                    f"({url}) uses an ASYNC driver scheme.")
        return None

    def _import_check_and_repair_python(self, max_attempts: int = 5) -> bool:
        """
        Python has no separate compile step the way Java does — a model with
        a real bug (e.g. a SQLAlchemy relationship type annotation that
        isn't wrapped in Mapped[...]) imports "successfully" as far as the
        interpreter's own syntax/bytecode checks go; the failure only
        surfaces when the entry module is actually imported and a library
        like SQLAlchemy does its own class-scanning validation at
        class-definition time. Reproduced directly: a generated FastAPI
        project crashed on startup with exactly this SQLAlchemy
        MappedAnnotationError, well after "generation" itself finished
        without any reported error. Importing src.main in a fresh
        subprocess alone reproduces the failure — uvicorn never even gets
        to bind a port, since the crash happens at import time, before
        uvicorn gets that far.
        """
        self._p("crew:Verifying the generated Python project starts...")
        for attempt in range(1, max_attempts + 1):
            ok, error_text = self._run_python_import_check()
            if ok:
                if attempt > 1:
                    self._p(f"skill:App imports cleanly after {attempt - 1} automatic repair pass(es)")
                else:
                    self._p("skill:App imports cleanly")
                return True
            self._p(f"skill:Import check failed (attempt {attempt}/{max_attempts})")
            if attempt == max_attempts:
                break
            if not self._repair_python_import_error(error_text):
                self._p("skill:Automatic repair produced no usable fix — giving up")
                break
            self._flush_to_disk()
        self._p("skill:WARNING — the generated project may still fail to start; check "
                 "api_server.log after Start for what still needs fixing")
        return False

    def _pip_install_requirements(self):
        """
        The import check below needs the project's real dependencies
        actually installed — this platform doesn't use a per-project venv,
        it installs into the same interpreter api_runner.py later starts
        uvicorn with (sys.executable), so whatever's already installed from
        earlier generations is normally already satisfied and this is fast.
        Best-effort: a failed/slow install here just means the import check
        below can't run reliably either, so both are skipped together via
        the same try/except pattern used everywhere else in this file.
        """
        req_path = self.project_dir / "requirements.txt"
        if not req_path.exists():
            return
        import subprocess
        import sys
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_path)],
                cwd=str(self.project_dir), capture_output=True, text=True, timeout=300,
            )
        except Exception as e:
            self._p(f"skill:Could not install dependencies for the import check ({e}) — skipping")

    def _run_python_import_check(self, timeout: int = 30) -> tuple[bool, str]:
        """Mirrors _run_mvn_compile's shape for Python: best-effort, any
        failure to even invoke the interpreter is treated as a pass — this
        check exists to catch LLM code bugs, not to gate generation on the
        local machine's own environment."""
        import subprocess
        import sys
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import src.main"],
                cwd=str(self.project_dir), capture_output=True, text=True, timeout=timeout,
            )
        except Exception as e:
            self._p(f"skill:Could not run the import check ({e}) — skipping")
            return True, ""
        if result.returncode == 0:
            return True, ""
        output = (result.stdout or "") + (result.stderr or "")
        return False, output[-6000:]

    def _repair_python_import_error(self, error_text: str) -> bool:
        """
        A Python traceback already names every file in the actual import
        chain (route → service → repository → model, ...), unlike a single
        javac error line — so touched files come straight from the
        traceback's own `File "...", line N` frames. Still widened one step
        further for model files specifically: a relationship annotation bug
        like the one that motivated this (SQLAlchemy's Mapped[...]
        requirement) is inherently two-sided — the crash names whichever
        model class SQLAlchemy scanned first, not necessarily the model on
        the OTHER end of the relationship that also needs a matching fix —
        so every other file under src/models/ is pulled in too when any one
        of them is implicated.

        `ImportError: cannot import name 'X' from 'Y' (path/to/Y.py)` is a
        second shape entirely — observed directly: a bare Python name lookup
        failure has no `File "...", line N` frame for the module it failed
        to find X in (there's no new file being executed, just a name
        missing from one already loaded), so the one file that actually
        needs the fix — Y's own __init__.py, usually missing a re-export —
        was never in touched_paths at all and a real, otherwise-fixable
        bug went unrepaired. Extracted separately via ImportError's own
        parenthetical path.
        """
        touched_paths = self._touched_paths_from_python_traceback(error_text)
        if not touched_paths:
            return False
        if any(p.startswith("src/models/") for p in touched_paths):
            touched_paths |= {p for p in self.files if p.startswith("src/models/") and p.endswith(".py")}
        all_paths = self._widen_python_repair_context(touched_paths)
        return self._call_java_repair_llm(
            "startup", error_text[:6000], all_paths,
            extra_system=(
                "This error is a SQLAlchemy 2.0 Mapped[...] annotation mistake, and it is usually "
                "not a one-off typo — the same LLM wrote every model file the same way, so the "
                "identical mistake is very likely repeated across OTHER attributes and OTHER "
                "model files too, ones this particular error hasn't even reached yet because "
                "Python's class-scanning stops at the first bad annotation it finds. Scan EVERY "
                "attribute in EVERY model file you've been given for ALL of these common mistakes "
                "and fix all of them in this one pass, not just the single one named in the "
                "error: (1) a relationship or column with no Mapped[...] wrapper at all, "
                "(2) Mapped[List] or Mapped[Optional] used bare, with no inner type argument — "
                "must be Mapped[List[\"Other\"]] / Mapped[Optional[\"Other\"]] / Mapped[\"Other\"] "
                "(never a bare generic with nothing inside the brackets), (3) a forward-reference "
                "string in Mapped[\"X\"] that doesn't match the actual related class's name."
            ),
            role="Python/FastAPI/SQLAlchemy",
        )

    def _touched_paths_from_python_traceback(self, error_text: str) -> set[str]:
        """
        Shared file-extraction logic for both the import-check (SQLAlchemy
        class-scanning errors) and boot-check (runtime request errors)
        repair passes: touched files come from the traceback's own
        `File "...", line N` frames, plus ImportError's own parenthetical
        path shape (`cannot import name 'X' from 'Y' (path/to/Y.py)`), which
        has no `File` frame at all for the module that actually needs fixing.

        A third shape has neither: SQLAlchemy's mapper configuration is
        lazy, so a `back_populates` string on one model that doesn't match
        an actual attribute on the OTHER model only throws once the ORM
        first configures itself — reproduced directly:
        `sqlalchemy.exc.InvalidRequestError: Mapper 'Mapper[Dealership
        (dealerships)]' has no property 'salespersons'`, with a traceback
        that's ENTIRELY internal sqlalchemy/orm/*.py library frames, zero
        references to any file under the project — every `File "...", line
        N` frame gets discarded by the relative_to check above, touched_paths
        comes back empty, and the repair call never even fires. The mapper
        error message itself names the class directly, so that's matched
        separately here and mapped to its likely model file by name.
        """
        if not error_text.strip():
            return set()
        touched_paths: set[str] = set()
        for m in re.finditer(r'File "([^"]+\.py)"', error_text):
            try:
                rel = Path(m.group(1)).relative_to(self.project_dir).as_posix()
            except ValueError:
                continue
            if rel in self.files:
                touched_paths.add(rel)
        for m in re.finditer(r"cannot import name '(\w+)' from '[\w.]+' \(([^)]+\.py)\)", error_text):
            try:
                rel = Path(m.group(2)).relative_to(self.project_dir).as_posix()
            except ValueError:
                continue
            if rel in self.files:
                touched_paths.add(rel)
        for m in re.finditer(r"Mapper\[(\w+)\(", error_text):
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", m.group(1)).lower()
            candidate = f"src/models/{snake}.py"
            if candidate in self.files:
                touched_paths.add(candidate)
        # "Multiple classes found for path X" names the ambiguous class
        # directly — search EVERY file (not just src/models/) for that exact
        # class declaration, since the actual duplicate can live anywhere.
        # Reproduced directly: the real second `class Technician(Base)` was
        # sitting in src/repositories/technician.py, a full redundant
        # re-declaration of the model instead of importing it — repeatedly
        # "fixing" src/models/technician.py alone (the only file the
        # broader models/-only fallback below would have included) never
        # touched the actual duplicate at all, and the same error kept
        # recurring attempt after attempt.
        for m in re.finditer(r'Multiple classes found for path "(\w+)"', error_text):
            class_name = m.group(1)
            pattern = re.compile(rf"^class {re.escape(class_name)}\(", re.MULTILINE)
            for path, content in self.files.items():
                if path.endswith(".py") and pattern.search(content):
                    touched_paths.add(path)
        # General fallback, not another one-off pattern: SQLAlchemy's lazy
        # declarative-registry configuration can fail in many distinct ways
        # once it actually runs (a back_populates mismatch, a duplicate
        # class name shadowing another one's string reference, ...), each
        # phrasing its own message differently and NONE naming a project
        # file in the traceback (it's all internal sqlalchemy/orm/*.py
        # frames) — reproduced directly, twice, with two completely
        # different SQLAlchemy error messages back to back on the same
        # project. Chasing every possible message shape with its own regex
        # doesn't scale; any unrecognized SQLAlchemy exception is reliably
        # "something about how the models relate to each other", so default
        # to every model file rather than returning empty and never even
        # calling the LLM.
        if not touched_paths and re.search(r"sqlalchemy\.(?:orm\.)?exc\.\w*Error", error_text):
            touched_paths = {p for p in self.files if p.startswith("src/models/") and p.endswith(".py")}
        return touched_paths

    def _repair_python_boot_error(self, error_text: str) -> bool:
        """
        Runtime-only failures — the import check above can never see these,
        since nothing is wrong until an actual request runs. Reproduced
        directly, both in the same generated project: (1) every repository
        function was written as a plain sync `def` taking a SQLAlchemy
        `Session` (no `await` anywhere), while database.py set up an ASYNC
        engine/session instead — db.execute(...) returned an un-awaited
        coroutine, and .scalars() on that coroutine threw AttributeError on
        every single request; (2) Base.metadata.create_all(...) (or the
        async equivalent) was never called anywhere in the project at all,
        so the .db file never even got created — a query against a table
        that was never created fails just as loudly, just later.
        """
        touched_paths = self._touched_paths_from_python_traceback(error_text)
        if not touched_paths:
            return False
        if any(p.startswith("src/models/") for p in touched_paths):
            touched_paths |= {p for p in self.files if p.startswith("src/models/") and p.endswith(".py")}
        # database.py is the one file that's rarely IN the traceback (the
        # mismatch it causes always surfaces inside whatever repository
        # touched it first) but is very often the actual file that needs to
        # change — always include it as context if it exists.
        if "src/database.py" in self.files:
            touched_paths.add("src/database.py")
        all_paths = self._widen_python_repair_context(touched_paths)
        return self._call_java_repair_llm(
            "runtime", error_text[:6000], all_paths,
            extra_system=(
                "This is a request-time failure, not an import-time one — the app started fine, "
                "so look for these two specific, previously-confirmed mismatches rather than "
                "assuming it's a typo in just the one function named in the traceback: "
                "(1) sync/async mismatch — every repository/service file uses plain `def` "
                "functions with a synchronous SQLAlchemy `Session` and calls like "
                "`db.execute(stmt).scalars()...` with no `await`, but database.py sets up an "
                "ASYNC engine (create_async_engine/AsyncSession/async_sessionmaker) — the fix is "
                "to make database.py use the SYNC SQLAlchemy API (create_engine, Session, "
                "sessionmaker) to match what every repository already assumes, NOT to rewrite "
                "every repository/service file to be async; (2) if there is no call anywhere to "
                "Base.metadata.create_all(...) (check by looking for it in database.py's own "
                "content, which you've been given), the database file and its tables are never "
                "created at all — add one, called once at import/module time in database.py "
                "itself (after Base and engine are both defined), not inside a route handler; "
                "(3) 'Mapper ... has no property X' means a relationship's back_populates=\"X\" "
                "on ONE model doesn't match an actual relationship attribute defined on the OTHER "
                "model — this only throws lazily on first ORM use, so it's easy to miss; you've "
                "been given every model file specifically so you can find both ends of the "
                "mismatched relationship and make them agree, not just the one model class named "
                "in the error message; (4) 'Multiple classes found for path \"X\" in the registry' "
                "means class X is declared with `class X(Base)` more than once — you've been given "
                "EVERY file that declares it, not just the model file, because the real second "
                "declaration is often NOT in src/models/ at all (seen directly: a repository file "
                "redundantly re-declared the full ORM model inline instead of importing the real "
                "one from src/models/); delete the redundant declaration and import the real model "
                "class instead — do not just rename one copy or add __table_args__ = "
                "{\"extend_existing\": True}, neither actually resolves the registry ambiguity. If the error is some "
                "OTHER SQLAlchemy configuration exception not described above, you've still been "
                "given every model file — apply the same reasoning: find the actual mismatch "
                "between how two models reference each other, not a made-up unrelated change."
            ),
            role="Python/FastAPI/SQLAlchemy",
        )

    def _widen_python_repair_context(self, touched_paths: set[str], cap: int = 20) -> set[str]:
        """Python analogue of _widen_java_repair_context: follow each touched
        file's own `from src.(models|repositories|services)...import ...`
        lines so the LLM sees what it depends on, not just what the
        traceback happened to name."""
        related: set[str] = set()
        for p in touched_paths:
            content = self.files.get(p, "")
            for m in re.finditer(r"from\s+src\.(models|repositories|services)(?:\.(\w+))?\s+import\s+([^\n]+)",
                                  content):
                pkg, module, names = m.group(1), m.group(2), m.group(3)
                if module:
                    candidate = f"src/{pkg}/{module}.py"
                    if candidate in self.files:
                        related.add(candidate)
                else:
                    for name in re.split(r",\s*", names):
                        name = name.strip().split(" as ")[0]
                        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
                        candidate = f"src/{pkg}/{snake}.py"
                        if candidate in self.files:
                            related.add(candidate)
        all_paths = touched_paths | related
        if len(all_paths) > cap:
            all_paths = touched_paths | set(list(related)[: max(0, cap - len(touched_paths))])
        return all_paths

    def _boot_check_and_repair_python(self, max_attempts: int = 6) -> bool:
        """
        Importing the entry module isn't enough — reproduced directly: a
        project imported cleanly (every route/service/repository/model
        loaded without error) but every single request failed with a 500,
        because the repository layer was written entirely with a
        synchronous SQLAlchemy Session while database.py set up an async
        engine/session instead — the mismatch only throws once a request
        actually reaches a repository call, which the import check has no
        way to trigger. On top of that, this same project never called
        Base.metadata.create_all(...) anywhere, so its .db file didn't even
        exist — also invisible without a real request. Mirrors the Java
        boot-check's shape: start the app for real on a throwaway port and
        fire actual requests at it, then repair off whatever it does.
        """
        if not self.project_dir:
            return False
        self._p("crew:Verifying the generated Python project's endpoints actually work...")
        for attempt in range(1, max_attempts + 1):
            ok, error_text = self._run_python_boot_check()
            if ok:
                if attempt > 1:
                    self._p(f"skill:Endpoints respond cleanly after {attempt - 1} automatic repair pass(es)")
                else:
                    self._p("skill:Endpoints respond cleanly")
                return True
            self._p(f"skill:Boot/route check failed (attempt {attempt}/{max_attempts})")
            if attempt == max_attempts:
                break
            if not self._repair_python_boot_error(error_text):
                self._p("skill:Automatic repair produced no usable fix — giving up")
                break
            self._flush_to_disk()
            # The fix just edited Python files too — recheck the import
            # before spending another full boot attempt (much slower) on
            # code that can't even import. max_attempts=2, not a bare check:
            # same reasoning as the Java boot-check's identical fix — a
            # single-attempt "check" can only ever detect a broken import,
            # never repair it, since its own loop's attempt budget is
            # already exhausted by the time it would try.
            if not self._import_check_and_repair_python(max_attempts=2):
                self._p("skill:Repair broke the import — giving up")
                break
        self._p("skill:WARNING — some endpoints may still fail; check api_server.log "
                 "after Start for what still needs fixing")
        return False

    def _run_python_boot_check(self, timeout: int = 30) -> tuple[bool, str]:
        """
        Start the app for real on a throwaway port — never the project's
        own assigned port, since this runs during generate()/refine()
        itself, before any real Start call. Once up, discover real GET
        endpoints via the app's own OpenAPI spec and hit every one of the
        simplest ones (no path params — skips {id}-style routes, which need
        made-up values that could themselves 404/422 for reasons unrelated
        to code correctness). Every no-path-param GET gets hit, not a
        capped sample — reproduced directly: a 5-endpoint cap let a
        project's /api/students list route go untested (its 500 only
        surfaced later, on a real user request) purely because two other
        entities' list+aggregate routes happened to fill the cap first;
        the actual cost of testing all of them instead is a few extra local
        HTTP round-trips once per generation/refine, not a per-request
        runtime cost. Authenticates
        every request with the project's real Basic Auth credentials from
        its own .env, read directly rather than relying on os.environ,
        since this subprocess's env is a copy of THIS process's, not
        necessarily the generated app's real deployed credentials.
        """
        import base64 as _b64
        import json as _json
        import subprocess
        import sys
        import tempfile
        import time as _time
        import urllib.error as _ue
        import urllib.request as _ur
        from agents.uigen_agent import _port_is_free

        port = 19100
        while not _port_is_free(port):
            port += 1

        creds_user, creds_pass = "admin", "changeme"
        env_file = self.project_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("API_BASIC_AUTH_USERNAME="):
                    creds_user = line.split("=", 1)[1].strip()
                elif line.startswith("API_BASIC_AUTH_PASSWORD="):
                    creds_pass = line.split("=", 1)[1].strip()
        auth_header = "Basic " + _b64.b64encode(f"{creds_user}:{creds_pass}".encode()).decode()

        log_path = Path(tempfile.gettempdir()) / f"py_boot_check_{self.project_dir.name}_{port}.log"
        env = dict(os.environ)
        proc = None
        try:
            with open(log_path, "w", encoding="utf-8") as log_file:
                cmd = [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)]
                kwargs: dict = {"cwd": str(self.project_dir), "env": env, "stdout": log_file, "stderr": log_file}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen(cmd, **kwargs)

            deadline = _time.time() + timeout
            up = False
            while _time.time() < deadline:
                if proc.poll() is not None:
                    break
                try:
                    _ur.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                    up = True
                    break
                except _ue.HTTPError:
                    up = True
                    break
                except Exception:
                    _time.sleep(0.5)
            if not up:
                log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
                return False, (log_text[-6000:] or "App did not start within timeout")

            try:
                req = _ur.Request(f"http://127.0.0.1:{port}/openapi.json", headers={"Authorization": auth_header})
                spec = _json.loads(_ur.urlopen(req, timeout=5).read())
            except Exception:
                spec = {}
            paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
            for path, methods in paths.items():
                if "{" in path or not isinstance(methods, dict) or "get" not in methods:
                    continue
                try:
                    req = _ur.Request(f"http://127.0.0.1:{port}{path}", headers={"Authorization": auth_header})
                    _ur.urlopen(req, timeout=8)
                except _ue.HTTPError as e:
                    if e.code >= 500:
                        log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
                        return False, log_text[-6000:]
                    # 4xx here (401/404/422/...) isn't the code-correctness bug this check
                    # is meant to catch — only a 5xx means the app itself broke.
                except Exception:
                    pass
            return True, ""
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=8)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            log_path.unlink(missing_ok=True)

