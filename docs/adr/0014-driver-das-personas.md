# ADR 0014 — Driver das personas do M3: scripts Python contra a API HTTP do `serve`

- **Status:** aceita (2026-10-10, dono)
- **Data:** 2026-10-09
- **Relacionada:** ADR 0008 (backend do acervo), `docs/M3_plano.md` fase M3.0,
  HANDOFF §M3 item 1 (personas sintéticas)

## Contexto

O M3 transforma o DemoMuseum em cliente virtual: personas sintéticas
(`owner@demo`, `team@demo`) executam rotinas diárias, semanais e pontuais de
curadoria, e um gerador de uso indevido tenta quebrar o produto. A primeira
decisão é **por onde esses atores agem**. O que pesa:

1. **A restrição nº 1 do plano M3**: o cliente virtual age pelo caminho do
   curador real — nunca por atalho interno (editar `.musa/` direto, chamar
   função do builder). Se uma rotina não é possível pela interface pública,
   isso é um achado, não um convite a gambiarra.
2. **O caminho do curador real hoje é a API HTTP do `musa-build serve`** — é
   ela que o admin web consome (login, criar coleção, criar/editar item,
   publicar). O CLI `musa-build upload` cobre o que a API ainda não cobre
   (upload de assets).
3. **O MCP não é o caminho do curador** — é ferramenta da equipe (e de
   assistentes de IA) para consultar e operar o acervo. Testar por ele
   mediria a interface errada.
4. **Determinismo e velocidade**: as rotinas precisam ser reproduzíveis
   (seed fixa) e rápidas o bastante para rodar todas as noites em CI —
   scripts HTTP são ambos; automação de browser é frágil e lenta.
5. **Lacunas de API já conhecidas** (sem endpoint de upload de asset, sem
   despublicar, sem desfazer, sem proteção de edição concorrente) serão
   expostas pelas personas — o driver precisa registrar "rotina impossível
   pela API" como achado de primeira classe, não como falha de script.

## Decisão proposta

1. **Driver = scripts Python** (`beta/personas/`, `beta/misuse/`) usando
   `requests`/`httpx` contra a API HTTP do `musa-build serve`, com o token de
   tenant exatamente como o admin web faz.
2. **CLI documentado onde a API não cobre**: upload de asset usa
   `musa-build upload` (o caminho real de hoje). Toda vez que uma rotina
   precisar sair da API, o driver loga um achado de lacuna classificado.
3. **Seed determinística**: mesma seed → mesma sequência de ações; qualquer
   cenário é reproduzível localmente com um comando.
4. **Cada rotina declara suas asserções de invariante** (ADR 0016 /
   `beta/invariants.py`): ação sem asserção não conta como exercitada.
5. **Smoke de UI fica fora deste driver**: se/quando quisermos cobrir o
   admin web ponta a ponta, será uma suíte Playwright separada e pequena —
   não o driver das rotinas diárias.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Playwright contra a UI do admin** | Cobre a UI, mas é frágil (seletores, timing), lenta para nightly e testa duas coisas ao mesmo tempo (UI + API) — quando quebra, o diagnóstico é ambíguo. Pode vir depois como smoke separado |
| **MCP server como driver** | O MCP é a interface da equipe/assistentes, não do curador — medir por ele deixaria a API pública do cliente sem cobertura de ator |
| **Chamar funções internas do builder** | Viola a restrição nº 1: testaria o código, não o produto; o overlay e o gating HTTP ficariam fora do caminho exercitado |
| **Scripts de shell com curl** | Funciona, mas a orquestração de rotinas com seed, retry, captura estruturada de evidência e asserções é muito mais legível em Python — e o time já mantém tudo em Python |

## Consequências

- O nightly exercita **exatamente** o que um curador real exercita: a API
  pública. Bug encontrado = bug que um cliente encontraria.
- Lacunas de API emergem como dados estruturados ("rotina X precisou do CLI/
  foi impossível"), alimentando a lista priorizada de bugs do critério de
  saída 3.
- As personas rodam em qualquer lugar que rode Python + a imagem — máquina
  do estúdio, CI, ou a futura App Service — sem dependência de browser.
- Risco aceito: a UI do admin fica sem cobertura de ator sintético nesta
  fase; mitigado pelo smoke manual do M1.7 e pela possibilidade de uma
  suíte Playwright separada mais tarde.
