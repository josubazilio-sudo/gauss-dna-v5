import json
import os
import datetime
import queue
import threading

_DEFAULT_ROTATE_BYTES = 5_000_000


class AuditEngine:
    """Logger de auditoria assincrono: fila + worker unico (sem thread por evento)."""

    def __init__(self, base_path="MEMORY", rotate_bytes=_DEFAULT_ROTATE_BYTES):
        self.base_path = base_path
        self.rotate_bytes = rotate_bytes
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        while True:
            path, data = self._queue.get()
            self._append_line(path, data)

    def _rotate_if_needed(self, path):
        try:
            if not (os.path.exists(path) and os.path.getsize(path) >= self.rotate_bytes):
                return
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            rotated = f"{path}.{ts}"
            suffix = 0
            while os.path.exists(rotated):
                suffix += 1
                rotated = f"{path}.{ts}_{suffix}"
            os.rename(path, rotated)
        except OSError as e:
            print(f"[AuditEngine ERROR] Falha ao rotacionar {path}: {e}")

    def _append_line(self, path, data):
        """Design Fail-Safe: Se o AuditEngine falhar, o Scanner continua."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._rotate_if_needed(path)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            print(f"[AuditEngine ERROR] Falha ao gravar logs: {e}")
            # Silencioso: O Scanner continua rodando.

    def log_cycle(self, metrics):
        """Coleta automática de métricas de ciclo (append-only, JSON Lines)."""
        data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "metrics": metrics,
        }
        self._queue.put((f"{self.base_path}/paper_trading/cycles.jsonl", data))

    def log_blocker(self, reason, asset):
        """Registra bloqueadores automaticamente (append-only, JSON Lines)."""
        data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "reason": reason,
            "asset": asset,
        }
        self._queue.put((f"{self.base_path}/audit/blockers.jsonl", data))

    def log_trade(self, trade_data):
        """Registra cada trade do Paper Trading (append-only, JSON Lines)."""
        data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "trade": trade_data,
        }
        self._queue.put((f"{self.base_path}/paper_trading/trades.jsonl", data))


# Instância Global para o Scanner usar
audit = AuditEngine()
