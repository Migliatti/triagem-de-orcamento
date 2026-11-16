"""Regra de classificação: tipo, urgência, SLA e responsável. Sem acesso a banco nem relógio."""
import re
import unicodedata
from dataclasses import dataclass

GESTOR = "Helena Prado"

RESPONSAVEIS = {
    "sob_medida": "Marta Lopes",
    "corporativo": "Rogério Faria",
    "reparo": "Davi Moura",
    "indefinido": GESTOR,
}

# Ordem = prioridade em caso de empate: o primeiro tipo com alguma palavra encontrada vence.
PALAVRAS_CHAVE = {
    "corporativo": ["escritorio", "loja", "empresa", "estacoes", "mobiliario", "restaurante", "clinica", "consultorio"],
    "reparo": ["conserto", "consertar", "dobradica", "reparo", "emperr", "restaurar", "lixar", "envernizar"],
    "sob_medida": ["armario", "cozinha", "guarda-roupa", "planejad", "closet", "estante", "sob medida"],
}

SLA_HORAS = {"alta": 4, "media": 24, "baixa": 72}
_NIVEIS = ["baixa", "media", "alta"]


@dataclass
class Classificacao:
    tipo: str
    urgencia: str
    sla_horas: int
    responsavel: str


def sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _tipo(texto: str) -> str:
    for tipo, palavras in PALAVRAS_CHAVE.items():
        if any(re.search(r"\b" + re.escape(p), texto) for p in palavras):  # início de palavra
            return tipo
    return "indefinido"


def _urgencia(prazo_dias: int | None, texto: str) -> str:
    if prazo_dias is None or prazo_dias > 14:
        nivel = 0
    elif prazo_dias > 3:
        nivel = 1
    else:
        nivel = 2
    if re.search(r"\burgente", texto) and not re.search(r"\bnao (e |eh |tao )?urgente", texto):
        nivel = min(nivel + 1, 2)
    return _NIVEIS[nivel]


def classificar(pedido: dict) -> Classificacao:
    texto = sem_acento(" ".join([pedido.get("descricao", ""), *pedido.get("itens", [])]))
    tipo = _tipo(texto)
    urgencia = _urgencia(pedido.get("prazo_dias"), texto)
    return Classificacao(tipo, urgencia, SLA_HORAS[urgencia], RESPONSAVEIS[tipo])
