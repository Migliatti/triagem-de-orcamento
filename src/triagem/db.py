"""Persistência em SQLite. Datas em ISO-8601 (texto, sem fuso); 'agora' sempre vem de fora."""
import json
import sqlite3
from datetime import datetime, timedelta

import re

from .classificar import Classificacao, sem_acento

JANELA_DUPLICADO_DIAS = 7

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL, email TEXT, telefone TEXT,
    descricao TEXT NOT NULL, itens TEXT NOT NULL, prazo TEXT,
    tipo TEXT NOT NULL, urgencia TEXT NOT NULL, responsavel TEXT NOT NULL,
    sla_horas INTEGER NOT NULL, status TEXT NOT NULL,
    criado_em TEXT NOT NULL, chave_desc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pedidos_dedup ON pedidos(chave_desc, criado_em);
CREATE TABLE IF NOT EXISTS historico_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    status TEXT NOT NULL, em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER REFERENCES pedidos(id),
    destinatario TEXT NOT NULL, tipo TEXT NOT NULL, status TEXT NOT NULL, criado_em TEXT NOT NULL,
    assunto TEXT NOT NULL DEFAULT '', corpo TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS erros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL, payload TEXT, detalhe TEXT NOT NULL, criado_em TEXT NOT NULL
);
"""


def conectar(caminho: str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def para_naive(dt: datetime) -> datetime:
    """O banco guarda só datas sem fuso (hora local); datas com fuso são convertidas."""
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _iso(dt: datetime) -> str:
    return para_naive(dt).isoformat(timespec="seconds")


def chave_descricao(pedido: dict) -> str:
    """Descrição sem acento, sem pontuação, minúscula e com espaços colapsados."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento(pedido["descricao"])).split())


def inserir_pedido(con, pedido: dict, cls: Classificacao, agora: datetime) -> int:
    pedido_id = _inserir(con, pedido, cls, agora)
    con.commit()
    return pedido_id


def inserir_unico(con, pedido: dict, cls: Classificacao, agora: datetime) -> tuple[int, bool]:
    """Checa duplicidade e insere na mesma transação (BEGIN IMMEDIATE): webhooks simultâneos não duplicam.
    Devolve (id, duplicado)."""
    con.execute("BEGIN IMMEDIATE")
    try:
        existente = achar_duplicado(con, pedido, agora)
        if existente is not None:
            con.rollback()
            return existente, True
        pedido_id = _inserir(con, pedido, cls, agora)
        con.commit()
        return pedido_id, False
    except BaseException:
        con.rollback()
        raise


def _inserir(con, pedido: dict, cls: Classificacao, agora: datetime) -> int:
    cur = con.execute(
        """INSERT INTO pedidos (nome, email, telefone, descricao, itens, prazo, tipo, urgencia,
               responsavel, sla_horas, status, criado_em, chave_desc)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pedido["nome"], pedido["email"], pedido["telefone"], pedido["descricao"],
         json.dumps(pedido["itens"], ensure_ascii=False),
         pedido["prazo"].isoformat() if pedido["prazo"] else None,
         cls.tipo, cls.urgencia, cls.responsavel, cls.sla_horas, "atribuido",
         _iso(agora), chave_descricao(pedido)),
    )
    con.execute("INSERT INTO historico_status (pedido_id, status, em) VALUES (?,?,?)",
                (cur.lastrowid, "atribuido", _iso(agora)))
    return cur.lastrowid


def achar_duplicado(con, pedido: dict, agora: datetime) -> int | None:
    limite = _iso(para_naive(agora) - timedelta(days=JANELA_DUPLICADO_DIAS))
    # mesma descrição normalizada E mesmo e-mail OU mesmo telefone (NULL nunca é igual a nada)
    linha = con.execute(
        """SELECT id FROM pedidos WHERE chave_desc=? AND criado_em>=?
           AND (email=? OR telefone=?) ORDER BY id LIMIT 1""",
        (chave_descricao(pedido), limite, pedido.get("email"), pedido.get("telefone")),
    ).fetchone()
    return linha["id"] if linha else None


def registrar_erro(con, tipo: str, payload, detalhe: str, agora: datetime) -> None:
    try:
        texto = json.dumps(payload, default=str)
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
                          status: str, agora: datetime, assunto: str = "", corpo: str = "") -> int:
    cur = con.execute(
        """INSERT INTO notificacoes (pedido_id, destinatario, tipo, status, criado_em, assunto, corpo)
           VALUES (?,?,?,?,?,?,?)""",
        (pedido_id, destinatario, tipo, status, _iso(agora), assunto, corpo))
    con.commit()
    return cur.lastrowid
