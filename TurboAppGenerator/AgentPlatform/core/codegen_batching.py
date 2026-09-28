"""
Reusable per-entity code-generation batching helpers.

Extracted from WebAPIGenerator/api_agents/api_orchestrator.py, where this
machinery was first built and proven (adaptive batch-size shrinking on
failure, and the "non-empty response != complete response" per-entity
completeness check). Shared so WebUIGenerator's own per-entity ORM
generation (see WebUIGenerator/agents/orchestrator.py) reuses the identical,
already-battle-tested logic instead of a second copy.
"""

import re


def snake_case(name: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return re.sub(r"[^a-z0-9_]", "_", s).strip("_") or "entity"


def expected_model_path(entity_name: str, language: str) -> str:
    """Where a given entity's model file should land, per the established
    convention (com.api.model.<Name> for Java, snake_case under src/models/
    for Python) — used to verify a data-modeling batch actually produced a
    file for every entity it was asked for, not just SOME non-empty content."""
    if language == "java":
        return f"src/main/java/com/api/model/{entity_name}.java"
    return f"src/models/{snake_case(entity_name)}.py"


def expected_route_path(entity_name: str, language: str) -> str:
    """Where a given entity's route (Python) or controller (Java) file
    should land — used to verify an entity-implementation batch actually
    produced the one file every one of its endpoints depends on being
    wired."""
    if language == "java":
        return f"src/main/java/com/api/controller/{entity_name}Controller.java"
    return f"src/routes/{snake_case(entity_name)}.py"


def missing_expected_files(batch_names, expected_path_fn, batch_files, also_check=None) -> list[str]:
    """Which of batch_names' expected files (per expected_path_fn) are
    absent from batch_files — and, if also_check is given, also absent from
    it (e.g. self.files, so a file produced by an earlier sub-batch still
    counts as present)."""
    missing = []
    for name in batch_names:
        path = expected_path_fn(name)
        if path in batch_files:
            continue
        if also_check is not None and path in also_check:
            continue
        missing.append(name)
    return missing


def shrink_until_success(batch: list, run_batch, min_size: int,
                          on_final_failure=None, log=None) -> list:
    """
    Try run_batch(batch); if it fails (returns None/falsy — after
    run_batch's own internal retry, if it has one), split the batch in half
    and recurse on each half independently, down to min_size if necessary,
    instead of retrying the exact same oversized ask or giving up on the
    whole batch outright. A batch sized for most projects can still be too
    much for one that's especially large or especially data-heavy in its
    requirements — there is no fixed size that's correct for every project,
    so this makes the size adapt to whatever actually fails, rather than
    needing to be guessed upfront.
    """
    result = run_batch(batch)
    if result:
        return [result]
    if len(batch) <= min_size:
        if on_final_failure:
            on_final_failure(batch)
        return []
    mid = len(batch) // 2
    if log:
        log(f"skill:Batch of {len(batch)} still failed at this size — "
            f"splitting into {mid} + {len(batch) - mid} and retrying independently")
    return (shrink_until_success(batch[:mid], run_batch, min_size, on_final_failure, log)
            + shrink_until_success(batch[mid:], run_batch, min_size, on_final_failure, log))


def run_with_adaptive_batching(items: list, run_batch, initial_size: int,
                                min_size: int = 1, on_final_failure=None, log=None) -> list:
    """Chunk `items` into initial_size-sized pieces, then shrink only the
    specific chunks that actually fail (see shrink_until_success) — chunks
    that succeed at the initial size are never touched again."""
    chunks = [items[i:i + initial_size] for i in range(0, len(items), initial_size)]
    results = []
    for chunk in chunks:
        results.extend(shrink_until_success(chunk, run_batch, min_size, on_final_failure, log))
    return results


# Coarse SQL type categories, shared between WebAPIGenerator's schema/entity
# type reconciliation (api_orchestrator.py — corrects schema.sql to match
# the ORM entity that actually gets materialized) and WebUIGenerator's
# seed-vs-live-schema check (uigen_agent.py — flags a seed value that can't
# possibly fit the REAL, already-booted database's column type). Both need
# the exact same "is this a numeric-ish type or a text-ish type" judgment;
# keeping one copy here means they can't independently drift into
# disagreeing about it, the same class of bug this whole feature exists to
# close everywhere else.
SQL_TYPE_CATEGORY = {
    "integer": "integer", "int": "integer", "bigint": "integer", "smallint": "integer",
    "tinyint": "integer", "boolean": "integer", "bool": "integer",
    "real": "real", "float": "real", "double": "real", "numeric": "real", "decimal": "real",
    "text": "text", "varchar": "text", "char": "text", "clob": "text", "nvarchar": "text",
    "blob": "blob",
}


def sql_type_category(sql_type: str) -> str | None:
    """Coarse category ('integer'/'real'/'text'/'blob') for a raw SQL type
    word, or None if unrecognized. Strips any `(...)` precision/length
    suffix (e.g. `VARCHAR(255)` -> `varchar`) before looking it up."""
    word = re.match(r"\s*(\w+)", sql_type or "")
    return SQL_TYPE_CATEGORY.get(word.group(1).lower()) if word else None
