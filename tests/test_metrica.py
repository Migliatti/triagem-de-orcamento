import json
from datetime import timedelta
from pathlib import Path

import pytest

from conftest import AGORA
from triagem import cli, db
from triagem.metrica import calcular

EXEMPLOS = json.loads((Path(__file__).parent.parent / "data" / "pedidos_exemplo.json").read_text(encoding="utf-8"))


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGEM_LOG", str(tmp_path / "a.log"))
    return db.conectar(str(tmp_path / "t.db"))


def carregar_exemplos(con):
    for ex in EXEMPLOS:
        cli.receber({k: v for k, v in ex.items() if k != "_esperado"}, con, AGORA)


def test_metrica_rotulada_simulacao(con):
    assert calcular(con)["rotulo"] == "SIMULAÇÃO"


def test_metrica_calcula_com_exemplos(con):
    carregar_exemplos(con)  # 6 pedidos aceitos
    m = calcular(con)
    assert m["pedidos"] == 6
    assert m["minutos_antes"] == 72.0   # 6 x 12 min
    assert m["minutos_depois"] == 3.0   # 6 x 0,5 min
    assert m["sem_resposta_antes"] == 2  # round(6 x 0,25) = round(1,5) = 2
    assert m["vencidos_depois"] == 0


def test_metrica_conta_vencidos_apos_varredura(con):
    carregar_exemplos(con)
    cli.varrer(con, AGORA + timedelta(hours=100))
    assert calcular(con)["vencidos_depois"] == 6


def test_metrica_banco_vazio_nao_divide_por_zero(con):
    m = calcular(con)
    assert (m["pedidos"], m["minutos_antes"], m["minutos_depois"]) == (0, 0.0, 0.0)


def test_sem_resposta_arredonda_para_cima(con):
    # 10 pedidos x 25% = 2,5 -> 3 (round() daria 2)
    for i in range(10):
        cli.receber({"nome": "A", "contato": f"a{i}@exemplo.test", "descricao": f"mesa {i}"}, con, AGORA)
    assert calcular(con)["sem_resposta_antes"] == 3
