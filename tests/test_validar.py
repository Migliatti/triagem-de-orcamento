from datetime import date

from conftest import AGORA
from triagem.validar import validar


def base(**extra):
    p = {"nome": "Ana", "contato": "ana@exemplo.test", "descricao": "uma mesa"}
    p.update(extra)
    return p


def test_normaliza_nome_email_telefone():
    r = validar({"nome": "  jOÃO  silva ", "contato": "Ana@Exemplo.TEST",
                 "telefone": "(11) 91234-5678", "descricao": "x"}, AGORA)
    assert r.ok
    assert r.pedido["nome"] == "João Silva"
    assert r.pedido["email"] == "ana@exemplo.test"
    assert r.pedido["telefone"] == "11912345678"


def test_contato_telefone_formatado():
    r = validar(base(contato="(11) 91234-5678"), AGORA)
    assert r.ok and r.pedido["telefone"] == "11912345678" and r.pedido["email"] is None


def test_sem_contato_erro():
    p = base()
    del p["contato"]
    r = validar(p, AGORA)
    assert not r.ok and "contato_invalido" in r.erros and r.pedido is None


def test_email_invalido_mas_telefone_valido_ok():
    r = validar(base(contato="ana@@", telefone="11 91234-5678"), AGORA)
    assert r.ok and r.pedido["email"] is None and r.pedido["telefone"] == "11912345678"


def test_sem_descricao_erro():
    r = validar(base(descricao="   "), AGORA)
    assert not r.ok and "descricao_ausente" in r.erros


def test_sem_nome_erro():
    r = validar(base(nome=""), AGORA)
    assert not r.ok and "nome_ausente" in r.erros


def test_prazo_formatos():
    for texto in ("2026-11-20", "20/11/2026"):
        r = validar(base(prazo=texto), AGORA)
        assert r.pedido["prazo"] == date(2026, 11, 20)
        assert r.pedido["prazo_dias"] == 4


def test_prazo_passado_ok_dias_negativos():
    r = validar(base(prazo="2026-11-14"), AGORA)
    assert r.ok and r.pedido["prazo_dias"] == -2


def test_prazo_ausente_ok():
    for valor in (None, ""):
        r = validar(base(prazo=valor), AGORA)
        assert r.ok and r.pedido["prazo"] is None and r.pedido["prazo_dias"] is None


def test_prazo_ilegivel_erro():
    r = validar(base(prazo="amanhã"), AGORA)
    assert not r.ok and "prazo_ilegivel" in r.erros


def test_itens_string_vira_lista():
    r = validar(base(itens="2 mesas, 1 banco"), AGORA)
    assert r.pedido["itens"] == ["2 mesas", "1 banco"]


def test_payload_nao_dict_nao_quebra():
    for lixo in (None, [], "texto", 42):
        r = validar(lixo, AGORA)
        assert not r.ok and r.erros


def test_telefone_com_prefixo_55():
    r = validar(base(contato="+55 11 91234-5678"), AGORA)
    assert r.ok and r.pedido["telefone"] == "11912345678"


def test_email_invalido_nao_vira_telefone():
    r = validar(base(contato="11987654321@gmail"), AGORA)
    assert not r.ok and "contato_invalido" in r.erros


def test_surrogate_solto_nao_quebra():
    r = validar(base(nome="\ud800ana"), AGORA)
    assert r.ok
    r.pedido["nome"].encode("utf-8")  # não pode levantar
