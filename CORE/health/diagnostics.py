import importlib
import logging
from typing import Dict, Any, List

log = logging.getLogger(__name__)


class Diagnostics:
    def __init__(self, modules: List[str]):
        self._modules = modules

    def run_all(self) -> List[Dict[str, Any]]:
        results = []
        log.info("Executando diagnosticos em %d modulos", len(self._modules))
        for module in self._modules:
            results.append(self._check_module(module))
        return results

    def _check_module(self, module_name: str) -> Dict[str, Any]:
        try:
            importlib.import_module(module_name)
            log.debug("Modulo %s OK", module_name)
            return {"module": module_name, "status": "ok"}
        except ImportError:
            log.warning("Modulo %s nao encontrado", module_name)
            return {"module": module_name, "status": "error", "error": "Module not found"}
        except Exception as exc:
            log.error("Modulo %s falhou: %s", module_name, exc)
            return {"module": module_name, "status": "error", "error": str(exc)}
