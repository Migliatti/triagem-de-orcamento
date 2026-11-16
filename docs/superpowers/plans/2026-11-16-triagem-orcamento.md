# Triagem de orçamento — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automação que recebe pedidos de orçamento fictícios por webhook, valida, classifica, grava em SQLite, avisa o responsável (alerta simulado) e escalona por prazo.

**Architecture:** Toda a lógica fica em Python puro (`src/triagem`), testável com pytest. O n8n local é fino: webhook → `python -m triagem receber` → ramifica pelo JSON de saída; um fluxo agendado chama `python -m triagem varrer`. Erros tratados saem com exit 0 e `ok:false`, para não quebrar o n8n.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), pytest, n8n local.

**Spec:** `docs/superpowers/specs/2026-11-16-triagem-orcamento-design.md`

## Global Constraints
- Dados 100% fictícios; empresa "Marcenaria Pinheiral"; responsáveis Marta Lopes (sob_medida), Rogério Faria (corporativo), Davi Moura (reparo), Helena Prado (indefinido + escalonamento).
- Urgência pelo prazo: ≤3 dias alta, 4–14 média, >14 ou ausente baixa; "urgente" sobe um nível. SLA: alta 4h, média 24h, baixa 72h.
- Lembrete em 75% do SLA; vencido + escalonamento a Helena em 100%.
- Status: `novo`, `atribuido`, `respondido`, `vencido`. Duplicidade: mesmo contato normalizado + descrição normalizada em 7 dias.
- Normalização: nome Title Case, e-mail minúsculo, telefone só dígitos, prazo ISO.
- Só stdlib + pytest. Sem envio real a terceiros. Métrica rotulada "SIMULAÇÃO".
- Tempo "agora" sempre injetável (parâmetro), nunca lido direto dentro das regras.
- Commits só quando o dono pedir; os passos "Commit" abaixo valem apenas com essa autorização.

## Review Focus
- Descrição só com espaços/maiúsculas diferentes de um pedido anterior → duplicado (Task 4).
- Prazo desejado no passado ou em formato inválido ("amanhã") → não quebra; urgência alta se passado, erro de campo se ilegível (Task 2).
- Contato com e-mail inválido mas telefone válido → aceita pelo telefone (Task 2).
- Descrição casando com duas categorias → desempate fixo documentado, nunca exceção (Task 3).
- Falha de envio simulada → pedido continua gravado, notificação marcada `falha` e reenviada na próxima varredura (Tasks 5–6).

---

### Task 1: Scaffold e pedidos de exemplo ("antes")

**Files:**
- Create: `pyproject.toml`, `.gitignore` (ignora `*.db`, `__pycache__`), `src/triagem/__init__.py`, `data/pedidos_exemplo.json`, `tests/test_exemplos.py`

**Interfaces:**
- Produces: `data/pedidos_exemplo.json` = lista de 10 objetos com chaves livres (bagunçadas) `nome, contato, descricao, itens, prazo` (algumas ausentes/mal formatadas), mais chave `_esperado` (`{"valido": bool, "tipo": str|None, "urgencia": str|None, "motivo_erro": str|None}`) usada pelos testes. Cobrir: 6 válidos (2 por tipo, 1 indefinido), 1 sem contato, 1 sem descrição, 1 duplicata exata de outro com caixa diferente, 1 prazo ilegível.

- [ ] **Step 1: Teste** `test_exemplos_tem_10_pedidos_com_esperado` e `test_exemplos_cobrem_casos_bagunçados` (asserts: len==10; todos têm `_esperado`; ≥1 inválido; ≥1 duplicata).
- [ ] **Step 2:** `pytest tests/test_exemplos.py -v` → FAIL (arquivo ausente).
- [ ] **Step 3:** Criar scaffold (`pyproject.toml` com `pythonpath=["src"]` para pytest) e escrever os 10 pedidos à mão, em português informal, com nomes/telefones/e-mails inventados (e-mails em `@exemplo.test`).
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5: Commit** `feat: scaffold e pedidos de exemplo`.

### Task 2: Validação e normalização

**Files:** Create `src/triagem/validar.py`; Test `tests/test_validar.py`

**Interfaces:**
- Produces: `validar(payload: dict, agora: datetime) -> Resultado` onde `Resultado = dataclass(ok: bool, pedido: dict | None, erros: list[str])`. `pedido` normalizado tem chaves `nome, email, telefone, descricao, itens (list[str]), prazo (date|None), prazo_dias (int|None)`. Erros são códigos: `nome_ausente`, `contato_invalido`, `descricao_ausente`, `prazo_ilegivel`.

- [ ] **Step 1: Testes** (nomes e asserts): `test_normaliza_nome_email_telefone` ("  jOÃO  silva " → "João Silva"; "Ana@Exemplo.TEST" → "ana@exemplo.test"; "(11) 91234-5678" → "11912345678"); `test_sem_contato_erro`; `test_email_invalido_mas_telefone_valido_ok`; `test_sem_descricao_erro`; `test_prazo_formatos` (`"2026-11-20"` e `"20/11/2026"` aceitos, `prazo_dias` correto); `test_prazo_passado_ok_dias_negativos`; `test_prazo_ilegivel_erro` ("amanhã" → `prazo_ilegivel`); `test_itens_string_vira_lista` ("2 mesas, 1 banco" → 2 itens); `test_payload_nao_dict_nao_quebra` (None, lista → `ok False`).
- [ ] **Step 2:** Rodar → FAIL.
- [ ] **Step 3:** Implementar `validar` e dataclass `Resultado`. Telefone válido = 10 ou 11 dígitos; e-mail válido = regex simples com `@` e `.`. Nunca levantar exceção para entrada ruim.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: validação e normalização`.

### Task 3: Classificação, urgência, SLA e responsável

**Files:** Create `src/triagem/classificar.py`; Test `tests/test_classificar.py`

**Interfaces:**
- Consumes: `pedido` normalizado (Task 2).
- Produces: `classificar(pedido: dict) -> Classificacao` com `Classificacao = dataclass(tipo: str, urgencia: str, sla_horas: int, responsavel: str)`; constantes `RESPONSAVEIS: dict[str,str]`, `GESTOR = "Helena Prado"`, `SLA_HORAS = {"alta":4,"media":24,"baixa":72}`, `PALAVRAS_CHAVE` por tipo.

- [ ] **Step 1: Testes:** um por tipo com descrição realista (`cozinha planejada` → sob_medida/Marta; `20 cadeiras para escritório` → corporativo/Rogério; `consertar dobradiça` → reparo/Davi); `test_sem_palavra_chave_indefinido_helena`; `test_empate_prioridade_fixa` (descrição com "reparo" e "escritório" → corporativo; ordem: corporativo > sob_medida > reparo); `test_urgencia_por_prazo` (3→alta, 4→media, 14→media, 15→baixa, None→baixa, -2→alta); `test_palavra_urgente_sobe_nivel` (baixa→media, alta continua alta); `test_sla_por_urgencia` (alta 4, media 24, baixa 72).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementar; busca por palavras-chave em `descricao + itens` em minúsculas sem acentos; empate resolvido pela ordem de prioridade acima.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: classificação por tipo e urgência`.

### Task 4: Banco SQLite

**Files:** Create `src/triagem/db.py`; Test `tests/test_db.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces: `conectar(caminho: str) -> sqlite3.Connection` (cria tabelas `pedidos, historico_status, notificacoes, erros` se faltarem; `row_factory=sqlite3.Row`); `inserir_pedido(con, pedido: dict, cls: Classificacao, agora: datetime) -> int` (status `atribuido`, grava histórico); `achar_duplicado(con, pedido: dict, agora: datetime) -> int | None`; `registrar_erro(con, tipo: str, payload: dict | None, detalhe: str, agora: datetime) -> None`; `mudar_status(con, pedido_id: int, status: str, agora: datetime) -> None`; `registrar_notificacao(con, pedido_id: int | None, destinatario: str, tipo: str, status: str, agora: datetime) -> int` (`tipo`: `novo|lembrete|escalonamento`; `status`: `enviada|falha`). Colunas de `pedidos` incluem `criado_em`, `sla_horas`, `chave_dedup` (contato normalizado + descrição normalizada, minúsculas, espaços colapsados).

- [ ] **Step 1: Testes:** `test_inserir_e_status_inicial_atribuido`; `test_historico_registra_mudancas`; `test_duplicado_ignora_caixa_e_espacos` (mesmo pedido com `"  CABIDEIRO   de parede"` → devolve id original); `test_duplicado_fora_de_7_dias_nao_conta`; `test_registrar_erro_guarda_payload_json`; `test_conectar_idempotente` (chamar duas vezes no mesmo arquivo não falha).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementar com SQL parametrizado; datas em ISO-8601 UTC como texto.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: persistência SQLite`.

### Task 5: CLI `receber` + alerta simulado

**Files:** Create `src/triagem/notificar.py`, `src/triagem/cli.py`, `src/triagem/__main__.py`; Test `tests/test_cli_receber.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `notificar.enviar_simulado(destinatario: str, assunto: str, corpo: str) -> bool` (grava linha em `logs/alertas.log`; devolve False se env `TRIAGEM_FALHA_ENVIO=1`). `cli.receber(payload: dict, con, agora: datetime) -> dict` com saída `{"ok": bool, "pedido_id": int|None, "tipo": str|None, "urgencia": str|None, "responsavel": str|None, "sla_horas": int|None, "erro": str|None, "notificacao": "enviada"|"falha"|None}`; `erro` ∈ `invalido|duplicado|None`. Comando: `python -m triagem receber --db caminho < payload.json` imprime esse JSON, **sempre exit 0** para erros tratados (JSON ilegível também → `erro:"invalido"`).

- [ ] **Step 1: Testes:** `test_receber_valido_grava_e_notifica` (ok True, status `atribuido`, 1 notificação `novo` `enviada` para o responsável); `test_receber_invalido_registra_erro_nao_cria_pedido`; `test_receber_duplicado_registra_erro_duplicado`; `test_falha_de_envio_mantem_pedido_e_marca_falha` (monkeypatch env; pedido existe; notificação `falha`); `test_cli_json_ilegivel_exit_0` (subprocess com stdin `"{{"`).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementar; `receber` usa `validar → achar_duplicado → classificar → inserir_pedido → enviar_simulado → registrar_notificacao`. `__main__` com `argparse`, subcomandos `receber`, `varrer`, `responder`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: comando receber e alerta simulado`.

### Task 6: Varredura de lembretes/escalonamento e resposta

**Files:** Modify `src/triagem/cli.py`; Test `tests/test_cli_varrer.py`

**Interfaces:**
- Consumes: Task 5.
- Produces: `cli.varrer(con, agora: datetime) -> list[dict]`, cada item `{"pedido_id": int, "acao": "lembrete"|"escalonamento"|"reenvio", "destinatario": str}`; `cli.responder(con, pedido_id: int, agora: datetime) -> bool`. Comandos: `python -m triagem varrer --db X [--agora ISO]` (imprime a lista JSON) e `python -m triagem responder --db X --id N`. Regras: pedido `atribuido` com ≥75% do SLA decorrido e sem lembrete → lembrete ao responsável; com ≥100% → status `vencido` + notificação `escalonamento` a Helena; notificações `falha` são reenviadas (acao `reenvio`). `respondido` e `vencido` já escalonado nunca geram nova ação.

- [ ] **Step 1: Testes** com `agora` injetado: `test_antes_de_75_nada`; `test_aos_75_lembrete_uma_vez` (segunda varredura não repete); `test_aos_100_vencido_e_escalona_helena`; `test_respondido_nao_escalona`; `test_reenvia_notificacao_falha` (falha → próxima varredura sem falha → `enviada`); `test_varrer_idempotente`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementar consultando `pedidos` + `notificacoes`; sem estado fora do banco.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: lembretes, escalonamento e resposta`.

### Task 7: Teste ponta a ponta e fluxos n8n

**Files:** Create `tests/test_e2e.py`, `n8n/fluxo_principal.json`, `n8n/fluxo_lembretes.json`, `docs/rodar-n8n.md`

**Interfaces:**
- Consumes: CLI das Tasks 5–6 e `data/pedidos_exemplo.json`.

- [ ] **Step 1: Teste e2e** `test_e2e_pedidos_exemplo`: banco temporário, alimenta os 10 exemplos via subprocess `python -m triagem receber`, compara cada saída com `_esperado` (válido/tipo/urgência/erro); depois `varrer --agora` 5h, 30h e 80h à frente e confere lembretes, vencidos e escalonamentos esperados.
- [ ] **Step 2:** Rodar → FAIL se algum exemplo divergir; ajustar exemplos **ou** regras (decisão consciente, registrada no spec 1 página).
- [ ] **Step 3:** Montar os dois fluxos no n8n local (webhook POST `/webhook/pedido` → Execute Command `python -m triagem receber` com payload no stdin → IF `ok`; agendado de hora em hora → `varrer`). Exportar os JSONs para `n8n/`; `docs/rodar-n8n.md` com comandos de subida (`npx n8n`) e como importar.
- [ ] **Step 4:** pytest completo → PASS. Verificação manual: `curl` ao webhook com um exemplo válido e um inválido; anotar o que foi realmente executado.
- [ ] **Step 5: Commit** `test: e2e e fluxos n8n`.

### Task 8: Métrica antes/depois (simulação)

**Files:** Create `src/triagem/metrica.py`, `docs/metrica.md`; Test `tests/test_metrica.py`

**Interfaces:**
- Produces: `calcular(con, minutos_manual: float = 12.0, minutos_auto: float = 0.5, taxa_sem_resposta_manual: float = 0.25) -> dict` com `{"pedidos": int, "minutos_antes": float, "minutos_depois": float, "sem_resposta_antes": int, "vencidos_depois": int, "rotulo": "SIMULAÇÃO"}`; comando `python -m triagem metrica --db X`.

- [ ] **Step 1: Testes:** `test_metrica_rotulada_simulacao`; `test_metrica_calcula_com_10_pedidos` (valores esperados escritos à mão a partir dos parâmetros); `test_metrica_banco_vazio_nao_divide_por_zero`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar; `docs/metrica.md` lista cada premissa e o aviso de que os números são ilustrativos. **Step 4:** PASS. **Step 5: Commit** `feat: métrica simulada`.

### Task 9: Especificação de uma página e README

**Files:** Create `docs/especificacao.md`, `README.md`

- [ ] **Step 1:** `docs/especificacao.md` (1 página): tabela de tipos/responsáveis, urgência, SLAs, status, duplicidade, erros — copiados do código final, não de memória.
- [ ] **Step 2:** `README.md`: problema, desenho (diagrama em texto), decisões (por que n8n fino, SQLite, alerta simulado), limites (sem nuvem, alerta simulado, métrica simulada), como rodar (`pip install -e .[dev]`, `pytest`, n8n). Aviso explícito: projeto fictício, sem clientes nem resultados reais.
- [ ] **Step 3:** Verificação final: `pytest -q` e checagem de que nada no repositório contém dados reais; listar no README o que foi executado de fato vs. não executado.
- [ ] **Step 4: Commit** `docs: especificação e README`.
