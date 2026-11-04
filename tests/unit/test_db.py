from app import db


def test_db_engine_uses_liveness_and_timeout_settings(monkeypatch, mocker):
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "45000")
    create_engine = mocker.patch(
        "app.db.create_engine", return_value=mocker.sentinel.engine
    )

    assert db.create_db_engine() is mocker.sentinel.engine
    _, kwargs = create_engine.call_args
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["connect_args"] == {
        "connect_timeout": 7,
        "options": "-c statement_timeout=45000",
    }
