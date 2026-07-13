import logging
import os
import sys
from pathlib import Path
from dotenv import dotenv_values

log = logging.getLogger(__name__)

def run_health_check() -> bool:
    """Valida o ambiente antes de iniciar o QuantOS."""
    log.info("Executando Health Check...")
    
    # 1. Base Dir
    base_dir = Path(__file__).resolve().parents[2]
    
    # 2. .env e Config
    env_path = base_dir / ".env"
    if not env_path.exists():
        log.error(f"FATAL: Arquivo .env nao encontrado em {env_path}")
        return False
        
    config = dotenv_values(env_path)
    required_keys = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    for key in required_keys:
        if not config.get(key):
            log.error(f"FATAL: {key} faltando no .env")
            return False
            
    # 3. Diretórios obrigatórios
    required_dirs = [
        base_dir / "MEMORY",
        base_dir / "LOGS",
        base_dir / "DATA"
    ]
    for d in required_dirs:
        if not d.exists():
            try:
                d.mkdir(parents=True, exist_ok=True)
                log.info(f"Diretorio criado: {d}")
            except Exception as e:
                log.error(f"FATAL: Nao foi possivel criar diretorio {d}: {e}")
                return False
                
    log.info("Health Check concluido: Sistema pronto.")
    return True
