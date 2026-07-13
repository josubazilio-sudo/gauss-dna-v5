import logging
from SERVICES.telegram.telegram_sender import TelegramSender

log = logging.getLogger(__name__)

def test_send():
    sender = TelegramSender()
    msg = "TESTE DE ENVIO QUANTOS V6.0 - SINAL APROVADO"
    print(f"Tentando enviar: {msg}")
    try:
        # Usando o método send do TelegramSender
        import asyncio
        asyncio.run(sender.send(msg))
        print("Envio realizado com sucesso!")
    except Exception as e:
        print(f"Erro no envio: {e}")

if __name__ == "__main__":
    test_send()
