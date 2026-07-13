"""RFC V19.2 — Estabilidade do AuditEngine (sem thread por evento, append O(1))."""
import importlib
import json
import os
import shutil
import threading
import time

import pytest

import audit_engine


@pytest.fixture
def engine(tmp_path):
    base = tmp_path / "MEMORY"
    eng = audit_engine.AuditEngine(base_path=str(base), rotate_bytes=500)
    yield eng
    base_parent = str(tmp_path)
    if os.path.exists(base_parent):
        shutil.rmtree(base_parent, ignore_errors=True)


def _drain(eng, timeout=2.0):
    """Aguarda a fila do worker esvaziar (sem usar Queue.join, que exige task_done())."""
    deadline = time.time() + timeout
    while not eng._queue.empty() and time.time() < deadline:
        time.sleep(0.01)
    # margem para o worker terminar de escrever o ultimo item retirado da fila
    time.sleep(0.1)


def test_log_blocker_does_not_spawn_thread_per_call(engine):
    before = threading.active_count()
    for i in range(50):
        engine.log_blocker(f"motivo {i}", f"PAIR{i}USDT")
    after = threading.active_count()
    # apenas o worker unico ja existente pode ter sido criado (no maximo +1
    # em relacao ao baseline do proprio fixture); nenhuma thread por chamada.
    assert after - before <= 1


def test_log_blocker_appends_as_json_lines(engine):
    engine.log_blocker("RVOL baixo", "BTCUSDT")
    engine.log_blocker("ADX fraco", "ETHUSDT")
    _drain(engine)

    path = os.path.join(engine.base_path, "audit", "blockers.jsonl")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 2
    assert lines[0]["reason"] == "RVOL baixo"
    assert lines[0]["asset"] == "BTCUSDT"
    assert lines[1]["reason"] == "ADX fraco"


def test_log_blocker_append_is_o1_no_full_file_rewrite(tmp_path):
    """Cada chamada deve apenas abrir em modo append, nunca ler o arquivo inteiro."""
    base = tmp_path / "MEMORY"
    eng = audit_engine.AuditEngine(base_path=str(base), rotate_bytes=10_000_000)
    path = os.path.join(str(base), "audit", "blockers.jsonl")
    for i in range(20):
        eng.log_blocker(f"motivo {i}", "BTCUSDT")
    _drain(eng)

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 20
    for line in lines:
        json.loads(line)  # cada linha deve ser um JSON valido isolado


def test_rotation_when_file_exceeds_configured_size(engine):
    path = os.path.join(engine.base_path, "audit", "blockers.jsonl")
    for i in range(200):
        engine.log_blocker("motivo " * 5, f"PAIR{i}USDT")
    _drain(engine)

    directory = os.path.join(engine.base_path, "audit")
    files = os.listdir(directory)
    rotated = [f for f in files if f.startswith("blockers.jsonl.")]
    assert len(rotated) >= 1, "esperava ao menos um arquivo rotacionado apos exceder rotate_bytes"


def test_write_failure_is_silent_and_does_not_raise(engine, capsys):
    """Fail-safe: erro de escrita nao deve derrubar o chamador (scanner continua)."""
    bad_path = os.path.join(engine.base_path, "audit", "blockers.jsonl")
    os.makedirs(os.path.dirname(bad_path), exist_ok=True)
    # forca falha: usa um diretorio no lugar do arquivo esperado
    os.makedirs(bad_path, exist_ok=True)
    engine.log_blocker("motivo", "BTCUSDT")
    _drain(engine)
    captured = capsys.readouterr()
    assert "[AuditEngine ERROR]" in captured.out


def test_log_cycle_and_log_trade_also_append_only(engine):
    engine.log_cycle({"pares": 300, "aprovados": 2})
    engine.log_trade({"pair": "BTCUSDT", "pnl": 12.5})
    _drain(engine)

    cycles_path = os.path.join(engine.base_path, "paper_trading", "cycles.jsonl")
    trades_path = os.path.join(engine.base_path, "paper_trading", "trades.jsonl")
    assert os.path.exists(cycles_path)
    assert os.path.exists(trades_path)


def test_main_module_calls_log_blocker_directly_without_thread():
    """Garante que main.py nao volta a usar threading.Thread por evento (RFC V19.2)."""
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(main_path, encoding="utf-8") as f:
        content = f.read()
    assert "threading.Thread(target=audit.log_blocker" not in content
    assert "audit.log_blocker(" in content
