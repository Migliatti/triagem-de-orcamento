import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import AGORA
from triagem import cli, db

RAIZ = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def log_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGEM_LOG", str(tmp_path / "alertas.log"))
    monkeypatch.delenv("TRIAGEM_FALHA_ENVIO", raising=False)


@pytest.fixture
def con(tmp_path):
    return db.conectar(str(tmp_path / "t.db"))


VALIDO = {"nome": "ana", "contato": "ana@exemplo.test",
          "descricao": "cozinha planejada", "prazo": "2026-11-30"}


def test_receber_valido_grava_e_notifica(con):
    r = cli.receber(VALIDO, con, AGORA)
    assert r["ok"] and r["erro"] is None
    assert (r["tipo"], r["urgencia"], r["responsavel"]) == ("sob_medida", "media", "Marta Lopes")
    assert r["notificacao"] == "enviada"
    assert con.execute("SELECT status FROM pedidos WHERE id=?", (r["pedido_id"],)).fetchone()[0] == "atribuido"
    n = con.execute("SELECT destinatario, tipo, status FROM notificacoes").fetchall()
    assert [tuple(x) for x in n] == [("Marta Lopes", "novo", "enviada")]


def test_receber_invalido_registra_erro_nao_cria_pedido(con):
    r = cli.receber({"nome": "x"}, con, AGORA)
    assert not r["ok"] and r["erro"] == "invalido" and r["pedido_id"] is None
    assert con.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 0
    assert con.execute("SELECT tipo FROM erros").fetchone()[0] == "invalido"


def test_receber_duplicado_registra_erro_duplicado(con):
    primeiro = cli.receber(VALIDO, con, AGORA)
    r = cli.receber({**VALIDO, "descricao": "  COZINHA   planejada"}, con, AGORA)
    assert not r["ok"] and r["erro"] == "duplicado" and r["pedido_id"] == primeiro["pedido_id"]
    assert con.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 1
    assert con.execute("SELECT tipo FROM erros").fetchone()[0] == "duplicado"


def test_falha_de_envio_mantem_pedido_e_marca_falha(con, monkeypatch):
    monkeypatch.setenv("TRIAGEM_FALHA_ENVIO", "1")
    r = cli.receber(VALIDO, con, AGORA)
    assert r["ok"] and r["notificacao"] == "falha"
    assert con.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 1
    assert con.execute("SELECT status FROM notificacoes").fetchone()[0] == "falha"


def rodar_cli(args, entrada, tmp_path):
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "TRIAGEM_LOG": str(tmp_path / "a.log")}
    return subprocess.run([sys.executable, "-m", "triagem", *args], input=entrada,
                          capture_output=True, text=True, encoding="utf-8", env=env)


def test_cli_json_ilegivel_exit_0(tmp_path):
    p = rodar_cli(["receber", "--db", str(tmp_path / "c.db")], "{{", tmp_path)
    assert p.returncode == 0
    saida = json.loads(p.stdout)
    assert saida["ok"] is False and saida["erro"] == "invalido"


def test_cli_payload_base64_sem_stdin(tmp_path):
    import base64
    b64 = base64.b64encode(json.dumps({**VALIDO, "nome": "João"}).encode("utf-8")).decode()
    p = rodar_cli(["receber", "--db", str(tmp_path / "c.db"), "--payload-b64", b64], None, tmp_path)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["ok"] is True


def test_cli_valido_imprime_json_utf8(tmp_path):
    entrada = json.dumps({**VALIDO, "nome": "João"}, ensure_ascii=False)
    p = rodar_cli(["receber", "--db", str(tmp_path / "c.db"), "--agora", "2026-11-16T09:00:00"],
                  entrada, tmp_path)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["responsavel"] == "Marta Lopes"
