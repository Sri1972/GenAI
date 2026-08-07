"""
Centralized JS/TS string sanitizer.

Fixes ALL classes of problematic characters that break esbuild/Vite/TS parsing
when the LLM produces them in code. This is the SINGLE source of truth for
character sanitization — every code-writing path must call `sanitize()` or
`sanitize_files()` before writing to disk.

Categories handled:
1. Word-internal apostrophes (India's → India’s)
2. Fancy/smart quotes that break string delimiters
3. En-dash and em-dash in contexts that break parsing
4. Invisible/zero-width characters that cause silent failures
5. Emojis inside string literals (safe in template literals/JSX text, but
   can break single/double quoted strings in object literals)
6. Non-breaking spaces that look like regular spaces but aren't
7. Other Unicode control characters
"""

import re

# ── Character replacement maps ───────────────────────────────────────────────

# Unicode right single quote — safe replacement for possessive/contraction apostrophes
_RSQ = chr(0x2019)

# Problematic characters → safe replacements
_CHAR_MAP = {
    " ": " ",       # Non-breaking space → regular space
    "​": "",        # Zero-width space → remove
    "‌": "",        # Zero-width non-joiner → remove
    "‍": "",        # Zero-width joiner → remove
    "﻿": "",        # BOM / zero-width no-break space → remove
    " ": "\\n",     # Line separator → newline escape
    " ": "\\n",     # Paragraph separator → newline escape
    "­": "",        # Soft hyphen → remove
    "\u200E": "",        # Left-to-right mark → remove
    "\u200F": "",        # Right-to-left mark → remove
    "\u202A": "",        # Left-to-right embedding → remove
    "\u202B": "",        # Right-to-left embedding → remove
    "\u202C": "",        # Pop directional formatting → remove
    "\u202D": "",        # Left-to-right override → remove
    "\u202E": "",        # Right-to-left override → remove
}

# Smart/fancy quotes that the LLM may use that break JS if mixed with delimiters
_QUOTE_MAP = {
    "“": '"',       # Left double quote → regular double quote
    "”": '"',       # Right double quote → regular double quote
    "‘": "'",       # Left single quote → regular apostrophe
    # Note: ’ (right single quote) is deliberately NOT mapped —
    # we USE it as a safe replacement for possessive apostrophes
}

# Pattern: letter + apostrophe + letter (possessive/contraction in English)
_APOSTROPHE_RE = re.compile(r"([a-zA-Z])'([a-zA-Z])")

# Invisible/zero-width characters regex (for removal)
_INVISIBLE_RE = re.compile(
    "[​‌‍﻿­\u200E\u200F"
    "\u202A\u202B\u202C\u202D\u202E⁠⁡⁢⁣⁤]"
)

# Non-breaking space
_NBSP_RE = re.compile(" ")

# Line/paragraph separators (break JS parsing if inside a string)
_LINE_SEP_RE = re.compile("[  ]")

# Emoji pattern — comprehensive coverage of ALL Unicode emoji blocks.
# Uses the full Supplementary Multilingual Plane range (U+1F000–U+1FAFF) which
# covers all current and future emoji allocations. Also covers BMP emoji-like
# symbols that can break JS string parsing.
# We only strip emojis from SINGLE-QUOTED and DOUBLE-QUOTED string values,
# not from template literals or JSX text where they're usually safe.
_EMOJI_RE = re.compile(
    "["
    "\U0000200D"             # ZWJ (glues compound emoji sequences)
    "\U0000FE00-\U0000FE0F"  # variation selectors (emoji vs text presentation)
    "\U00002600-\U000027BF"  # misc symbols, dingbats (☀️, ✂️, ⚡, etc.)
    "\U0001F000-\U0001FAFF"  # ALL SMP emoji: emoticons, symbols, pictographs,
                             # transport, flags, food, animals, activities,
                             # supplemental, extended-A, chess, etc.
    "\U000024C2-\U000024FF"  # enclosed alphanumerics (Ⓜ️ etc.)
    "\U0000E000-\U0000F8FF"  # private-use area (custom emoji from some systems)
    "\U000020E3"             # combining enclosing keycap
    "]+",
    re.UNICODE
)


def sanitize(content: str, file_path: str = "") -> str:
    """
    Sanitize a single file's content for safe JS/TS/JSX parsing.

    Args:
        content: The file content string
        file_path: The relative file path (used to determine file type)

    Returns:
        Sanitized content safe for esbuild/Vite/TypeScript
    """
    if not content or not isinstance(content, str):
        return content

    is_code_file = file_path.endswith((".ts", ".tsx", ".js", ".jsx"))
    is_json_file = file_path.endswith(".json")

    if not is_code_file and not is_json_file:
        return content

    # 1. Remove invisible/zero-width characters (always harmful in code)
    content = _INVISIBLE_RE.sub("", content)

    # 2. Replace non-breaking spaces with regular spaces
    content = _NBSP_RE.sub(" ", content)

    # 3. Replace line/paragraph separators (break string literals)
    content = _LINE_SEP_RE.sub("\\n", content)

    if is_code_file:
        # 4. Fix word-internal apostrophes (letter'letter → letter’letter)
        #    This pattern is NEVER valid JS — always a possessive/contraction
        #    inside a single-quoted string that will break parsing
        content = _APOSTROPHE_RE.sub(r"\1" + _RSQ + r"\2", content)

        # 5. Fix smart/fancy opening quotes that break string delimiters
        for bad_char, replacement in _QUOTE_MAP.items():
            if bad_char in content:
                content = content.replace(bad_char, replacement)

        # 6. Strip emojis from single-quoted and double-quoted string values
        #    (they're safe in template literals and JSX text)
        content = _strip_emojis_from_quoted_strings(content)

        # 7. Fix D3 class selectors that use raw data labels (breaks on special chars)
        content = _fix_d3_class_selectors(content)

    if is_json_file:
        # JSON: fix all smart quotes to regular, fix apostrophes
        content = _APOSTROPHE_RE.sub(r"\1" + _RSQ + r"\2", content)
        for bad_char, replacement in _QUOTE_MAP.items():
            if bad_char in content:
                content = content.replace(bad_char, replacement)
        # Right single quote is fine in JSON string values (inside double quotes)

    return content


def _strip_emojis_from_quoted_strings(content: str) -> str:
    """
    Remove emojis ONLY from inside single-quoted and double-quoted strings.
    Template literals (backtick) and JSX text are left alone — emojis render
    fine there.
    """
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if not _EMOJI_RE.search(line):
            continue
        # Only strip emojis from lines that look like quoted string values
        # (inside object literals, variable assignments, etc.)
        stripped = line.lstrip()
        # Lines that are clearly string values in objects/arrays
        is_quoted_value = (
            stripped.startswith("'") or
            stripped.startswith('"') or
            "': '" in line or
            '": "' in line or
            "= '" in line or
            '= "' in line
        )
        # Don't touch JSX text content or template literals
        is_safe_context = (
            stripped.startswith("`") or
            stripped.startswith("<") or
            stripped.startswith("{`") or
            ">`" in line
        )
        if is_quoted_value and not is_safe_context:
            lines[i] = _EMOJI_RE.sub("", line)
    return "\n".join(lines)


def _fix_d3_class_selectors(content: str) -> str:
    """
    Fix D3 code that builds CSS selectors from data labels using only
    .replace(/\\s/g, '-'). Labels with (, ), %, $, #, etc. produce invalid
    selectors like '.dot-EV-Mix-(%)'. Replace with a full sanitize that
    strips all non-alphanumeric/hyphen characters.
    """
    # Pattern: .replace(/\s/g, '-') or .replace(/ /g, '-') used in selector context
    # Replace with .replace(/[^a-zA-Z0-9-]/g, '') which strips all unsafe chars
    # Note: \s in the file is a literal backslash + s (one char each in the .tsx source)
    old_patterns = [
        ".replace(/\x5cs/g, '-')",    # \s with single quotes
        '.replace(/\x5cs/g, "-")',    # \s with double quotes
        ".replace(/ /g, '-')",        # space literal with single quotes
        '.replace(/ /g, "-")',        # space literal with double quotes
    ]
    safe_replace = ".replace(/[^a-zA-Z0-9-]/g, '')"
    for old in old_patterns:
        if old in content:
            content = content.replace(old, safe_replace)
    return content


def sanitize_files(files: dict) -> dict:
    """
    Sanitize all JS/TS/JSON files in a files dict.
    This is the primary entry-point for batch sanitization.

    Args:
        files: dict mapping relative path → file content

    Returns:
        The same dict with sanitized content
    """
    for path in list(files.keys()):
        content = files[path]
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
            files[path] = content
        if not isinstance(content, str):
            continue
        sanitized = sanitize(content, path)
        if sanitized != content:
            files[path] = sanitized
    return files
