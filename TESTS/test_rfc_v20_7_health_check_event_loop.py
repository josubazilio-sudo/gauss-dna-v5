import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import _run_health_check_sync


class FakeHealth:
    async def check(self):
        return {"healthy": True}


def test_run_health_check_sync_closes_created_event_loop(monkeypatch):
    created_loop = asyncio.new_event_loop()

    def fake_new_event_loop():
        return created_loop

    monkeypatch.setattr(asyncio, "new_event_loop", fake_new_event_loop)

    result = _run_health_check_sync(FakeHealth())

    assert result == {"healthy": True}
    assert created_loop.is_closed()
