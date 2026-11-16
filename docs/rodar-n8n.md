# Rodar os fluxos no n8n local

Os fluxos em `n8n/` são finos: só chamam o CLI Python (`python -m triagem ...`). Toda a regra está em `src/triagem` e é testada com pytest.

**Status de verificação:** testado de verdade com o n8n 2.47.7 local (baixado via `npx`), em 2026-11-16. Resultados:
- `fluxo_principal`: `curl` com pedido válido → HTTP 200; inválido → 422; duplicado → 409. Pedido gravado no SQLite e alerta no `logs/alertas.log`.
- `fluxo_lembretes`: executado pelo agendador do n8n (cópia de teste a cada 1 minuto, não incluída no repositório). Com o pedido recuado no banco para 20h, saiu o lembrete; recuado para 30h, ficou `vencido` e a Helena foi avisada.
- O teste revelou um erro real: `Buffer` não existe em expressões do n8n, então a codificação base64 foi para um nó Code ("Codificar payload").
- Não testado: o agendamento de 1 hora de fato (só a cópia de 1 minuto), nem o nó Execute Command fora do Windows (o comando usa `cd /d` e `.venv\Scripts`).

## Passos
1. Preparar o Python: `python -m venv .venv`, `.venv\Scripts\pip install -e .[dev]`.
2. Subir o n8n com o nó Execute Command habilitado (desabilitado por padrão nas versões recentes):
   `set NODES_EXCLUDE=[]` e depois `npx n8n`
3. Importar `n8n/fluxo_principal.json` e `n8n/fluxo_lembretes.json` (menu ⋯ → Import from file).
4. Nos nós "Python: receber" e "Python: varrer", trocar `<CAMINHO_DO_PROJETO>` pelo caminho local do repositório.
5. Ativar os fluxos e testar o webhook:
   `curl -X POST http://localhost:5678/webhook/pedido -H "Content-Type: application/json" -d "{\"nome\":\"Ana\",\"contato\":\"ana@exemplo.test\",\"descricao\":\"cozinha planejada\"}"`
   Respostas esperadas: 200 (aceito), 422 (inválido), 409 (duplicado). Acentos exigem corpo em UTF-8 (`--data-binary @arquivo.json`); `curl -d` direto no Git Bash do Windows corrompe os acentos.
   Dica sem interface: `n8n import:workflow --input=...` e `n8n publish:workflow --id=...` ativam os fluxos pela linha de comando.
6. Ver o resultado: `logs/alertas.log` (alertas simulados) e o banco `triagem.db`.

O Execute Command não aceita stdin, por isso o payload vai em base64 pelo argumento `--payload-b64`.
