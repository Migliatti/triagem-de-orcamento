# Triagem automática de pedidos de orçamento — Design

Data: 2026-11-16 · Status: aguardando aprovação do dono

## Intenção
Projeto de portfólio de automação de processos. Mostra uma bagunça (pedidos por vários canais, sem padrão, esquecidos) virando regras que rodam sozinhas, com métrica de antes e depois. O dono (dev júnior) precisa explicar e defender cada parte: simplicidade e legibilidade vencem sofisticação.

## Metas
- Receber pedido por webhook, validar, normalizar, classificar (tipo + urgência), gravar, avisar o responsável certo.
- Lembrar e escalonar quando não há resposta no prazo.
- Registrar erros (inválido, duplicado, falha de envio) sem quebrar o fluxo.
- Métrica antes/depois sobre dados fictícios, rotulada como simulação.
- Testes: regra Python (unitários) e ao menos um fluxo ponta a ponta.
- README / estudo de caso: problema, desenho, decisões, limites, como rodar.

## Não metas / anti-metas
- Sem dados reais, sem empregador atual, sem afirmar uso real, clientes ou resultados de mercado.
- Sem envio real a terceiros, sem custo, sem publicar nada sem aprovação.
- Anti-meta: algo sofisticado que o dono não consiga explicar.

## Abordagens consideradas
- A. n8n faz quase tudo: fluxo visual, mas lógica espalhada em nós e difícil de testar. Descartada.
- **B. n8n fino + Python com a lógica (escolhida pelo dono).** n8n orquestra; Python valida, classifica e grava; testável com pytest sem subir o n8n.
- C. Serviço FastAPI com n8n só agendador: n8n vira enfeite e o projeto cresce demais. Descartada.

## Decisões do dono
SQLite · n8n local (Execute Command chama Python, por isso não serve a nuvem gratuita) · este repositório · alerta simulado (tabela `notificacoes` + log) · abordagem B.

## Empresa fictícia (minha proposta)
**Marcenaria Pinheiral** (nome inventado), móveis sob medida e reformas leves.

| Tipo | Quando | Responsável (fictício) |
|---|---|---|
| `sob_medida` | móveis planejados residenciais | Marta Lopes |
| `corporativo` | lojas, escritórios, volume | Rogério Faria |
| `reparo` | conserto/ajuste de peça existente | Davi Moura |
| `indefinido` | não casou com regra | Helena Prado (gestora, triagem manual) |

Helena também recebe todo escalonamento.

## Regras (proposta, ajustável na especificação)
- **Tipo:** palavras-chave na descrição/itens (ex.: "armário", "cozinha" → sob_medida; "escritório", "loja", "20 cadeiras" → corporativo; "consertar", "dobradiça", "reparo" → reparo). Empate ou nenhuma → `indefinido`. Prioridade fixa em caso de empate, documentada.
- **Urgência** pelo prazo desejado (dias até a data): ≤3 alta, 4–14 média, >14 ou ausente baixa. Palavras como "urgente" sobem um nível.
- **SLA de resposta:** alta 4h, média 24h, baixa 72h.
- **Lembrete** ao responsável em 75% do SLA; **vencido + escalonamento** à Helena em 100%.
- **Status:** `novo` → `atribuido` → `respondido` | `vencido`.
- **Normalização:** nome em Title Case, e-mail em minúsculas, telefone só dígitos, prazo em ISO.
- **Validação:** obrigatórios nome, contato (e-mail ou telefone válido), descrição. Faltando → registro em `erros`, resposta 422, fluxo segue.
- **Duplicidade:** mesmo contato normalizado + descrição normalizada em 7 dias → registra em `erros` como duplicado, não cria pedido.
- **Falha de envio:** o alerta simulado pode falhar (falha injetável em teste); grava `notificacoes.status = falha` e tenta de novo no próximo ciclo.

## Estrutura
```
data/pedidos_exemplo.json      # 8–10 pedidos bagunçados ("antes")
src/triagem/                   # validar.py, classificar.py, db.py, cli.py
tests/                         # pytest: regras + ponta a ponta
n8n/fluxo_principal.json       # webhook → cli → ramifica → notifica
n8n/fluxo_lembretes.json       # agendado (a cada hora) → cli vencidos
docs/                          # especificação 1 página, métrica, estudo de caso
```
Tabelas SQLite: `pedidos`, `historico_status`, `notificacoes`, `erros`.

## Métrica (simulação)
Linha de base manual assumida (ex.: 12 min por triagem, % sem resposta no prazo) contra o tempo automatizado e pedidos vencidos nos mesmos dados de exemplo. Premissas explícitas e rótulo "SIMULAÇÃO" em tudo.

## Entregas em ordem
1. Empresa + pedidos de exemplo ("antes") · 2. Especificação de 1 página · 3. Fluxo mínimo webhook→validação→banco→alerta · 4. Escalonamento, erros, métrica · 5. README/estudo de caso.

## Deixado ao implementador
Nomes de arquivos/colunas, formato exato do JSON de saída do CLI, lista final de palavras-chave, redação dos pedidos de exemplo.

## Em aberto
Horas semanais do dono (ajusta ritmo; se pouco, escalonamento e métrica vão por último).
