"""Story 2-5: verify the hide_local_login_form default setting is seeded.

Locks in:
  - seed_default_settings() inserts hide_local_login_form with default "false"
  - PATCH round-trip via the admin settings endpoint persists the new value
"""

from tests.conftest import auth_header

from src.settings.service import (
    get_setting,
    get_setting_value,
    seed_default_settings,
)


class TestHideLocalLoginFormSeed:
    def test_default_is_seeded_as_false(self, db_session):
        """seed_default_settings creates the row with default 'false'."""
        seed_default_settings(db_session)
        db_session.commit()

        row = get_setting(db_session, "hide_local_login_form")
        assert row is not None
        assert row.value == "false"
        assert row.value_type == "bool"
        assert row.category == "auth"

    def test_seed_is_idempotent(self, db_session):
        """Running the seed twice doesn't duplicate the row or reset the value."""
        seed_default_settings(db_session)
        db_session.commit()

        # Mutate then reseed: the seed must NOT clobber the admin's change.
        row = get_setting(db_session, "hide_local_login_form")
        assert row is not None
        row.value = "true"
        db_session.commit()

        seed_default_settings(db_session)
        db_session.commit()

        row_after = get_setting(db_session, "hide_local_login_form")
        assert row_after is not None
        assert row_after.value == "true"

    def test_patch_persists_new_value(self, client, db_session, admin_user):
        """Admin PATCH updates the setting; subsequent read reflects the change."""
        seed_default_settings(db_session)
        db_session.commit()

        resp = client.patch(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "hide_local_login_form", "value": "true"},
                ],
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

        assert get_setting_value(db_session, "hide_local_login_form") == "true"
