import logging
import asyncio
from CORE.events.event_bus import EventBus
from .telegram_sender import TelegramSender
from .telegram_formatter import TelegramFormatter
from .telegram_validator import (
    validate_signal_data, validate_consistency, validate_presentation_consistency,
)
from .signal_compat import wrap_signal

log = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._sender = TelegramSender()
        self._formatter = TelegramFormatter()
        
        # Loop de processamento
        self._queue = asyncio.Queue()
        self._loop = asyncio.new_event_loop()
        import threading
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._bus.subscribe("signal.generated", self._on_signal)
        self._bus.subscribe("decision.made", self._on_decision)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._worker())
        self._loop.run_forever()

    async def _worker(self):
        while True:
            msg = await self._queue.get()
            try:
                await self._sender.send(msg)
            except Exception as e:
                log.error("Falha fatal ao enviar Telegram: %s", e)
            finally:
                self._queue.task_done()
                await asyncio.sleep(1.5)

    def _on_signal(self, event):
        self._format_and_queue(event.data, default_message_type="new")

    def _on_decision(self, event):
        # DecisionEngine.evaluate_signal() ja filtrou por approved=True antes
        # de chamar Publisher.decision_made() (ver main.py _process_scan_result),
        # entao todo evento aqui e um sinal aprovado que precisa ser enviado —
        # nao um diagnostico. Usa a mesma formatacao/validacao de _on_signal.
        self._format_and_queue(event.data, default_message_type="new")

    def _format_and_queue(self, data: dict, default_message_type: str) -> None:
        valid, reason = validate_signal_data(data)
        if not valid:
            log.warning("TelegramService: sinal descartado (%s): %s", reason, data.get("pair") or data.get("symbol"))
            return
        if not validate_consistency(data):
            return

        # RFC V20.2: valida consistencia dos dados que serao EXIBIDOS
        pres_ok, pres_reason = validate_presentation_consistency(data)
        if not pres_ok:
            log.error(
                "TelegramService: envio cancelado por inconsistencia de apresentacao (%s): %s",
                data.get("pair") or data.get("symbol"), pres_reason,
            )
            return

        # RFC V18.5.2: update_label vem do tracker (main.py ja validou via pode_reenviar)
        update_label = data.get("update_label")
        if not update_label and data.get("message_type") == "update":
            log.info(
                "Update ignorado. Impacto operacional: %d/100. "
                "Nenhuma alteracao relevante detectada.",
                data.get("impact_score", 0),
            )
            return

        message_type = data.get("message_type", default_message_type)
        try:
            msg = self._formatter.format_signal(wrap_signal(data), message_type, update_label=update_label)
            asyncio.run_coroutine_threadsafe(self._queue.put(msg), self._loop)
        except Exception as e:
            log.exception("Erro na formatação de sinal: %s", e)

    def send_diagnostic(self, message: str):
        log.info("TelegramService: send_diagnostic: %s", message)
        asyncio.run_coroutine_threadsafe(self._queue.put(message), self._loop)
