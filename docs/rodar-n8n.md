# Rodar os fluxos no n8n local

Os fluxos em `n8n/` são finos: só chamam o CLI Python (`python -m triagem ...`). Toda a regra está em `src/triagem` e é testada com pytest.

**Status de verificação:** os JSONs foram escritos à mão e **não foram importados nem executados em um n8n real** neste repositório. O que foi testado de verdade é o CLI que eles chamam (`tests/test_e2e.py`). Valide a importação antes de afirmar que o fluxo roda.

## Passos
1. Preparar o Python: `python -m venv .venv`, `.venv\Scripts\pip install -e .[dev]`.
2. Subir o n8n com o nó Execute Command habilitado (desabilitado por padrão nas versões recentes):
   `set NODES_EXCLUDE=[] && npx n8n`
3. Importar `n8n/fluxo_principal.json` e `n8n/fluxo_lembretes.json` (menu ⋯ → Import from file).
4. Nos nós "Python: receber" e "Python: varrer", trocar `<CAMINHO_DO_PROJETO>` pelo caminho local do repositório.
5. Ativar os fluxos e testar o webhook:
   `curl -X POST http://localhost:5678/webhook/pedido -H "Content-Type: application/json" -d "{\"nome\":\"Ana\",\"contato\":\"ana@exemplo.test\",\"descricao\":\"cozinha planejada\"}"`
   (use `/webhook-test/pedido` enquanto o fluxo estiver em modo de teste).
6. Ver o resultado: `logs/alertas.log` (alertas simulados) e o banco `triagem.db`.

O Execute Command não aceita stdin, por isso o payload vai em base64 pelo argumento `--payload-b64`.
