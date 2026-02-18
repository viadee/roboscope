"""Tests for explorer service: filesystem traversal, Robot file parsing."""

import pytest

from src.explorer.service import (
    build_tree,
    check_libraries_against_env,
    extract_libraries,
    list_all_testcases,
    parse_robot_testcases,
    read_file,
    search_in_repo,
)

SAMPLE_ROBOT = """\
*** Settings ***
Library    Browser

*** Test Cases ***
Login With Valid Credentials
    [Documentation]    Verify valid login works
    [Tags]    smoke    auth
    Open Browser    https://example.com    chromium
    Fill Text    id=username    admin
    Fill Text    id=password    secret
    Click    id=login
    Get Text    id=welcome    ==    Welcome, admin

Login With Invalid Password
    [Tags]    negative    auth
    Open Browser    https://example.com    chromium
    Fill Text    id=username    admin
    Fill Text    id=password    wrong
    Click    id=login
    Get Text    id=error    ==    Invalid credentials

*** Keywords ***
Custom Keyword
    Log    Hello
"""

SAMPLE_ROBOT_RESOURCE = """\
*** Settings ***
Library    Collections

*** Keywords ***
My Resource Keyword
    [Documentation]    A reusable keyword
    Log    resource keyword
"""


def _create_repo_structure(tmp_path):
    """Create a sample repo structure for testing.

    Structure:
        tmp_path/
            suites/
                login.robot        (2 test cases)
                api_tests.robot    (1 test case)
            resources/
                common.resource
            .git/                  (should be ignored)
                config
            README.md
    """
    suites = tmp_path / "suites"
    suites.mkdir()
    (suites / "login.robot").write_text(SAMPLE_ROBOT)
    (suites / "api_tests.robot").write_text(
        "*** Test Cases ***\nAPI Health Check\n    Log    OK\n"
    )

    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "common.resource").write_text(SAMPLE_ROBOT_RESOURCE)

    # Ignored directories
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    (tmp_path / "README.md").write_text("# Test Repo\n")


class TestBuildTree:
    def test_build_tree_returns_root_directory(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        assert tree.type == "directory"
        assert tree.path == "."
        assert tree.children is not None

    def test_build_tree_contains_subdirectories(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        child_names = [c.name for c in tree.children]
        assert "suites" in child_names
        assert "resources" in child_names

    def test_build_tree_ignores_git_directory(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        child_names = [c.name for c in tree.children]
        assert ".git" not in child_names

    def test_build_tree_contains_files(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        suites_node = next(c for c in tree.children if c.name == "suites")
        file_names = [c.name for c in suites_node.children]
        assert "login.robot" in file_names
        assert "api_tests.robot" in file_names

    def test_build_tree_counts_tests_in_robot_files(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        suites_node = next(c for c in tree.children if c.name == "suites")
        login_file = next(c for c in suites_node.children if c.name == "login.robot")
        assert login_file.test_count == 2

        api_file = next(c for c in suites_node.children if c.name == "api_tests.robot")
        assert api_file.test_count == 1

    def test_build_tree_counts_tests_recursively_in_directory(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        suites_node = next(c for c in tree.children if c.name == "suites")
        # suites dir contains login.robot (2) + api_tests.robot (1) = 3
        assert suites_node.test_count == 3

    def test_build_tree_files_have_extensions(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        suites_node = next(c for c in tree.children if c.name == "suites")
        login_file = next(c for c in suites_node.children if c.name == "login.robot")
        assert login_file.extension == ".robot"
        assert login_file.type == "file"

    def test_build_tree_with_relative_path(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path), "suites")

        assert tree.name == "suites"
        assert tree.type == "directory"
        child_names = [c.name for c in tree.children]
        assert "login.robot" in child_names

    def test_build_tree_nonexistent_directory(self, tmp_path):
        tree = build_tree(str(tmp_path / "nonexistent"))
        assert tree.type == "directory"
        assert tree.children == []

    def test_build_tree_directories_sorted_before_files(self, tmp_path):
        _create_repo_structure(tmp_path)
        tree = build_tree(str(tmp_path))

        types = [c.type for c in tree.children]
        # All directories should come before files
        dir_indices = [i for i, t in enumerate(types) if t == "directory"]
        file_indices = [i for i, t in enumerate(types) if t == "file"]
        if dir_indices and file_indices:
            assert max(dir_indices) < min(file_indices)


class TestReadFile:
    def test_read_file_returns_content(self, tmp_path):
        _create_repo_structure(tmp_path)
        result = read_file(str(tmp_path), "suites/login.robot")

        assert result.name == "login.robot"
        assert result.path == "suites/login.robot"
        assert result.extension == ".robot"
        assert "Login With Valid Credentials" in result.content
        assert result.line_count > 0

    def test_read_file_correct_line_count(self, tmp_path):
        content = "line1\nline2\nline3\n"
        (tmp_path / "test.txt").write_text(content)
        result = read_file(str(tmp_path), "test.txt")

        assert result.line_count == 3

    def test_read_file_blocks_path_traversal(self, tmp_path):
        _create_repo_structure(tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            read_file(str(tmp_path), "../../../etc/passwd")

    def test_read_file_blocks_path_traversal_encoded(self, tmp_path):
        _create_repo_structure(tmp_path)
        with pytest.raises(ValueError, match="Path traversal detected"):
            read_file(str(tmp_path), "suites/../../etc/passwd")

    def test_read_file_not_found(self, tmp_path):
        _create_repo_structure(tmp_path)
        with pytest.raises(FileNotFoundError):
            read_file(str(tmp_path), "nonexistent.robot")

    def test_read_file_resource_file(self, tmp_path):
        _create_repo_structure(tmp_path)
        result = read_file(str(tmp_path), "resources/common.resource")

        assert result.name == "common.resource"
        assert result.extension == ".resource"
        assert "My Resource Keyword" in result.content


class TestParseRobotTestcases:
    def test_parse_finds_all_testcases(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        assert len(testcases) == 2
        names = [tc.name for tc in testcases]
        assert "Login With Valid Credentials" in names
        assert "Login With Invalid Password" in names

    def test_parse_extracts_tags(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        valid_login = next(tc for tc in testcases if tc.name == "Login With Valid Credentials")
        assert "smoke" in valid_login.tags
        assert "auth" in valid_login.tags

        invalid_login = next(tc for tc in testcases if tc.name == "Login With Invalid Password")
        assert "negative" in invalid_login.tags
        assert "auth" in invalid_login.tags

    def test_parse_extracts_documentation(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        valid_login = next(tc for tc in testcases if tc.name == "Login With Valid Credentials")
        assert valid_login.documentation == "Verify valid login works"

    def test_parse_extracts_suite_name(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        for tc in testcases:
            assert tc.suite_name == "login"

    def test_parse_extracts_file_path(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        for tc in testcases:
            assert tc.file_path == "suites/login.robot"

    def test_parse_extracts_line_numbers(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = parse_robot_testcases(str(tmp_path), "suites/login.robot")

        for tc in testcases:
            assert tc.line_number > 0

        # First test case should have a lower line number than the second
        valid_login = next(tc for tc in testcases if tc.name == "Login With Valid Credentials")
        invalid_login = next(tc for tc in testcases if tc.name == "Login With Invalid Password")
        assert valid_login.line_number < invalid_login.line_number

    def test_parse_nonexistent_file_returns_empty(self, tmp_path):
        testcases = parse_robot_testcases(str(tmp_path), "nonexistent.robot")
        assert testcases == []

    def test_parse_file_without_test_section(self, tmp_path):
        (tmp_path / "no_tests.robot").write_text(
            "*** Keywords ***\nSome Keyword\n    Log    Hello\n"
        )
        testcases = parse_robot_testcases(str(tmp_path), "no_tests.robot")
        assert testcases == []


class TestSearchInRepo:
    def test_search_finds_matching_filename(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "login")

        file_results = [r for r in results if r.type == "file" and r.line_number == 0]
        assert len(file_results) >= 1
        assert any(r.name == "login.robot" for r in file_results)

    def test_search_finds_matching_content(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "Valid Credentials")

        assert len(results) >= 1
        assert any("Valid Credentials" in r.name or "Valid Credentials" in r.context for r in results)

    def test_search_finds_testcase_type(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "Login With Valid")

        testcase_results = [r for r in results if r.type == "testcase"]
        assert len(testcase_results) >= 1

    def test_search_with_file_type_filter_robot(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "keyword", file_type="robot")

        # Should only search .robot files, not .resource files
        for r in results:
            assert r.file_path.endswith(".robot")

    def test_search_with_file_type_filter_resource(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "keyword", file_type="resource")

        # Should only search .resource files
        for r in results:
            assert r.file_path.endswith(".resource")

    def test_search_case_insensitive(self, tmp_path):
        _create_repo_structure(tmp_path)
        results_lower = search_in_repo(str(tmp_path), "login")
        results_upper = search_in_repo(str(tmp_path), "LOGIN")

        # Both should find results (case-insensitive search)
        assert len(results_lower) > 0
        assert len(results_upper) > 0

    def test_search_no_results(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "zzz_nonexistent_term_zzz")
        assert results == []

    def test_search_ignores_git_directory(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "core")

        # .git/config contains [core] but should be ignored
        for r in results:
            assert ".git" not in r.file_path

    def test_search_includes_line_numbers(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "Login With Valid Credentials")

        content_results = [r for r in results if r.line_number > 0]
        assert len(content_results) >= 1

    def test_search_includes_context(self, tmp_path):
        _create_repo_structure(tmp_path)
        results = search_in_repo(str(tmp_path), "Login With Valid Credentials")

        content_results = [r for r in results if r.context]
        assert len(content_results) >= 1


class TestListAllTestcases:
    def test_list_all_finds_all_testcases(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = list_all_testcases(str(tmp_path))

        # login.robot has 2 test cases, api_tests.robot has 1 = 3 total
        assert len(testcases) == 3

    def test_list_all_includes_tests_from_multiple_files(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = list_all_testcases(str(tmp_path))

        file_paths = {tc.file_path for tc in testcases}
        assert len(file_paths) == 2

    def test_list_all_testcase_names(self, tmp_path):
        _create_repo_structure(tmp_path)
        testcases = list_all_testcases(str(tmp_path))

        names = [tc.name for tc in testcases]
        assert "Login With Valid Credentials" in names
        assert "Login With Invalid Password" in names
        assert "API Health Check" in names

    def test_list_all_empty_repo(self, tmp_path):
        # No .robot files at all
        testcases = list_all_testcases(str(tmp_path))
        assert testcases == []

    def test_list_all_ignores_git_directory(self, tmp_path):
        _create_repo_structure(tmp_path)
        # Put a .robot file inside .git (should be ignored)
        (tmp_path / ".git" / "hidden.robot").write_text(
            "*** Test Cases ***\nHidden Test\n    Log    secret\n"
        )

        testcases = list_all_testcases(str(tmp_path))
        names = [tc.name for tc in testcases]
        assert "Hidden Test" not in names


SAMPLE_ROBOT_MULTI_LIB = """\
*** Settings ***
Library    Browser
Library    RequestsLibrary
Library    Collections
Library    ./libs/custom.py

*** Test Cases ***
Example
    Log    hello
"""

SAMPLE_RESOURCE_WITH_LIB = """\
*** Settings ***
Library    SeleniumLibrary

*** Keywords ***
Open App
    Log    opening
"""


class TestExtractLibraries:
    def test_extract_from_robot_file(self, tmp_path):
        (tmp_path / "test.robot").write_text(SAMPLE_ROBOT_MULTI_LIB)
        libs = extract_libraries(str(tmp_path))

        lib_names = [l["library_name"] for l in libs]
        assert "Browser" in lib_names
        assert "RequestsLibrary" in lib_names
        assert "Collections" in lib_names
        assert "./libs/custom.py" in lib_names

    def test_extract_from_resource_file(self, tmp_path):
        (tmp_path / "keywords.resource").write_text(SAMPLE_RESOURCE_WITH_LIB)
        libs = extract_libraries(str(tmp_path))

        lib_names = [l["library_name"] for l in libs]
        assert "SeleniumLibrary" in lib_names

    def test_extract_tracks_files(self, tmp_path):
        (tmp_path / "a.robot").write_text(
            "*** Settings ***\nLibrary    Browser\n\n*** Test Cases ***\nT\n    Log    ok\n"
        )
        (tmp_path / "b.robot").write_text(
            "*** Settings ***\nLibrary    Browser\n\n*** Test Cases ***\nT2\n    Log    ok\n"
        )
        libs = extract_libraries(str(tmp_path))

        browser_lib = next(l for l in libs if l["library_name"] == "Browser")
        assert len(browser_lib["files"]) == 2

    def test_extract_ignores_git_dirs(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "test.robot").write_text(
            "*** Settings ***\nLibrary    SeleniumLibrary\n\n*** Test Cases ***\nT\n    Log    ok\n"
        )
        libs = extract_libraries(str(tmp_path))
        assert len(libs) == 0

    def test_extract_empty_repo(self, tmp_path):
        libs = extract_libraries(str(tmp_path))
        assert libs == []

    def test_extract_skips_comments(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\n# Library    FakeLib\nLibrary    Browser\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        libs = extract_libraries(str(tmp_path))
        lib_names = [l["library_name"] for l in libs]
        assert "FakeLib" not in lib_names
        assert "Browser" in lib_names

    def test_extract_with_tab_separator(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary\tBrowser\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        libs = extract_libraries(str(tmp_path))
        lib_names = [l["library_name"] for l in libs]
        assert "Browser" in lib_names


class TestCheckLibrariesAgainstEnv:
    def test_builtin_detected(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary    Collections\nLibrary    String\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        results = check_libraries_against_env(str(tmp_path), [])
        for r in results:
            assert r["status"] == "builtin"

    def test_installed_detected(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary    Browser\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        installed = [{"name": "robotframework-browser", "version": "18.0.0"}]
        results = check_libraries_against_env(str(tmp_path), installed)

        browser = next(r for r in results if r["library_name"] == "Browser")
        assert browser["status"] == "installed"
        assert browser["installed_version"] == "18.0.0"
        assert browser["pypi_package"] == "robotframework-browser"

    def test_missing_detected(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary    SeleniumLibrary\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        results = check_libraries_against_env(str(tmp_path), [])

        selenium = next(r for r in results if r["library_name"] == "SeleniumLibrary")
        assert selenium["status"] == "missing"
        assert selenium["pypi_package"] == "robotframework-seleniumlibrary"

    def test_normalized_package_matching(self, tmp_path):
        """Package names with dashes should match those with underscores."""
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary    RequestsLibrary\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        # pip list often returns names with dashes
        installed = [{"name": "robotframework-requests", "version": "0.9.7"}]
        results = check_libraries_against_env(str(tmp_path), installed)

        req = next(r for r in results if r["library_name"] == "RequestsLibrary")
        assert req["status"] == "installed"

    def test_path_based_import_treated_as_builtin(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\nLibrary    ./libs/custom.py\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        results = check_libraries_against_env(str(tmp_path), [])

        custom = next(r for r in results if r["library_name"] == "./libs/custom.py")
        assert custom["status"] == "builtin"

    def test_mixed_statuses(self, tmp_path):
        (tmp_path / "test.robot").write_text(
            "*** Settings ***\n"
            "Library    Collections\n"
            "Library    Browser\n"
            "Library    SeleniumLibrary\n\n"
            "*** Test Cases ***\nT\n    Log    ok\n"
        )
        installed = [{"name": "robotframework-browser", "version": "18.0.0"}]
        results = check_libraries_against_env(str(tmp_path), installed)

        statuses = {r["library_name"]: r["status"] for r in results}
        assert statuses["Collections"] == "builtin"
        assert statuses["Browser"] == "installed"
        assert statuses["SeleniumLibrary"] == "missing"
