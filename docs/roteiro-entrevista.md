# Roteiro para explicar e defender o projeto

Perguntas que um recrutador ou entrevistador técnico provavelmente faria, com respostas curtas baseadas no que o código realmente faz. Frase-chave para abrir: *"É uma simulação com dados fictícios: mostra como regras simples e testadas substituem uma triagem manual."*

## Visão geral
**1. O que o projeto faz, em 30 segundos?**
Recebe pedidos de orçamento de uma marcenaria fictícia por webhook, valida e normaliza, classifica por tipo e urgência, grava no SQLite, avisa o responsável e, se ninguém responde no prazo, manda lembrete e escalona para a gestora.

**2. Por que automatizar isso?**
Pedidos chegam bagunçados (contato faltando, prazo "quando der", duplicados) e ninguém cobra resposta. As regras rodam sozinhas e deixam rastro no banco. Os números de ganho são **simulação**, com premissas inventadas e declaradas em `docs/metrica.md`.

**3. Por que n8n fino + Python, e não tudo no n8n?**
A lógica em Python é testável com pytest sem subir o n8n e fica legível num arquivo só. O n8n entra para o que ele faz bem: receber o webhook, agendar e ramificar pela resposta.

## Decisões técnicas
**4. Como a classificação funciona? Por que não usar IA?**
Palavras-chave no início de palavra, sem acento, em descrição e itens, com prioridade fixa (corporativo, reparo, sob_medida). Nada casou vira `indefinido` e vai para a Helena. Escolhi regra simples porque dá para explicar e testar cada caso; o limite é que textos fora do vocabulário caem em `indefinido`.

**5. Como a urgência é definida?**
Pelo prazo desejado: até 3 dias alta, 4 a 14 média, acima disso ou sem prazo baixa. "Urgente" sobe um nível, a não ser que venha negado ("não é urgente"). O SLA sai da urgência: 4h, 24h ou 72h.

**6. Como funciona o escalonamento?**
O n8n roda `varrer` a cada hora. Com 75% do SLA gasto, sai um lembrete ao responsável (uma vez). Com 100%, o pedido vira `vencido` e a Helena é avisada. A hora atual é um parâmetro, o que permite testar sem esperar.

**7. Como trata duplicados?**
Compara a descrição sem acento e pontuação, e e-mail **ou** telefone iguais, em 7 dias. A checagem e a gravação ficam na mesma transação (`BEGIN IMMEDIATE`), então oito webhooks simultâneos gravam um pedido só. Há um teste com threads para isso.

**8. E se o envio do alerta falhar?**
O pedido continua gravado, a notificação fica `falha` com o texto original e a próxima varredura reenvia (a não ser que o pedido já tenha sido respondido). Os testes simulam falha por variável de ambiente e por erro de arquivo.

**9. Como o fluxo não quebra com dado ruim?**
O Python sempre responde um JSON com `ok` true ou false e exit 0. Erro tratado vai para a tabela `erros`. O n8n responde 422 (inválido), 409 (duplicado) ou 500 (erro interno). Corpo grande demais vira `payload_grande` em vez de estourar a linha de comando do Windows.

## Testes e honestidade
**10. O que foi testado?**
78 testes pytest (regras, banco, CLI, concorrência, métrica) e um ponta a ponta que passa os 10 pedidos de exemplo pelo CLI real. Os fluxos n8n foram testados à mão num n8n 2.47.7 local: 200, 422, 409, lembrete e escalonamento.

**11. O que não foi testado ou tem limite?**
O agendamento de 1 hora de verdade (usei uma cópia de 1 minuto), o Execute Command fora do Windows, e a nuvem gratuita do n8n, que não permite esse nó. O GitHub Actions foi escrito mas nunca executado. A métrica usa premissas inventadas.

**12. Um bug que você encontrou?**
Ao testar no n8n real, o fluxo dava 500 porque `Buffer` não existe nas expressões do n8n. A solução foi codificar o payload em base64 num nó Code. Os testes do CLI sozinhos não teriam mostrado isso.

**13. Usou IA para fazer?**
Responda com sinceridade: o desenho, o código e a revisão foram feitos com apoio do Claude Code, e você revisou e consegue explicar cada parte. Se não conseguir explicar algo, diga que está estudando.

## Se perguntarem "e se fosse produção?"
- Postgres no lugar do SQLite e fila para o webhook.
- E-mail ou Telegram reais no lugar do alerta simulado, trocando só `notificar.py`.
- Autenticação no webhook, tamanho máximo de corpo no proxy e migrações de banco (hoje o esquema é criado do zero).
- Medir a métrica com dados reais, não simulados.

## Para treinar
Abra `src/triagem/cli.py` e explique `receber` linha a linha, depois rode `python -m pytest -q` e mostre um teste falhando de propósito (por exemplo, mude o SLA de alta para 5 e veja quais testes quebram).
