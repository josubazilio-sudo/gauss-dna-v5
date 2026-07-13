import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class ServiceFactory:
    def __init__(self):
        self._creators: Dict[str, callable] = {}

    def register_creator(self, name: str, creator: callable) -> None:
        self._creators[name] = creator
        log.debug(f"Creator registered: {name}")

    def create(self, name: str, **kwargs) -> Any:
        creator = self._creators.get(name)
        if creator:
            log.info(f"Creating service: {name}")
            return creator(**kwargs)
        log.warning(f"No creator registered for: {name}")
        return None
