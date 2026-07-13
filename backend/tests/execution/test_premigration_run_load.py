"""EXEC.2: rows predating the advanced_config migration load without error.

The new columns are nullable with no server default, so an ExecutionRun (or
Schedule) created without advanced_config / variables must load back with those
fields as None — the FMEA guard against the migration breaking old rows.
"""

from src.execution.models import ExecutionRun, Schedule


def _user(db_session):
    from src.auth.models import User
    from src.auth.service import hash_password

    u = User(
        email="exec2@test.com",
        username="exec2",
        hashed_password=hash_password("pw123456"),
    )
    db_session.add(u)
    db_session.flush()
    return u


def _repo(db_session, user):
    from src.repos.models import Repository

    r = Repository(name="exec2-repo", local_path="/tmp/exec2-repo", created_by=user.id)
    db_session.add(r)
    db_session.flush()
    return r


def test_execution_run_without_advanced_config_loads_as_none(db_session):
    user = _user(db_session)
    repo = _repo(db_session, user)
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="suite.robot",
        triggered_by=user.id,
        # advanced_config intentionally omitted (simulates a pre-migration row)
    )
    db_session.add(run)
    db_session.commit()
    db_session.expire_all()

    loaded = db_session.get(ExecutionRun, run.id)
    assert loaded is not None
    assert loaded.advanced_config is None


def test_schedule_without_variables_or_advanced_config_loads_as_none(db_session):
    user = _user(db_session)
    repo = _repo(db_session, user)
    sched = Schedule(
        name="nightly",
        cron_expression="0 2 * * *",
        repository_id=repo.id,
        target_path="suite.robot",
        created_by=user.id,
    )
    db_session.add(sched)
    db_session.commit()
    db_session.expire_all()

    loaded = db_session.get(Schedule, sched.id)
    assert loaded is not None
    assert loaded.variables is None
    assert loaded.advanced_config is None
