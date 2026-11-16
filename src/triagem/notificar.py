"""Alerta simulado: nada é enviado a terceiros, só gravado em log."""
import os
from pathlib import Path


def enviar_simulado(destinatario: str, assunto: str, corpo: str) -> bool:
    """Devolve False (falha) quando TRIAGEM_FALHA_ENVIO=1; útil para testar o tratamento de erro."""
    if os.environ.get("TRIAGEM_FALHA_ENVIO") == "1":
        return False
    caminho = Path(os.environ.get("TRIAGEM_LOG", "logs/alertas.log"))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(f"[SIMULADO] para={destinatario} | {assunto} | {corpo}\n")
    return True
