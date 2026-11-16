# Especificação — Marcenaria Pinheiral (empresa fictícia)

Regras implementadas em `src/triagem/classificar.py`, `validar.py` e `cli.py`.

**Tipos e responsáveis** (primeiro tipo com palavra-chave encontrada vence, nesta ordem; sem acento, em descrição + itens):
| Prioridade | Tipo | Exemplos de palavras | Responsável |
|---|---|---|---|
| 1 | `corporativo` | escritório, loja, empresa, estações, mobiliário | Rogério Faria |
| 2 | `sob_medida` | armário, cozinha, guarda-roupa, planejado, closet | Marta Lopes |
| 3 | `reparo` | consertar, dobradiça, reparo, emperrou, lixar | Davi Moura |
| — | `indefinido` | nenhuma palavra casou | Helena Prado (gestora) |

**Urgência** pelo prazo desejado: ≤3 dias (ou já passado) alta · 4–14 média · >14 ou sem prazo baixa. A palavra "urgente" sobe um nível (máximo alta).
**SLA de resposta:** alta 4h · média 24h · baixa 72h.
**Status:** `atribuido` (ao gravar) → `respondido` (comando `responder`) ou `vencido` (a varredura aos 100% do SLA). O estado `novo` do brief é coberto pelo instante da gravação, que já atribui o responsável.
**Lembrete:** aos 75% do SLA, uma vez, ao responsável. **Escalonamento:** aos 100%, à Helena Prado.
**Validação:** obrigatórios nome, contato (e-mail ou telefone de 10–11 dígitos) e descrição; prazo, se vier, deve ser `AAAA-MM-DD` ou `DD/MM/AAAA`.
**Erros** vão para a tabela `erros` e o fluxo continua: `invalido`, `duplicado` (mesmo contato + descrição normalizados em 7 dias).
**Falha de envio:** a notificação fica `falha` e é reenviada na próxima varredura; o pedido não se perde.
**Alerta:** simulado, gravado em `logs/alertas.log` e na tabela `notificacoes`; nada sai da máquina.
