"""Comandos da triagem. Erros tratados saem como JSON com ok=false e exit 0, para não quebrar o n8n."""
import argparse
import base64
import json
import sys
from datetime import datetime

from . import db
from .classificar import GESTOR, classificar
from .metrica import calcular
from .notificar import enviar_simulado
from .validar import validar


def _saida(**campos) -> dict:
    base = {"ok": False, "pedido_id": None, "tipo": None, "urgencia": None,
            "responsavel": None, "sla_horas": None, "erro": None, "notificacao": None}
    return {**base, **campos}


def receber(payload, con, agora: datetime) -> dict:
    resultado = validar(payload, agora)
    if not resultado.ok:
        db.registrar_erro(con, "invalido", payload, ",".join(resultado.erros), agora)
        return _saida(erro="invalido", detalhe=resultado.erros)

    pedido = resultado.pedido
    existente = db.achar_duplicado(con, pedido, agora)
    if existente is not None:
        db.registrar_erro(con, "duplicado", payload, f"igual ao pedido {existente}", agora)
        return _saida(erro="duplicado", pedido_id=existente)

    cls = classificar(pedido)
    pedido_id, duplicado = db.inserir_unico(con, pedido, cls, agora)
    if duplicado:  # outro pedido igual entrou entre a checagem e a gravação
        db.registrar_erro(con, "duplicado", payload, f"igual ao pedido {pedido_id}", agora)
        return _saida(erro="duplicado", pedido_id=pedido_id)
    status = _enviar_e_registrar(
        con, pedido_id, cls.responsavel, "novo",
        f"Novo pedido #{pedido_id} ({cls.tipo}, urgência {cls.urgencia})",
        f"{pedido['nome']}: {pedido['descricao']} | responder em {cls.sla_horas}h", agora)
    return _saida(ok=True, pedido_id=pedido_id, tipo=cls.tipo, urgencia=cls.urgencia,
                  responsavel=cls.responsavel, sla_horas=cls.sla_horas, notificacao=status)


def _enviar_e_registrar(con, pedido_id, destinatario, tipo, assunto, corpo, agora) -> str:
    status = "enviada" if enviar_simulado(destinatario, assunto, corpo) else "falha"
    db.registrar_notificacao(con, pedido_id, destinatario, tipo, status, agora, assunto, corpo)
    return status


def varrer(con, agora: datetime) -> list[dict]:
    """Reenvia alertas que falharam, manda lembrete aos 75% do SLA e escalona aos 100%."""
    acoes = []
    for n in db.notificacoes_com_falha(con):
        pedido = db.buscar_pedido(con, n["pedido_id"]) if n["pedido_id"] else None
        if pedido is not None and pedido["status"] == "respondido":
            continue  # já foi respondido: não adianta reenviar
        assunto = n["assunto"] or f"Reenvio de alerta ({n['tipo']})"
        if enviar_simulado(n["destinatario"], assunto, n["corpo"] or f"pedido #{n['pedido_id']}"):
            db.marcar_notificacao_enviada(con, n["id"])
            acoes.append({"pedido_id": n["pedido_id"], "acao": "reenvio", "destinatario": n["destinatario"]})

    for p in db.pedidos_com_status(con, "atribuido"):
        decorrido_h = (agora - datetime.fromisoformat(p["criado_em"])).total_seconds() / 3600
        if decorrido_h >= p["sla_horas"]:
            db.mudar_status(con, p["id"], "vencido", agora)
            _enviar_e_registrar(con, p["id"], GESTOR, "escalonamento",
                                f"VENCIDO: pedido #{p['id']} sem resposta",
                                f"responsável {p['responsavel']}, SLA {p['sla_horas']}h", agora)
            acoes.append({"pedido_id": p["id"], "acao": "escalonamento", "destinatario": GESTOR})
        elif decorrido_h >= 0.75 * p["sla_horas"] and not db.ja_notificou(con, p["id"], "lembrete"):
            _enviar_e_registrar(con, p["id"], p["responsavel"], "lembrete",
                                f"Lembrete: pedido #{p['id']} perto do prazo",
                                f"restam {p['sla_horas'] - decorrido_h:.1f}h de {p['sla_horas']}h", agora)
            acoes.append({"pedido_id": p["id"], "acao": "lembrete", "destinatario": p["responsavel"]})
    return acoes


def responder(con, pedido_id: int, agora: datetime) -> bool:
    p = db.buscar_pedido(con, pedido_id)
    if p is None or p["status"] not in ("atribuido", "vencido"):
        return False
    db.mudar_status(con, pedido_id, "respondido", agora)
    return True


def _agora(texto: str | None) -> datetime:
    agora = datetime.fromisoformat(texto) if texto else datetime.now().replace(microsecond=0)
    return db.para_naive(agora)


def main(argv=None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8")
    try:
        return _executar(argv)
    except Exception as e:  # contrato: o n8n sempre recebe um JSON, nunca um traceback
        print(json.dumps(_saida(erro="interno", detalhe=type(e).__name__)))
        return 0


def _executar(argv) -> int:
    parser = argparse.ArgumentParser(prog="triagem")
    sub = parser.add_subparsers(dest="comando", required=True)
    for nome in ("receber", "varrer", "responder", "metrica"):
        p = sub.add_parser(nome)
        p.add_argument("--db", required=True)
        p.add_argument("--agora")
        if nome == "receber":
            p.add_argument("--payload-b64", help="payload JSON em base64 (alternativa ao stdin)")
        if nome == "responder":
            p.add_argument("--id", type=int, required=True)
    args = parser.parse_args(argv)

    con = db.conectar(args.db)
    agora = _agora(args.agora)
    if args.comando == "receber":
        try:
            bruto = (base64.b64decode(args.payload_b64) if args.payload_b64
                     else sys.stdin.buffer.read())
            payload = json.loads(bruto.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            payload = None
        resultado = receber(payload, con, agora)
    elif args.comando == "varrer":
        resultado = varrer(con, agora)
    elif args.comando == "metrica":
        resultado = calcular(con)
    else:
        resultado = {"ok": responder(con, args.id, agora), "pedido_id": args.id}
    print(json.dumps(resultado, ensure_ascii=False, default=str))
    return 0
