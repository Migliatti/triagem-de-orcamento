"""Ponta a ponta: os 10 pedidos bagunçados passam pelo CLI real (subprocess), como o n8n faria."""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from conftest import AGORA

RAIZ = Path(__file__).parent.parent
EXEMPLOS = json.loads((RAIZ / "data" / "pedidos_exemplo.json").read_text(encoding="utf-8"))


def cli(tmp_path, *args, entrada=None):
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "TRIAGEM_LOG": str(tmp_path / "alertas.log")}
    env.pop("TRIAGEM_FALHA_ENVIO", None)
    p = subprocess.run([sys.executable, "-m", "triagem", *args, "--db", str(tmp_path / "e2e.db")],
                       input=entrada, capture_output=True, text=True, encoding="utf-8", env=env)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_e2e_pedidos_exemplo(tmp_path):
    agora = AGORA.isoformat()
    for ex in EXEMPLOS:
        esperado = ex["_esperado"]
        payload = {k: v for k, v in ex.items() if k != "_esperado"}
        r = cli(tmp_path, "receber", "--agora", agora, entrada=json.dumps(payload))
        assert r["ok"] is esperado["valido"], ex["nome"]
        if esperado["valido"]:
            assert (r["tipo"], r["urgencia"]) == (esperado["tipo"], esperado["urgencia"]), ex["nome"]
        else:
            assert r["erro"] in ("invalido", "duplicado")
            if esperado["motivo_erro"] == "duplicado":
                assert r["erro"] == "duplicado"
            else:
                assert esperado["motivo_erro"] in r["detalhe"]

    con = sqlite3.connect(tmp_path / "e2e.db")
    assert con.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 6
    assert con.execute("SELECT COUNT(*) FROM erros").fetchone()[0] == 4

    def varrer(horas):
        from datetime import timedelta
        return cli(tmp_path, "varrer", "--agora", (AGORA + timedelta(hours=horas)).isoformat())

    # 6 pedidos: 2 alta (SLA 4h), 2 media (24h), 2 baixa (72h)
    assert varrer(2) == []
    aos_4h = varrer(4)
    assert sorted(a["acao"] for a in aos_4h) == ["escalonamento", "escalonamento"]
    assert all(a["destinatario"] == "Helena Prado" for a in aos_4h)
    aos_20h = varrer(20)
    assert sorted(a["acao"] for a in aos_20h) == ["lembrete", "lembrete"]
    aos_30h = varrer(30)
    assert sorted(a["acao"] for a in aos_30h) == ["escalonamento", "escalonamento"]
    assert sorted(a["acao"] for a in varrer(55)) == ["lembrete", "lembrete"]
    assert sorted(a["acao"] for a in varrer(80)) == ["escalonamento", "escalonamento"]
    assert varrer(200) == []
    assert con.execute("SELECT COUNT(*) FROM pedidos WHERE status='vencido'").fetchone()[0] == 6
