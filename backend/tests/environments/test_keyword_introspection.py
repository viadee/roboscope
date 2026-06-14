"""Tests for libdoc-per-environment keyword discovery.

Story: Flow Editor — Verification & Hardening (libdoc-per-environment).
"""

import json
from unittest.mock import MagicMock, patch

from src.environments.models import Environment, EnvironmentKeywordCache
from src.environments import keyword_introspection as ki
from src.environments import service
from tests.conftest import auth_header

URL = "/api/v1/environments"


class TestComputePackagesHash:
    def test_empty_venv_yields_empty_hash(self):
        assert ki.compute_packages_hash(None) == ""

    def test_hash_is_deterministic_and_order_independent(self):
        pkgs_a = [{"name": "robotframework", "version": "7.4.2"}, {"name": "robotframework-browser", "version": "18.0.0"}]
        pkgs_b = list(reversed(pkgs_a))
        with patch.object(ki, "pip_list_installed", return_value=pkgs_a):
            h1 = ki.compute_packages_hash("/venv")
        with patch.object(ki, "pip_list_installed", return_value=pkgs_b):
            h2 = ki.compute_packages_hash("/venv")
        assert h1 == h2 and len(h1) == 64

    def test_hash_changes_when_a_package_upgrades(self):
        with patch.object(ki, "pip_list_installed", return_value=[{"name": "x", "version": "1.0"}]):
            h1 = ki.compute_packages_hash("/venv")
        with patch.object(ki, "pip_list_installed", return_value=[{"name": "x", "version": "2.0"}]):
            h2 = ki.compute_packages_hash("/venv")
        assert h1 != h2


class TestTargetLibraryNames:
    def test_always_includes_standard_libraries(self):
        with patch.object(ki, "pip_list_installed", return_value=[]):
            names = ki.target_library_names("/venv")
        assert "BuiltIn" in names and "Collections" in names and "String" in names

    def test_includes_installed_third_party_libraries(self):
        installed = [{"name": "robotframework-browser", "version": "18.0.0"}]
        with patch.object(ki, "pip_list_installed", return_value=installed):
            names = ki.target_library_names("/venv")
        assert "Browser" in names
        assert "BuiltIn" in names  # standard libs still present


class TestIntrospectKeywords:
    def test_returns_empty_for_missing_venv(self):
        assert ki.introspect_keywords(None) == []

    def test_parses_subprocess_json(self, tmp_path):
        # Fake a venv python that exists
        py = tmp_path / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("")
        payload = [{"name": "Click", "library": "Browser", "args": ["selector"], "shortdoc": "Click it"}]
        fake = MagicMock(returncode=0, stdout=json.dumps(payload), stderr="")
        with patch.object(ki, "get_python_path", return_value=str(py)), \
             patch.object(ki, "target_library_names", return_value=["Browser"]), \
             patch.object(ki.subprocess, "run", return_value=fake):
            out = ki.introspect_keywords(str(tmp_path))
        assert out == payload

    def test_bad_json_yields_empty(self, tmp_path):
        py = tmp_path / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("")
        fake = MagicMock(returncode=0, stdout="not json", stderr="")
        with patch.object(ki, "get_python_path", return_value=str(py)), \
             patch.object(ki, "target_library_names", return_value=["Browser"]), \
             patch.object(ki.subprocess, "run", return_value=fake):
            assert ki.introspect_keywords(str(tmp_path)) == []


class TestRebuildKeywordCache:
    def test_persists_keywords_and_hash(self, db_session, admin_user):
        env = Environment(name="kw-env", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        kws = [{"name": "Log", "library": "BuiltIn", "args": ["message"], "shortdoc": ""}]
        with patch("src.environments.keyword_introspection.introspect_keywords", return_value=kws), \
             patch("src.environments.keyword_introspection.compute_packages_hash", return_value="abc123"):
            cache = service.rebuild_keyword_cache(db_session, env.id)
        assert cache is not None
        assert cache.status == "ready"
        assert cache.source_hash == "abc123"
        assert json.loads(cache.keywords_json) == kws

    def test_marks_error_on_introspection_failure(self, db_session, admin_user):
        env = Environment(name="kw-env2", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        with patch("src.environments.keyword_introspection.introspect_keywords", side_effect=RuntimeError("boom")):
            cache = service.rebuild_keyword_cache(db_session, env.id)
        assert cache.status == "error"
        assert "boom" in (cache.error or "")


class TestKeywordsEndpoint:
    def test_404_for_missing_env(self, client, admin_user):
        resp = client.get(f"{URL}/99999/keywords", headers=auth_header(admin_user))
        assert resp.status_code == 404

    def test_fresh_cache_returns_ready(self, client, db_session, admin_user):
        env = Environment(name="fresh-env", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        kws = [{"name": "Click", "library": "Browser", "args": ["selector"], "shortdoc": "x"}]
        cache = EnvironmentKeywordCache(
            environment_id=env.id, source_hash="HASH", status="ready",
            keywords_json=json.dumps(kws),
        )
        db_session.add(cache)
        db_session.flush()
        with patch("src.environments.keyword_introspection.compute_packages_hash", return_value="HASH"):
            resp = client.get(f"{URL}/{env.id}/keywords", headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["keywords"][0]["name"] == "Click"
        assert body["keywords"][0]["library"] == "Browser"

    def test_stale_cache_dispatches_rebuild_and_returns_building(self, client, db_session, admin_user):
        env = Environment(name="stale-env", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        cache = EnvironmentKeywordCache(
            environment_id=env.id, source_hash="OLD", status="ready", keywords_json="[]",
        )
        db_session.add(cache)
        db_session.flush()
        with patch("src.environments.keyword_introspection.compute_packages_hash", return_value="NEW"), \
             patch("src.environments.router.dispatch_task") as disp:
            resp = client.get(f"{URL}/{env.id}/keywords", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "building"
        assert disp.called

    def test_missing_cache_dispatches_and_builds(self, client, db_session, admin_user):
        env = Environment(name="nocache-env", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        with patch("src.environments.router.dispatch_task") as disp:
            resp = client.get(f"{URL}/{env.id}/keywords", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "building"
        assert disp.called

    def test_unauthenticated_rejected(self, client, db_session, admin_user):
        env = Environment(name="auth-env", python_version="3.12", venv_path="/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        resp = client.get(f"{URL}/{env.id}/keywords")
        assert resp.status_code in (401, 403)
