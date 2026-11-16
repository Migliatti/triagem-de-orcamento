import pytest

from triagem.classificar import GESTOR, SLA_HORAS, classificar


def pedido(descricao="", itens=(), prazo_dias=None):
    return {"descricao": descricao, "itens": list(itens), "prazo_dias": prazo_dias}


@pytest.mark.parametrize("descricao,tipo,resp", [
    ("Quero uma cozinha planejada", "sob_medida", "Marta Lopes"),
    ("20 cadeiras para escritório", "corporativo", "Rogério Faria"),
    ("preciso consertar a dobradiça", "reparo", "Davi Moura"),
])
def test_tipo_por_palavra_chave(descricao, tipo, resp):
    c = classificar(pedido(descricao))
    assert (c.tipo, c.responsavel) == (tipo, resp)


def test_sem_palavra_chave_indefinido_helena():
    c = classificar(pedido("vocês trabalham com madeira?"))
    assert c.tipo == "indefinido" and c.responsavel == GESTOR == "Helena Prado"


def test_empate_prioridade_fixa():
    # corporativo > reparo > sob_medida
    assert classificar(pedido("reparo no escritório")).tipo == "corporativo"
    assert classificar(pedido("consertar armário")).tipo == "reparo"


def test_palavras_em_itens_e_sem_acento():
    assert classificar(pedido("orçamento", itens=["ARMÁRIO"])).tipo == "sob_medida"


@pytest.mark.parametrize("dias,urgencia", [
    (3, "alta"), (4, "media"), (14, "media"), (15, "baixa"), (None, "baixa"), (-2, "alta"),
])
def test_urgencia_por_prazo(dias, urgencia):
    assert classificar(pedido("mesa", prazo_dias=dias)).urgencia == urgencia


def test_palavra_urgente_sobe_nivel():
    assert classificar(pedido("URGENTE mesa", prazo_dias=30)).urgencia == "media"
    assert classificar(pedido("urgente mesa", prazo_dias=10)).urgencia == "alta"
    assert classificar(pedido("urgente mesa", prazo_dias=1)).urgencia == "alta"


def test_sla_por_urgencia():
    assert SLA_HORAS == {"alta": 4, "media": 24, "baixa": 72}
    assert classificar(pedido("mesa", prazo_dias=1)).sla_horas == 4
    assert classificar(pedido("mesa", prazo_dias=10)).sla_horas == 24
    assert classificar(pedido("mesa")).sla_horas == 72


def test_reparo_vence_sob_medida_mas_nao_corporativo():
    assert classificar(pedido("conserto da porta do armário")).tipo == "reparo"
    assert classificar(pedido("consertar cadeira do escritório")).tipo == "corporativo"


def test_palavra_chave_so_no_inicio_da_palavra():
    assert classificar(pedido("preparo de superfície")).tipo == "indefinido"  # não é "reparo"
    assert classificar(pedido("reparo na mesa")).tipo == "reparo"


def test_negacao_de_urgente_nao_sobe_nivel():
    assert classificar(pedido("mesa, não é urgente", prazo_dias=30)).urgencia == "baixa"
    assert classificar(pedido("mesa nao urgente", prazo_dias=30)).urgencia == "baixa"
    assert classificar(pedido("mesa urgente", prazo_dias=30)).urgencia == "media"
