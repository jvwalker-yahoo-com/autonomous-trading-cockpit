"""
Pytest configuration and global safety fixtures.
Ensures test runs never overwrite production data/trading_state.json or execute live trades on eToro.
"""
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def isolate_trading_state(tmp_path, monkeypatch):
    """
    Redirects broker.db_path and config.db_path to an isolated temporary file
    for every test, preserving the production data/trading_state.json on disk,
    and blocks unmocked real-money order execution on server.etoro_client.
    """
    from backend.config import config
    from backend.server import broker, etoro_client

    orig_config_db = config.db_path
    orig_broker_db = broker.db_path
    prod_file = Path(orig_config_db)
    backup_bytes = prod_file.read_bytes() if prod_file.exists() else None

    temp_db = tmp_path / "test_trading_state.json"
    if backup_bytes is not None:
        temp_db.write_bytes(backup_bytes)

    config.db_path = str(temp_db)
    broker.db_path = str(temp_db)

    orig_call_mcp = etoro_client.call_mcp_tool

    def safe_call_mcp(tool_name, arguments=None, timeout=6.0, trigger_cooldown_on_auth_fail=True):
        if tool_name in ("place-trade", "place-close"):
            return {
                "success": True,
                "data": {
                    "outcome": "executed",
                    "orderId": 999999,
                    "positions": []
                }
            }
        return orig_call_mcp(
            tool_name,
            arguments=arguments,
            timeout=timeout,
            trigger_cooldown_on_auth_fail=trigger_cooldown_on_auth_fail
        )

    monkeypatch.setattr(etoro_client, "call_mcp_tool", safe_call_mcp)

    try:
        yield
    finally:
        config.db_path = orig_config_db
        broker.db_path = orig_broker_db
        if backup_bytes is not None:
            prod_file.write_bytes(backup_bytes)
