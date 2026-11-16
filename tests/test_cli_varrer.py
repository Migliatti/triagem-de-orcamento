from datetime import timedelta

import pytest

from conftest import AGORA
from triagem import cli, db


@pytest.fixture(autouse=True)
def log_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGEM_LOG", str(tmp_path / "alertas.log"))
    monkeypatch.delenv("TRIAGEM_FALHA_ENVIO", raising=False)


@pytest.fixture
def con(tmp_path):
    return db.conectar(str(tmp_path / "t.db"))


def pedido_alta(con):
    """Pedido de urgência alta (SLA 4h), responsável Marta."""
    r = cli.receber({"nome": "Ana", "contato": "ana@exemplo.test",
                     "descricao": "cozinha planejada", "prazo": "2026-11-17"}, con, AGORA)
    assert r["sla_horas"] == 4
    return r["pedido_id"]


def horas(h):
    return AGORA + timedelta(hours=h)


def status(con, pid):
    return con.execute("SELECT status FROM pedidos WHERE id=?", (pid,)).fetchone()[0]


def test_antes_de_75_nada(con):
    pedido_alta(con)
    assert cli.varrer(con, horas(2.9)) == []


def test_aos_75_lembrete_uma_vez(con):
    pid = pedido_alta(con)
    assert cli.varrer(con, horas(3)) == [
        {"pedido_id": pid, "acao": "lembrete", "destinatario": "Marta Lopes"}]
    assert cli.varrer(con, horas(3.5)) == []
    assert status(con, pid) == "atribuido"


def test_aos_100_vencido_e_escalona_helena(con):
    pid = pedido_alta(con)
    assert cli.varrer(con, horas(4)) == [
        {"pedido_id": pid, "acao": "escalonamento", "destinatario": "Helena Prado"}]
    assert status(con, pid) == "vencido"
    assert cli.varrer(con, horas(10)) == []


def test_lembrete_e_depois_escalonamento(con):
    pid = pedido_alta(con)
    cli.varrer(con, horas(3))
    acoes = cli.varrer(con, horas(4.5))
    assert [a["acao"] for a in acoes] == ["escalonamento"]
    assert status(con, pid) == "vencido"


def test_respondido_nao_escalona(con):
    pid = pedido_alta(con)
    assert cli.responder(con, pid, horas(1)) is True
    assert status(con, pid) == "respondido"
    assert cli.varrer(con, horas(100)) == []


def test_responder_pedido_inexistente(con):
    assert cli.responder(con, 999, AGORA) is False


def test_reenvia_notificacao_falha(con, monkeypatch):
    monkeypatch.setenv("TRIAGEM_FALHA_ENVIO", "1")
    pid = pedido_alta(con)
    monkeypatch.delenv("TRIAGEM_FALHA_ENVIO")
    acoes = cli.varrer(con, horas(1))
    assert acoes == [{"pedido_id": pid, "acao": "reenvio", "destinatario": "Marta Lopes"}]
    assert con.execute("SELECT status FROM notificacoes").fetchone()[0] == "enviada"


def test_reenvio_continua_falhando_sem_acao(con, monkeypatch):
    monkeypatch.setenv("TRIAGEM_FALHA_ENVIO", "1")
    pedido_alta(con)
    assert cli.varrer(con, horas(1)) == []
    assert con.execute("SELECT status FROM notificacoes").fetchone()[0] == "falha"


def test_varrer_idempotente(con):
    pedido_alta(con)
    cli.varrer(con, horas(5))
    assert cli.varrer(con, horas(5)) == []


def test_reenvio_usa_texto_original(con, monkeypatch, tmp_path):
    monkeypatch.setenv("TRIAGEM_FALHA_ENVIO", "1")
    pedido_alta(con)
    monkeypatch.delenv("TRIAGEM_FALHA_ENVIO")
    cli.varrer(con, horas(1))
    log = (tmp_path / "alertas.log").read_text(encoding="utf-8")
    assert "Novo pedido #1" in log and "cozinha planejada" in log


def test_reenvio_pula_pedido_ja_respondido(con, monkeypatch):
    monkeypatch.setenv("TRIAGEM_FALHA_ENVIO", "1")
    pid = pedido_alta(con)
    monkeypatch.delenv("TRIAGEM_FALHA_ENVIO")
    cli.responder(con, pid, horas(0.5))
    assert cli.varrer(con, horas(1)) == []
