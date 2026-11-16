import json
from pathlib import Path

CAMINHO = Path(__file__).parent.parent / "data" / "pedidos_exemplo.json"


def carregar():
    return json.loads(CAMINHO.read_text(encoding="utf-8"))


def test_exemplos_tem_10_pedidos_com_esperado():
    pedidos = carregar()
    assert len(pedidos) == 10
    assert all("_esperado" in p for p in pedidos)


def test_exemplos_cobrem_casos_bagunçados():
    esperados = [p["_esperado"] for p in carregar()]
    assert any(not e["valido"] for e in esperados)
    assert any(e["motivo_erro"] == "duplicado" for e in esperados)
    assert {e["tipo"] for e in esperados if e["valido"]} == {
        "sob_medida", "corporativo", "reparo", "indefinido",
    }
