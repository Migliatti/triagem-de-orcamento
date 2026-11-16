"""Persistência em SQLite. Datas em ISO-8601 (texto, sem fuso); 'agora' sempre vem de fora."""
import json
import sqlite3
from datetime import datetime, timedelta

from .classificar import Classificacao

JANELA_DUPLICADO_DIAS = 7

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL, email TEXT, telefone TEXT,
    descricao TEXT NOT NULL, itens TEXT NOT NULL, prazo TEXT,
    tipo TEXT NOT NULL, urgencia TEXT NOT NULL, responsavel TEXT NOT NULL,
    sla_horas INTEGER NOT NULL, status TEXT NOT NULL,
    criado_em TEXT NOT NULL, chave_dedup TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pedidos_dedup ON pedidos(chave_dedup, criado_em);
CREATE TABLE IF NOT EXISTS historico_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    status TEXT NOT NULL, em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER REFERENCES pedidos(id),
    destinatario TEXT NOT NULL, tipo TEXT NOT NULL, status TEXT NOT NULL, criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS erros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL, payload TEXT, detalhe TEXT NOT NULL, criado_em TEXT NOT NULL
);
"""


def conectar(caminho: str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def chave_dedup(pedido: dict) -> str:
    contato = pedido.get("email") or pedido.get("telefone") or ""
    descricao = " ".join(pedido["descricao"].lower().split())
    return f"{contato}|{descricao}"


def inserir_pedido(con, pedido: dict, cls: Classificacao, agora: datetime) -> int:
    cur = con.execute(
        """INSERT INTO pedidos (nome, email, telefone, descricao, itens, prazo, tipo, urgencia,
               responsavel, sla_horas, status, criado_em, chave_dedup)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pedido["nome"], pedido["email"], pedido["telefone"], pedido["descricao"],
         json.dumps(pedido["itens"], ensure_ascii=False),
         pedido["prazo"].isoformat() if pedido["prazo"] else None,
         cls.tipo, cls.urgencia, cls.responsavel, cls.sla_horas, "atribuido",
         _iso(agora), chave_dedup(pedido)),
    )
    con.execute("INSERT INTO historico_status (pedido_id, status, em) VALUES (?,?,?)",
                (cur.lastrowid, "atribuido", _iso(agora)))
    con.commit()
    return cur.lastrowid


def achar_duplicado(con, pedido: dict, agora: datetime) -> int | None:
    limite = _iso(agora - timedelta(days=JANELA_DUPLICADO_DIAS))
    linha = con.execute(
        "SELECT id FROM pedidos WHERE chave_dedup=? AND criado_em>=? ORDER BY id LIMIT 1",
        (chave_dedup(pedido), limite),
    ).fetchone()
    return linha["id"] if linha else None


def registrar_erro(con, tipo: str, payload, detalhe: str, agora: datetime) -> None:
    try:
        texto = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        texto = repr(payload)
    con.execute("INSERT INTO erros (tipo, payload, detalhe, criado_em) VALUES (?,?,?,?)",
                (tipo, texto, detalhe, _iso(agora)))
    con.commit()


def mudar_status(con, pedido_id: int, status: str, agora: datetime) -> None:
    con.execute("UPDATE pedidos SET status=? WHERE id=?", (status, pedido_id))
    con.execute("INSERT INTO historico_status (pedido_id, status, em) VALUES (?,?,?)",
                (pedido_id, status, _iso(agora)))
    con.commit()


def pedidos_com_status(con, status: str) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM pedidos WHERE status=? ORDER BY id", (status,)).fetchall()


def buscar_pedido(con, pedido_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,)).fetchone()


def notificacoes_com_falha(con) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM notificacoes WHERE status='falha' ORDER BY id").fetchall()


def marcar_notificacao_enviada(con, notificacao_id: int) -> None:
    con.execute("UPDATE notificacoes SET status='enviada' WHERE id=?", (notificacao_id,))
    con.commit()


def ja_notificou(con, pedido_id: int, tipo: str) -> bool:
    linha = con.execute("SELECT 1 FROM notificacoes WHERE pedido_id=? AND tipo=? LIMIT 1",
                        (pedido_id, tipo)).fetchone()
    return linha is not None


def registrar_notificacao(con, pedido_id: int | None, destinatario: str, tipo: str,
                          status: str, agora: datetime) -> int:
    cur = con.execute(
        "INSERT INTO notificacoes (pedido_id, destinatario, tipo, status, criado_em) VALUES (?,?,?,?,?)",
        (pedido_id, destinatario, tipo, status, _iso(agora)))
    con.commit()
    return cur.lastrowid
