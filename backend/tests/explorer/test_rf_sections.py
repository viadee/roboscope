"""Section-header recognition (GitHub #58).

The explorer used to detect sections with `line.lower().startswith("*** keyword")`,
which recognises exactly one of the spellings Robot Framework accepts. Every
other valid form fell through to the generic `startswith("***")` branch, which
CLOSED the section — so valid files yielded no keywords, no test cases, no tags
and a test count of 0.

Each positive case here is a form RF 7.x parses successfully; each negative case
is one RF rejects. Being more permissive than RF would be its own bug — the
explorer would advertise keywords RF refuses to resolve at run time.
"""

import pytest

from src.explorer.rf_sections import (
    KEYWORDS,
    SETTINGS,
    TASKS,
    TEST_CASES,
    VARIABLES,
    build_section_matcher,
    declared_languages,
    is_section_start,
)


def kind_of(line: str, content: str | None = None) -> str | None:
    """Match a single line, optionally in the context of a whole file."""
    return build_section_matcher(content if content is not None else line)(line)


class TestAsteriskAndSpacingForms:
    @pytest.mark.parametrize(
        "line",
        [
            "*** Keywords ***",
            "***Keywords***",
            "**** Keywords ****",
            "* Keywords",
            "*** Keywords",
            "***   Keywords   ***",
            "*** keywords ***",
            "*** KEYWORDS ***",
            "*** Keyword ***",  # RF accepts the singular
            "  *** Keywords ***  ",  # leading/trailing whitespace on the line
        ],
    )
    def test_recognised_keyword_headers(self, line):
        assert kind_of(line) == KEYWORDS

    @pytest.mark.parametrize(
        "line,expected",
        [
            ("*** Settings ***", SETTINGS),
            ("*** Setting ***", SETTINGS),
            ("*** Variables ***", VARIABLES),
            ("*** Test Cases ***", TEST_CASES),
            ("*** Test Case ***", TEST_CASES),
            ("*** Tasks ***", TASKS),
        ],
    )
    def test_recognised_other_sections(self, line, expected):
        assert kind_of(line) == expected

    @pytest.mark.parametrize(
        "line",
        [
            "***\tKeywords\t***",  # RF rejects tabs around the name
            "*** Key\twords ***",  # ...and inside it
            "*** Bogus ***",  # not a section name at all
            "***",  # asterisks with no name
            "*",
            "Keywords",  # no asterisk → ordinary line
            "    Log    hello",
            "",
        ],
    )
    def test_rejected(self, line):
        assert kind_of(line) is None


class TestByteOrderMark:
    """A BOM rides on the first line — exactly where a `.resource` file puts
    its `*** Keywords ***`, so it used to wipe out the whole file."""

    def test_bom_before_header_is_ignored(self):
        assert kind_of("﻿*** Keywords ***") == KEYWORDS

    def test_bom_before_settings_is_ignored(self):
        assert kind_of("﻿*** Settings ***") == SETTINGS


class TestLocalisedHeaders:
    """RF honours translated headers only when the file declares `Language:`
    before its first section — so the matcher is built per file, not per line."""

    def test_chinese_header_with_declaration(self):
        content = "Language: zh-CN\n\n*** 关键字 ***\nK\n"
        assert kind_of("*** 关键字 ***", content) == KEYWORDS

    def test_german_header_with_language_code(self):
        content = "Language: de\n\n*** Schlüsselwörter ***\nK\n"
        assert kind_of("*** Schlüsselwörter ***", content) == KEYWORDS

    def test_german_header_with_language_name(self):
        content = "Language: German\n\n*** Schlüsselwörter ***\nK\n"
        assert kind_of("*** Schlüsselwörter ***", content) == KEYWORDS

    def test_localised_header_without_declaration_is_rejected(self):
        # RF rejects this too — matching it would advertise keywords RF cannot
        # resolve.
        assert kind_of("*** Schlüsselwörter ***", "*** Schlüsselwörter ***\n") is None

    def test_english_still_works_in_a_localised_file(self):
        content = "Language: zh-CN\n\n*** Keywords ***\nK\n"
        assert kind_of("*** Keywords ***", content) == KEYWORDS

    def test_unknown_language_falls_back_to_english(self):
        content = "Language: Klingon\n\n*** Keywords ***\nK\n"
        assert kind_of("*** Keywords ***", content) == KEYWORDS


class TestDeclaredLanguages:
    def test_reads_declaration_above_first_section(self):
        assert declared_languages("Language: de\n\n*** Keywords ***\n") == ["de"]

    def test_ignores_declaration_after_the_first_section(self):
        # RF only honours it in the preamble.
        content = "*** Keywords ***\nK\n    Log    Language: de\n"
        assert declared_languages(content) == []

    def test_multiple_declarations_are_additive(self):
        content = "Language: de\nLanguage: fi\n\n*** Keywords ***\n"
        assert declared_languages(content) == ["de", "fi"]

    def test_no_declaration(self):
        assert declared_languages("*** Keywords ***\nK\n") == []


class TestIsSectionStart:
    """Any `*`-leading line closes the current section, recognised or not —
    otherwise an unknown `*** Foo ***` would leak the previous section's body."""

    @pytest.mark.parametrize(
        "line", ["*** Keywords ***", "* Keywords", "*** Bogus ***", "***", "﻿*** Settings ***"]
    )
    def test_section_starts(self, line):
        assert is_section_start(line) is True

    @pytest.mark.parametrize("line", ["My Keyword", "    Log    x", "", "# comment"])
    def test_not_section_starts(self, line):
        assert is_section_start(line) is False
