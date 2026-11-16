# Métrica antes/depois — SIMULAÇÃO

Tudo aqui é simulação sobre os 10 pedidos fictícios de `data/pedidos_exemplo.json`. Não há uso real, clientes nem resultado de mercado.

## Premissas (ilustrativas, ajustáveis em `src/triagem/metrica.py`)
| Premissa | Valor | Origem |
|---|---|---|
| Minutos por triagem manual | 12 | inventado |
| Minutos por triagem automática | 0,5 | inventado |
| Pedidos sem resposta no processo manual | 25% | inventado |

## Resultado com os exemplos (6 pedidos aceitos; 4 rejeitados e registrados em `erros`)
| | Antes (manual) | Depois (automático) |
|---|---|---|
| Minutos de triagem | 72 | 3 |
| Pedidos sem resposta | 2 (25% arredondado para cima) | 0 até o SLA; os que passarem dele viram `vencido` e escalonam para a gestora |

Rodar: `python -m triagem metrica --db triagem.db`. A saída traz `"rotulo": "SIMULAÇÃO"`.

## Limites
Os números "antes" vêm das premissas, não de medição. Servem para ilustrar o raciocínio, não para provar ganho.
