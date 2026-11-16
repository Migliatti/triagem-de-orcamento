"""Validação e normalização do payload de um pedido. Nunca levanta exceção por entrada ruim."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Resultado:
    ok: bool
    pedido: dict | None = None
    erros: list[str] = field(default_factory=list)


def _texto(valor) -> str:
    if valor is None:
        return ""
    # surrogates soltos (ex.: um \ud800 no JSON) viram "?" para o texto poder ir ao SQLite/JSON
    return " ".join(str(valor).encode("utf-8", "replace").decode("utf-8").split())


def _nome(valor) -> str:
    return " ".join(p.capitalize() for p in _texto(valor).split())


def _contato(payload: dict) -> tuple[str | None, str | None]:
    """Procura e-mail e telefone válidos em contato/email/telefone."""
    email = telefone = None
    for chave in ("contato", "email", "telefone"):
        bruto = _texto(payload.get(chave))
        if not bruto:
            continue
        if EMAIL_RE.match(bruto):
            email = email or bruto.lower()
            continue
        if "@" in bruto:  # parece e-mail mas é inválido: não extrair telefone dele
            continue
        digitos = re.sub(r"\D", "", bruto)
        if len(digitos) in (12, 13) and digitos.startswith("55"):  # prefixo do país
            digitos = digitos[2:]
        if len(digitos) in (10, 11):
            telefone = telefone or digitos
    return email, telefone


def _prazo(valor) -> tuple[date | None, bool]:
    """Devolve (data, legivel). Vazio/None é legível e significa 'sem prazo'."""
    bruto = _texto(valor)
    if not bruto:
        return None, True
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(bruto, formato).date(), True
        except ValueError:
            pass
    return None, False


def _itens(valor) -> list[str]:
    if isinstance(valor, str):
        valor = valor.split(",")
    if not isinstance(valor, list):
        return []
    return [i for i in (_texto(x) for x in valor) if i]


def validar(payload, agora: datetime) -> Resultado:
    if not isinstance(payload, dict):
        return Resultado(False, None, ["payload_invalido"])

    erros = []
    nome = _nome(payload.get("nome"))
    if not nome:
        erros.append("nome_ausente")

    email, telefone = _contato(payload)
    if not (email or telefone):
        erros.append("contato_invalido")

    descricao = _texto(payload.get("descricao"))
    if not descricao:
        erros.append("descricao_ausente")

    prazo, legivel = _prazo(payload.get("prazo"))
    if not legivel:
        erros.append("prazo_ilegivel")

    if erros:
        return Resultado(False, None, erros)

    return Resultado(True, {
        "nome": nome,
        "email": email,
        "telefone": telefone,
        "descricao": descricao,
        "itens": _itens(payload.get("itens")),
        "prazo": prazo,
        "prazo_dias": (prazo - agora.date()).days if prazo else None,
    })
