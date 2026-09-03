"""Rotation + robustness tier: MultiFernet, worker alignment, telemetry."""
import pytest


# ---------------------------------------------------------
# MultiFernet rotation
# ---------------------------------------------------------

def test_multifernet_decrypts_previous_key_ciphertext(monkeypatch):
    """After a key swap, rows encrypted under the old key still decrypt."""
    from cryptography.fernet import Fernet

    from app.core import security

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    monkeypatch.setattr(security.settings, "ENCRYPTION_KEY", new_key)
    monkeypatch.setattr(security.settings, "ENCRYPTION_KEY_PREVIOUS", old_key)

    old_cipher = Fernet(old_key.encode())
    token = old_cipher.encrypt(b"oauth-secret-value").decode()
    assert security.decrypt_token(token) == "b" + "oauth-secret-value"[1:] or security.decrypt_token(token) == b"oauth-secret-value".decode()


def test_multifernet_new_writes_use_current_key(monkeypatch):
    """Post-rotation ciphertext is NOT decryptable by the old key alone."""
    from cryptography.fernet import Fernet

    from app.core import security

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(security.settings, "ENCRYPTION_KEY", new_key)
    monkeypatch.setattr(security.settings, "ENCRYPTION_KEY_PREVIOUS", old_key)

    token = security.encrypt_token("fresh-value")
    Fernet(new_key.encode()).decrypt(token.encode())  # current key: OK
    import cryptography.fernet as cf

    with pytest.raises(cf.InvalidToken):
        Fernet(old_key.encode()).decrypt(token.encode())


@pytest.mark.asyncio
async def test_rotate_script_aborts_before_write_on_undecryptable_row(monkeypatch, capsys):
    """One undecryptable row aborts with NOTHING written — no partial vault."""
    from cryptography.fernet import Fernet

    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    stranger = Fernet.generate_key().decode()

    async with async_session_factory() as session:
        session.add(OAuthTokenModel(
            id="row-good", provider="rot-good",
            access_token_enc=Fernet(old_key.encode()).encrypt(b"good").decode(),
        ))
        session.add(OAuthTokenModel(
            id="row-bad", provider="rot-bad",
            access_token_enc=Fernet(stranger.encode()).encrypt(b"unreadable").decode(),
        ))
        await session.commit()

    monkeypatch.setenv("ENCRYPTION_KEY", old_key)
    monkeypatch.setenv("ENCRYPTION_KEY_NEW", new_key)

    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "rotate_fernet_key",
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "rotate_fernet_key.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = await module.main()
    assert exit_code == 3
    assert "ABORT" in capsys.readouterr().err

    # The good row is STILL under the old key — nothing was touched.
    # Cleanup deletes ONLY this test's rows so sibling tests keep theirs.
    from sqlalchemy import select

    async with async_session_factory() as session:
        rows = await session.scalars(select(OAuthTokenModel))
        good = next(r for r in rows if r.id == "row-good")
        assert Fernet(old_key.encode()).decrypt(good.access_token_enc.encode()) == b"good"
        for r in rows:
            if r.id in ("row-good", "row-bad"):
                await session.delete(r)
        await session.commit()


@pytest.mark.asyncio
async def test_rotate_script_reencrypts_all_rows_atomically(monkeypatch, capsys):
    from cryptography.fernet import Fernet

    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    # Clear any leftover oauth rows: this test proves the script's happy
    # path, not cross-test isolation.
    from sqlalchemy import select as _sel

    async with async_session_factory() as _purge:
        for r in await _purge.scalars(_sel(OAuthTokenModel)):
            await _purge.delete(r)
        await _purge.commit()

    async with async_session_factory() as session:
        session.add(OAuthTokenModel(
            id="row-a", provider="rot-a",
            access_token_enc=Fernet(old_key.encode()).encrypt(b"token-a").decode(),
            refresh_token_enc=Fernet(old_key.encode()).encrypt(b"refresh-a").decode(),
        ))
        await session.commit()

    monkeypatch.setenv("ENCRYPTION_KEY", old_key)
    monkeypatch.setenv("ENCRYPTION_KEY_NEW", new_key)

    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "rotate_fernet_key",
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "rotate_fernet_key.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert await module.main() == 0
    new_cipher = Fernet(new_key.encode())
    from sqlalchemy import select

    async with async_session_factory() as session:
        rows = list(await session.scalars(select(OAuthTokenModel)))
        row = rows[0]
        assert new_cipher.decrypt(row.access_token_enc.encode()) == b"token-a"
        assert new_cipher.decrypt(row.refresh_token_enc.encode()) == b"refresh-a"
        for r in rows:
            await session.delete(r)
        await session.commit()


def test_rotate_script_rejects_identical_keys(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "k1")
    monkeypatch.setenv("ENCRYPTION_KEY_NEW", "k1")

    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "rotate_fernet_key",
        os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "rotate_fernet_key.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import asyncio

    assert asyncio.run(module.main()) == 2


# ---------------------------------------------------------
# Worker alignment
# ---------------------------------------------------------

def test_worker_concurrency_setting_default():
    from app.config import Settings

    assert Settings().TEMPORAL_MAX_CONCURRENT_ACTIVITIES == 25


def test_worker_passes_concurrency_to_worker_constructor():
    import inspect

    from app.temporal import worker

    src = inspect.getsource(worker.create_worker)
    assert "max_concurrent_activities=settings.TEMPORAL_MAX_CONCURRENT_ACTIVITIES" in src


def test_session_app_name_reads_env(monkeypatch):
    """The engine's application_name comes from the process env at
    construction — import-order-proof per-process attribution."""
    import os

    monkeypatch.setenv("KAIROS_DB_APP_NAME", "kairos-worker")
    src = open(os.path.join(os.path.dirname(__file__), "..", "app", "db", "session.py")).read()
    assert 'os.getenv("KAIROS_DB_APP_NAME", "kairos-api")' in src


# ---------------------------------------------------------
# Telemetry conventions
# ---------------------------------------------------------

def test_genai_attributes_use_convention_token_keys():
    from app.core.telemetry import TelemetryClient

    attrs = TelemetryClient.genai_attributes(
        operation="execute_action", tool_name="jira", input_tokens=42,
    )
    assert attrs["gen_ai.usage.input_tokens"] == 42
    assert "gen_ai.usage.token_count" not in attrs
    assert "gen_ai.response.time_to_first_chunk" not in attrs
    assert attrs["gen_ai.tool.name"] == "jira"


def test_telemetry_fail_open_unchanged():
    from app.core.telemetry import TelemetryClient

    client = TelemetryClient()  # no Langfuse keys configured
    assert client.log_trace(batch_id="b", name="n") is None


# ---------------------------------------------------------
# Backup story
# ---------------------------------------------------------

def test_backup_script_exists_and_executable():
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backup.sh")
    assert os.access(path, os.X_OK)
