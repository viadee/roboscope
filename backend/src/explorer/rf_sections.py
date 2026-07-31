"""Robot Framework section-header recognition for the explorer's file parsers.

The explorer scans `.robot` / `.resource` files line by line (rather than
building RF's full AST) to stay fast enough for whole-repo sweeps. Section
detection used to be `line.lower().startswith("*** keyword")`, which accepts
exactly ONE of the spellings Robot Framework considers valid. Every other form
fell through to the generic `startswith("***")` branch, which *closed* the
section — so a perfectly valid file silently yielded no keywords, no test
cases, no tags and a test count of 0 (GitHub #58).

Forms RF accepts, verified against RF 7.4.2:

    *** Keywords ***      ***Keywords***      **** Keywords ****
    * Keywords            *** Keywords        *** keyword ***   (singular)

plus a leading UTF-8 BOM, and — when the file declares `Language: <name|code>`
before its first section — that language's translated header names.

Deliberately NOT accepted, because RF rejects them too:

    ***\tKeywords\t***    (tabs around the name)
    *** Schlüsselwörter ***  in a file with no `Language:` declaration

Being *more* permissive than RF would be its own bug: the explorer would list
keywords that RF refuses to resolve at run time.

Translated names come from `robot.conf.languages` rather than a table
maintained here, so a new RF release's languages are picked up for free.
`robotframework` is a hard backend dependency, so this import is always safe.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from robot.conf.languages import Languages

SETTINGS = "settings"
VARIABLES = "variables"
TEST_CASES = "test_cases"
TASKS = "tasks"
KEYWORDS = "keywords"
COMMENTS = "comments"

# RF accepts singular and plural for every section name.
_ENGLISH: dict[str, str] = {
    "settings": SETTINGS,
    "setting": SETTINGS,
    "variables": VARIABLES,
    "variable": VARIABLES,
    "test cases": TEST_CASES,
    "test case": TEST_CASES,
    "tasks": TASKS,
    "task": TASKS,
    "keywords": KEYWORDS,
    "keyword": KEYWORDS,
    "comments": COMMENTS,
    "comment": COMMENTS,
}

# `*`+ then the name, then optional closing `*`+. Only SPACES may pad the name
# (RF rejects tabs there). `[^*]` keeps the name from swallowing the closing
# run of asterisks.
_HEADER_RE = re.compile(r"^\*+ *(?P<name>[^*]*?) *\**$")

_LANGUAGE_RE = re.compile(r"^language:\s*(?P<lang>\S.*?)\s*$", re.IGNORECASE)

_BOM = "﻿"


def _normalize(name: str) -> str:
    """Case- and whitespace-insensitive key, matching how RF compares names."""
    return " ".join(name.split()).lower()


def _strip(line: str) -> str:
    """Trim whitespace and a leading BOM.

    The BOM only ever rides on the first line of a file, but that is exactly
    where a `.resource` file puts its `*** Keywords ***` header — so a BOM used
    to wipe out the entire file's keywords.
    """
    return line.strip().lstrip(_BOM).strip()


def declared_languages(content: str) -> list[str]:
    """Return the `Language:` tokens declared before the first section header.

    RF only honours the declaration above the first section, and accepts either
    a language name (`German`) or a code (`de`). Multiple declarations are
    allowed and additive.
    """
    tokens: list[str] = []
    for line in content.splitlines():
        stripped = _strip(line)
        if not stripped:
            continue
        if stripped.startswith("*"):
            break
        match = _LANGUAGE_RE.match(stripped)
        if match:
            tokens.append(match.group("lang"))
    return tokens


def _header_map(language_tokens: list[str]) -> dict[str, str]:
    """English names plus, for each declared language, its translated names."""
    mapping = dict(_ENGLISH)
    if not language_tokens:
        return mapping
    try:
        languages = Languages(language_tokens)
    except Exception:
        # An unknown / misspelled language must not break parsing — English
        # headers still resolve, which is what RF does as well.
        return mapping
    for translated, english in languages.headers.items():
        kind = _ENGLISH.get(_normalize(english))
        if kind:
            mapping[_normalize(translated)] = kind
    return mapping


def build_section_matcher(content: str) -> Callable[[str], str | None]:
    """Return `match(line) -> section kind | None` for one file's content.

    The file is pre-scanned once for its `Language:` declaration, so the
    returned matcher is a cheap dict lookup per line.

    A line that starts with `*` but names no known section returns `None` like
    any other non-header line. Callers therefore still need the
    `startswith("*")` check to close the section they are in — see
    `is_section_start`.
    """
    headers = _header_map(declared_languages(content))

    def match(line: str) -> str | None:
        stripped = _strip(line)
        if not stripped.startswith("*"):
            return None
        header = _HEADER_RE.match(stripped)
        if header is None:
            return None
        raw_name = header.group("name")
        # Only plain spaces may pad or separate the name. The regex above eats
        # spaces, so any whitespace still sitting in the capture is a tab (or
        # similar) — which RF rejects, and so must we.
        if any(ch.isspace() and ch != " " for ch in raw_name):
            return None
        name = raw_name.strip()
        if not name:
            return None
        return headers.get(_normalize(name))

    return match


def is_section_start(line: str) -> bool:
    """Does this line open *some* section (recognised or not)?

    Any `*`-leading line ends whatever section the scanner is in, mirroring the
    previous `startswith("***")` behaviour but without demanding three
    asterisks.
    """
    return _strip(line).startswith("*")
