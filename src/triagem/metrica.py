"""Métrica antes/depois. SIMULAÇÃO: as premissas abaixo são ilustrativas, não medidas de uso real."""

import math

ROTULO = "SIMULAÇÃO"


def calcular(con, minutos_manual: float = 12.0, minutos_auto: float = 0.5,
             taxa_sem_resposta_manual: float = 0.25) -> dict:
    pedidos = con.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0]
    vencidos = con.execute("SELECT COUNT(*) FROM pedidos WHERE status='vencido'").fetchone()[0]
    return {
        "rotulo": ROTULO,
        "pedidos": pedidos,
        "minutos_antes": pedidos * minutos_manual,
        "minutos_depois": pedidos * minutos_auto,
        "sem_resposta_antes": math.ceil(pedidos * taxa_sem_resposta_manual),
        "vencidos_depois": vencidos,
    }
