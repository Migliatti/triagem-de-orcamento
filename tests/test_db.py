import json
from datetime import timedelta

import pytest

from conftest import AGORA
from triagem import db
from triagem.classificar import classificar
from triagem.validar import validar


@pytest.fixture
def con(tmp_path):
    return db.conectar(str(tmp_path / "t.db"))


def novo(**extra):
    p = {"nome": "Ana", "contato": "ana@exemplo.test", "descricao": "cabideiro de parede"}
    p.update(extra)
    pedido = validar(p, AGORA).pedido
    return pedido, classificar(pedido)


def test_inserir_e_status_inicial_atribuido(con):
    pedido, cls = novo()
    pid = db.inserir_pedido(con, pedido, cls, AGORA)
    linha = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
    assert linha["status"] == "atribuido"
    assert linha["responsavel"] == cls.responsavel
    assert linha["sla_horas"] == cls.sla_horas


def test_historico_registra_mudancas(con):
    pedido, cls = novo()
    pid = db.inserir_pedido(con, pedido, cls, AGORA)
    db.mudar_status(con, pid, "vencido", AGORA + timedelta(hours=80))
    status = [r["status"] for r in con.execute(
        "SELECT status FROM historico_status WHERE pedido_id=? ORDER BY id", (pid,))]
    assert status == ["atribuido", "vencido"]
    assert con.execute("SELECT status FROM pedidos WHERE id=?", (pid,)).fetchone()["status"] == "vencido"


def test_duplicado_ignora_caixa_e_espacos(con):
    pedido, cls = novo()
    pid = db.inserir_pedido(con, pedido, cls, AGORA)
    outro, _ = novo(contato="ANA@exemplo.test", descricao="  CABIDEIRO   de parede ")
    assert db.achar_duplicado(con, outro, AGORA + timedelta(days=1)) == pid


def test_pedido_diferente_nao_e_duplicado(con):
    pedido, cls = novo()
    db.inserir_pedido(con, pedido, cls, AGORA)
    outro, _ = novo(descricao="outra coisa")
    assert db.achar_duplicado(con, outro, AGORA) is None


def test_duplicado_fora_de_7_dias_nao_conta(con):
    pedido, cls = novo()
    db.inserir_pedido(con, pedido, cls, AGORA)
    assert db.achar_duplicado(con, pedido, AGORA + timedelta(days=8)) is None


def test_registrar_erro_guarda_payload_json(con):
    db.registrar_erro(con, "invalido", {"nome": "X"}, "contato_invalido", AGORA)
    linha = con.execute("SELECT * FROM erros").fetchone()
    assert linha["tipo"] == "invalido" and linha["detalhe"] == "contato_invalido"
    assert json.loads(linha["payload"]) == {"nome": "X"}


def test_registrar_notificacao(con):
    nid = db.registrar_notificacao(con, None, "Helena Prado", "escalonamento", "falha", AGORA)
    assert con.execute("SELECT status FROM notificacoes WHERE id=?", (nid,)).fetchone()["status"] == "falha"


def test_conectar_idempotente(tmp_path):
    caminho = str(tmp_path / "x.db")
    db.conectar(caminho).close()
    db.conectar(caminho).close()


def test_duplicado_ignora_acento_e_pontuacao(con):
    pedido, cls = novo(descricao="Orçamento: armário!")
    pid = db.inserir_pedido(con, pedido, cls, AGORA)
    outro, _ = novo(descricao="orcamento  ARMARIO")
    assert db.achar_duplicado(con, outro, AGORA) == pid


def test_duplicado_por_telefone_quando_email_difere(con):
    pedido, cls = novo(contato="ana@exemplo.test", telefone="11 91234-5678")
    pid = db.inserir_pedido(con, pedido, cls, AGORA)
    so_tel, _ = novo(contato="(11) 91234-5678")
    assert db.achar_duplicado(con, so_tel, AGORA) == pid


def test_datas_com_fuso_sao_gravadas_sem_fuso(con):
    from datetime import datetime, timedelta, timezone
    aware = datetime(2026, 11, 16, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
    pedido, cls = novo()
    pid = db.inserir_pedido(con, pedido, cls, aware)
    criado = con.execute("SELECT criado_em FROM pedidos WHERE id=?", (pid,)).fetchone()[0]
    assert "+" not in criado and "-03" not in criado
