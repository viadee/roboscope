"""Tests for explorer API endpoints."""

import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session

from src.environments.models import Environment
from src.repos.models import Repository
from tests.conftest import auth_header

SAMPLE_ROBOT = """\
*** Settings ***
Library    Browser

*** Test Cases ***
Login With Valid Credentials
    [Documentation]    Verify valid login works
    [Tags]    smoke    auth
    Open Browser    https://example.com    chromium
    Fill Text    id=username    admin

Login With Invalid Password
    [Tags]    negative
    Open Browser    https://example.com    chromium
    Fill Text    id=username    admin

*** Keywords ***
Custom Keyword
    Log    Hello
"""


@pytest.fixture
def repo_with_files(db_session: Session, admin_user, tmp_path):
    """Create a Repository record whose local_path points to a tmp_path with sample .robot files."""
    # Build sample file structure
    suites = tmp_path / "suites"
    suites.mkdir()
    (suites / "login.robot").write_text(SAMPLE_ROBOT)
    (suites / "api_tests.robot").write_text(
        "*** Test Cases ***\nAPI Health Check\n    Log    OK\n"
    )

    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "common.resource").write_text(
        "*** Keywords ***\nMy Keyword\n    Log    hello\n"
    )

    repo = Repository(
        name="test-explorer-repo",
        git_url="https://github.com/example/test.git",
        default_branch="main",
        local_path=str(tmp_path),
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


class TestGetTree:
    def test_get_tree_authenticated(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/tree",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "directory"
        assert data["children"] is not None
        child_names = [c["name"] for c in data["children"]]
        assert "suites" in child_names
        assert "resources" in child_names

    def test_get_tree_unauthenticated(self, client, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/tree",
        )
        assert response.status_code == 401

    def test_get_tree_with_subpath(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/tree",
            params={"path": "suites"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "suites"
        child_names = [c["name"] for c in data["children"]]
        assert "login.robot" in child_names

    def test_get_tree_nonexistent_repo(self, client, admin_user):
        response = client.get(
            "/api/v1/explorer/99999/tree",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_get_tree_contains_test_counts(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/tree",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()

        suites_node = next(c for c in data["children"] if c["name"] == "suites")
        assert suites_node["test_count"] >= 1


class TestGetFile:
    def test_read_file(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/file",
            params={"path": "suites/login.robot"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "login.robot"
        assert data["path"] == "suites/login.robot"
        assert data["extension"] == ".robot"
        assert "Login With Valid Credentials" in data["content"]
        assert data["line_count"] > 0

    def test_read_file_unauthenticated(self, client, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/file",
            params={"path": "suites/login.robot"},
        )
        assert response.status_code == 401

    def test_read_file_not_found(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/file",
            params={"path": "nonexistent.robot"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_read_file_path_traversal_blocked(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/file",
            params={"path": "../../../etc/passwd"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 403

    def test_read_file_nonexistent_repo(self, client, admin_user):
        response = client.get(
            "/api/v1/explorer/99999/file",
            params={"path": "suites/login.robot"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_read_resource_file(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/file",
            params={"path": "resources/common.resource"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "common.resource"
        assert data["extension"] == ".resource"


class TestSearch:
    def test_search_finds_results(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/search",
            params={"q": "login"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_search_unauthenticated(self, client, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/search",
            params={"q": "login"},
        )
        assert response.status_code == 401

    def test_search_no_results(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/search",
            params={"q": "zzz_nonexistent_term_zzz"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_search_with_file_type_filter(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/search",
            params={"q": "keyword", "file_type": "resource"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        for result in data:
            assert result["file_path"].endswith(".resource")

    def test_search_nonexistent_repo(self, client, admin_user):
        response = client.get(
            "/api/v1/explorer/99999/search",
            params={"q": "test"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_search_result_structure(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/search",
            params={"q": "Login With Valid"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        result = data[0]
        assert "type" in result
        assert "name" in result
        assert "file_path" in result


class TestGetTestcases:
    def test_list_testcases(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/testcases",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # login.robot has 2 test cases, api_tests.robot has 1 = 3 total
        assert len(data) == 3

    def test_list_testcases_unauthenticated(self, client, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/testcases",
        )
        assert response.status_code == 401

    def test_list_testcases_nonexistent_repo(self, client, admin_user):
        response = client.get(
            "/api/v1/explorer/99999/testcases",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    def test_list_testcases_structure(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/testcases",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        tc = data[0]
        assert "name" in tc
        assert "file_path" in tc
        assert "suite_name" in tc
        assert "tags" in tc
        assert "documentation" in tc
        assert "line_number" in tc

    def test_list_testcases_contains_expected_names(self, client, admin_user, repo_with_files):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/testcases",
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        names = [tc["name"] for tc in data]
        assert "Login With Valid Credentials" in names
        assert "Login With Invalid Password" in names
        assert "API Health Check" in names

    def test_list_testcases_with_different_role(self, client, runner_user, repo_with_files):
        """Any authenticated user should be able to list testcases."""
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/testcases",
            headers=auth_header(runner_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.fixture
def environment(db_session: Session, admin_user):
    """Create an Environment record for testing library-check."""
    env = Environment(
        name="test-env",
        python_version="3.12",
        venv_path="/tmp/test-venv",
        created_by=admin_user.id,
    )
    db_session.add(env)
    db_session.flush()
    db_session.refresh(env)
    return env


class TestLibraryCheck:
    @patch("src.explorer.router.pip_list_installed")
    def test_library_check_returns_results(
        self, mock_pip, client, admin_user, repo_with_files, environment
    ):
        """Library check should return installed/missing/builtin statuses."""
        mock_pip.return_value = [
            {"name": "robotframework-browser", "version": "18.0.0"},
        ]
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/library-check",
            params={"environment_id": environment.id},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["repo_id"] == repo_with_files.id
        assert data["environment_id"] == environment.id
        assert data["environment_name"] == "test-env"
        assert data["total_libraries"] >= 1
        assert "libraries" in data

        # The sample robot file has "Library    Browser" in *** Settings ***
        lib_names = [l["library_name"] for l in data["libraries"]]
        assert "Browser" in lib_names

        browser = next(l for l in data["libraries"] if l["library_name"] == "Browser")
        assert browser["status"] == "installed"
        assert browser["installed_version"] == "18.0.0"

    @patch("src.explorer.router.pip_list_installed")
    def test_library_check_missing_library(
        self, mock_pip, client, admin_user, repo_with_files, environment
    ):
        """Libraries not in pip list should be marked missing."""
        mock_pip.return_value = []  # Nothing installed
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/library-check",
            params={"environment_id": environment.id},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()

        browser = next(
            (l for l in data["libraries"] if l["library_name"] == "Browser"), None
        )
        if browser:
            assert browser["status"] == "missing"

    def test_library_check_unauthenticated(
        self, client, repo_with_files, environment
    ):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/library-check",
            params={"environment_id": environment.id},
        )
        assert response.status_code == 401

    @patch("src.explorer.router.pip_list_installed")
    def test_library_check_nonexistent_repo(
        self, mock_pip, client, admin_user, environment
    ):
        response = client.get(
            "/api/v1/explorer/99999/library-check",
            params={"environment_id": environment.id},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    @patch("src.explorer.router.pip_list_installed")
    def test_library_check_nonexistent_env(
        self, mock_pip, client, admin_user, repo_with_files
    ):
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/library-check",
            params={"environment_id": 99999},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

class TestOpenInFileBrowser:
    @patch("src.explorer.router.open_in_file_browser")
    def test_open_folder_success(self, mock_open, client, admin_user, repo_with_files):
        """POST /{repo_id}/folder/open should call open_in_file_browser."""
        response = client.post(
            f"/api/v1/explorer/{repo_with_files.id}/folder/open",
            json={"path": "suites"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 204
        mock_open.assert_called_once_with(repo_with_files.local_path, "suites")

    def test_open_folder_unauthenticated(self, client, repo_with_files):
        """POST /{repo_id}/folder/open should reject unauthenticated requests."""
        response = client.post(
            f"/api/v1/explorer/{repo_with_files.id}/folder/open",
            json={"path": "suites"},
        )
        assert response.status_code in (401, 403)

    @patch("src.explorer.router.open_in_file_browser")
    def test_open_folder_nonexistent_repo(self, mock_open, client, admin_user):
        """POST for nonexistent repo should return 404."""
        response = client.post(
            "/api/v1/explorer/99999/folder/open",
            json={"path": "suites"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    @patch("src.explorer.router.open_in_file_browser", side_effect=FileNotFoundError("Not found"))
    def test_open_folder_not_found(self, mock_open, client, admin_user, repo_with_files):
        """POST for nonexistent folder should return 404."""
        response = client.post(
            f"/api/v1/explorer/{repo_with_files.id}/folder/open",
            json={"path": "nonexistent"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 404

    @patch("src.explorer.router.open_in_file_browser", side_effect=ValueError("Path traversal"))
    def test_open_folder_path_traversal(self, mock_open, client, admin_user, repo_with_files):
        """POST with path traversal should return 403."""
        response = client.post(
            f"/api/v1/explorer/{repo_with_files.id}/folder/open",
            json={"path": "../../../etc"},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 403


    @patch("src.explorer.router.pip_list_installed")
    def test_library_check_response_counts(
        self, mock_pip, client, admin_user, repo_with_files, environment
    ):
        """Verify that counts in response match the library list."""
        mock_pip.return_value = [
            {"name": "robotframework-browser", "version": "18.0.0"},
        ]
        response = client.get(
            f"/api/v1/explorer/{repo_with_files.id}/library-check",
            params={"environment_id": environment.id},
            headers=auth_header(admin_user),
        )
        assert response.status_code == 200
        data = response.json()

        libs = data["libraries"]
        assert data["total_libraries"] == len(libs)
        assert data["missing_count"] == sum(1 for l in libs if l["status"] == "missing")
        assert data["installed_count"] == sum(1 for l in libs if l["status"] == "installed")
        assert data["builtin_count"] == sum(1 for l in libs if l["status"] == "builtin")
