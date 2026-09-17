# MUSA app-service — Hand-off para o próximo agente

> Leia este documento inteiro antes de escrever a primeira linha de código. Ele existe para que você
> não redescubra na prática o que já foi aprendido, e para que não desfaça decisões que custaram
> sessões para serem tomadas.
>
> Última atualização: **2026-09-17**.

---

## 0. Como este projeto pensa

Cinco princípios explicam quase todas as decisões que você vai encontrar aqui. Quando estiver em
dúvida, decida por eles:

1. **Contrato primeiro.** A forma dos dados é definida antes da implementação e é verificável
   (`schemas/ficha.schema.json`). O que não valida não entra.
2. **O portão fica no build, nunca no cliente.** Filtrar no browser equivale a não filtrar: o
   payload é público. Isso vale para `draft` e para tier.
3. **Binário grande não entra no git.** Um repositório que carrega mídia para sempre é um
   repositório lento para sempre — e o git nunca esquece.
4. **Uma fonte de verdade por assunto.** O `.usd` para o asset, a `ficha.json` para o curadorial, o
   repo do cliente para o conteúdo, o servidor para o tier. Duas cópias divergem.
5. **Verifique, não presuma.** Neste projeto já houve um "teste verde" que não testava nada e um
   índice que dizia estar atualizado sem estar. Prefira medir a afirmar.

---

## 1. O MUSA em um parágrafo

**MUSA (Museu Digital 3D)** é um serviço para museus, galerias, salas de cinema de arte e livrarias
com acervo: digitaliza, cataloga, preserva e exibe coleções online, em **tiers** (Bronze: catálogo
2D · Silver: peças em 3D · Gold: digital twins), com um **assistente de IA** que responde sobre o
acervo no site e em quiosques físicos. O valor comercial central é uma **pipeline de catalogação
automatizada**: fotos das fichas físicas entram, fichas estruturadas e validadas saem — "dias de
trabalho viram horas".

O detalhe técnico que diferencia o produto é tratar o **OpenUSD** como formato-fonte do asset 3D
(mesmo que o MVP entregue apenas GLB), com metadados curadoriais como atributos personalizados no
default prim.

---

## 2. Onde vive o quê

| Repositório | Papel | Estado |
|---|---|---|
| **`Agua-Games/Musa_app-service`** | a **plataforma**: documentos, contrato, frontend, ferramentas | privado, `main`, 6 commits |
| **`Agua-Games/DemoMuseum`** | **repositório cliente** — e o cliente virtual dos testes | privado, esqueleto (`a1f1204`) |
| `Agua-Games/musa-museum-template` | template do qual repos de clientes nascem | **não existe ainda** (M0) |

Local (este computador): plataforma em `H:\Musa_app-service\alpha`, DemoMuseum em
`H:\Musa_app-service\DemoMuseum` (irmão, **fora** da árvore da plataforma — não aninhe repos).

### Mapa do repositório da plataforma

```
docs/
├── Musa_design document_v1.0.md              # doc público: tiers, preços, proposta
├── Musa_design document_technical-specs_v1.1.md  # especificação §1–§8
├── Musa_design implementacao-usd.md          # asset USD, scripts, viewer, RAG
├── Musa_design onboarding.md                 # processo de onboarding de cliente
├── HANDOFF.md                                # este documento
└── adr/
    ├── 0001-camada-de-acervo.md              # contrato, backend-agnóstico, sem WordPress
    ├── 0002-tooling-de-desenvolvimento.md     # MCP, índice de codebase, limites
    └── 0003-onboarding-de-clientes.md         # artefato versionado, tenancy, gating
schemas/ficha.schema.json                     # O CONTRATO
source/                                       # frontend estático (o site)
tools/
├── fetch_assets.py                           # baixa 14 imagens do Wikimedia
├── fetch_models.py                           # baixa 3 modelos Khronos (o 4º é manual)
└── validate_catalog.py                       # valida o catálogo contra o contrato
```

---

## 3. Estado atual — verificado, com evidência

**O que existe e funciona:**

| Item | Evidência |
|---|---|
| Frontend estático completo (hero, galerias, viewer 3D, digital twin, triagem, loja, planos, admin) | `source/`, servido por `npm run dev` (porta 7100) |
| Camada de dados contract-first com modos `mock` e `live` | `source/assets/js/api.js` |
| Contrato que o catálogo **realmente** satisfaz | `python tools/validate_catalog.py` → **14 itens, 0 violações** |
| Fetchers de assets reproduzíveis | 3 modelos Khronos com tamanho exato verificado; 14 imagens Wikimedia |
| Decisões registradas | 3 ADRs |
| Repositório cliente | `DemoMuseum`, esqueleto commitado e publicado |

**O que NÃO existe ainda** (e por isso o M0 é onde o trabalho começa):

- ❌ **Nenhum CI** no repo da plataforma (zero workflows) e **nenhum teste automatizado** (zero
  arquivos de teste).
- ❌ **Nenhum artefato publicável**: não há `@musa/app`, nem imagem de container, nem builder. O
  `source/` é uma pasta, não um produto consumível por um repo de cliente.
- ❌ **Nenhum backend**: o frontend roda 100% sobre um mock em memória (`window.MUSA_MOCK`). Não há
  API, banco, autenticação real nem upload.
- ❌ **Nenhum logger, nenhuma observabilidade.**
- ❌ **Gating só cosmético**: o filtro de `website_status` e de tier acontece no browser.
- ❌ **Nenhum entitlements**: tier é um campo do mock.

### O defeito conhecido que precisa ser corrigido (e como confirmar)

`source/data/catalog.json` contém **1 item com `website_status = "draft"`**, e o filtro é client-side
(`main.js`). Numa build estática o item **vai no payload** — abra o devtools e ele está lá.

```powershell
$c = Get-Content source\data\catalog.json -Raw | ConvertFrom-Json
$c.items | Group-Object website_status | Select-Object Name, Count
# draft 1 | published 13
```

Pelo mesmo motivo, um cliente Bronze receberia os dados do Gold se o catálogo os contivesse. O
conserto é o item 3 do M0.

---

## 4. Decisões tomadas — não rediscutir

| ADR | Decisão | Se você discordar |
|---|---|---|
| **0001** | Camada de acervo **contract-first e backend-agnóstica**. **Sem WordPress.** MVP = índice em build-time; escala = **Payload** (TS/Postgres); modo padrões = Omeka S / CollectiveAccess. Directus foi rejeitado por licença (MSCL, limite de receita). | traga números, não gosto; um 4º ADR substitui |
| **0002** | Índice de codebase via MCP como fonte primária de exploração, tratado como **dado derivado**. | — |
| **0003** | MUSA é **artefato versionado e fixado**; o repo do cliente tem só conteúdo + config + CI; **runtime nunca escreve em git**; **entitlements vêm do servidor**; gating no build; **multi-deploy antes de multi-tenant**. | idem |

**Descartado de propósito:** Tainacan/WordPress (bloat e acoplamento), `ficha.toml` (substituído pelo
USD como fonte + `ficha.json` derivada), Qdrant como backend do acervo (pgvector junto ao Postgres),
`.exe` + DLLs copiados para repos de clientes, admin versionando conteúdo em git, `config.json` do
cliente definindo o próprio tier.

---

## 5. Invariantes (violar isto é regressão)

1. **Ficha fora do contrato falha o build.** Sem exceção, sem aviso.
2. **Nada `draft` e nada de tier acima do contratado chega ao payload.**
3. **Zero binário grande versionado** (`*.glb`, `*.usd`, `*.jpg` de alta). Vai para o bucket, com
   URL na ficha.
4. **Zero código do MUSA dentro de um repo de cliente.**
5. **Entitlements nunca são editáveis pelo cliente.**
6. **`docs/* session.md` não se reescreve.** Transcrições são registro datado; decisão nova vira ADR.
   (Os dois logs originais foram consolidados e removidos — recuperáveis em `git show 2dbcb4f`.)
7. **Nada de fornecedor amarrado ao contrato:** os campos de asset são agnósticos de formato
   (`model_primary`, `model_source`, `model_formats`, `model_viewer`, `model_status`).

---

## 6. Convenções

- **Documentos em português. Código, comentários, mensagens de log/erro, nomes de teste e mensagens
  de commit em inglês.** Artefato com os dois idiomas misturados é defeito, não preferência.
- **Decisão relevante vira arquivo em `docs/adr/`** — em arquivo, não espelhado no store do MCP (uma
  cópia só; duas divergem).
- **Versões de documento sobem em arquivo** (`v1.0` → `v1.1`), preservando o anterior.
- **Commit em inglês, imperativo, escopo entre parênteses:** `feat(frontend): …`, `docs: …`,
  `chore: …`.
- **Definition of done de qualquer tarefa:** contrato valida · nenhum binário novo no git ·
  documentação atualizada · ADR se houve decisão · verificação executada e colada no relatório.

---

## 7. Armadilhas conhecidas (todas custaram tempo real)

| Armadilha | Sintoma | O que fazer |
|---|---|---|
| **`index_repository` é no-op em projeto já indexado** | contagens de nós idênticas, arquivos novos invisíveis | `delete_project` + `index_repository`; e confirme com `search_graph` por um título que você sabe ser novo |
| **PowerShell come a crase** | `$_ -like '```*'` retornou **0 fences para todo arquivo** — um falso verde | monte o padrão com `[char]96` |
| **O terminal derruba aspas duplas** | `"-tc=*x*"` chega desquebrado e o filtro vira dois tokens | use aspas simples; confira o eco |
| **PowerShell + construtor multi-linha** | o prompt de continuação engole o resultado | comandos de uma linha só |
| **`gh` não resolve no terminal do VS Code** | `gh: not recognized` | caminho completo: `& "$env:LOCALAPPDATA\Programs\GitHubCLI\bin\gh.exe"` |
| **Build que falha não interrompe um teste encadeado** | `build; test` imprime verde rodando o binário *anterior* | nunca encadeie; leia a saída do build |
| **Apagar o fim de um arquivo não tem ferramenta de edição** | — | trunque com `[System.IO.File]::WriteAllText` (UTF-8 sem BOM) e **prove** com `git diff --numstat` (`0 <N>` = só deleção) |
| **Blob continua vivo depois de reescrever a história** | `.git` não encolhe | `reflog expire --all` + `gc --prune=now` **depois** do force-push |
| **Ícones/itens de teste que "passam"** | um teste que não testa nada é pior que um teste que falha | assertar um valor que você já viu |

---

## 8. Primeiros 30 minutos — estabeleça a verdade

```powershell
# 1. O grafo da codebase (é a fonte primária de exploração neste projeto)
#    mcp: list_projects → get_architecture({ project: "H-Musa_app-service-alpha" })

# 2. O contrato está satisfeito?
python tools\validate_catalog.py

# 3. Os assets são reproduzíveis?
python tools\fetch_models.py     # 3 modelos ok; venus-de-milo é MANUAL (sai com código 1)

# 4. Estado do git
git -C H:\Musa_app-service\alpha log --oneline
git -C H:\Musa_app-service\DemoMuseum log --oneline

# 5. Leia nesta ordem
#    docs/adr/0001 → docs/adr/0003 → docs/Musa_design onboarding.md → source/README.md
```

> Se o grafo não contiver um arquivo que você sabe existir, **o índice está velho** — e um índice
> velho responde com confiança. Force a reindexação antes de concluir qualquer coisa.

---

## 9. Roadmap e milestones

Cada milestone tem **critério de saída testável**: uma verificação que pode falhar. Não avance com
critério não atingido — o projeto não tem folga para dívida escondida.

| # | Milestone | Pergunta que ele responde | Bloqueia |
|---|---|---|---|
| **M0** | Fundação | o MUSA é um produto consumível? | tudo |
| **M1** | MVP funcional | o sistema faz o que promete, para um museu? | M3 |
| **M2** | Pipeline de catalogação | a promessa comercial ("dias → horas") se sustenta? | M4 |
| **M3** | Beta / cliente virtual | aguenta uso real e abuso? | M4 |
| **M4** | Produção / apresentável | vende, entrega e não quebra? | primeiro contrato |
| **M5** | Horizonte (escala) | o custo de operação escala? | — |

### M0 — Fundação ✅ *comece aqui*

**Objetivo:** transformar a pasta `source/` em um artefato que um repositório de cliente possa
consumir. Hoje a arquitetura está desenhada e não é executável.

**Entregáveis**
1. Contrato congelado como **v1** (versão no `$id` do schema, e uma nota de compatibilidade).
2. **Extrair `musa-museum-template`** de `source/` — hoje o demo e o template são a mesma coisa.
3. **Builder** que consome `content/` + `museum.config.json` e emite site estático.
4. **Publicar o artefato** (`@musa/app@<versão>` em GitHub Packages, ou imagem de container).
5. **Mover `tools/validate_catalog.py` para dentro do artefato** — o portão tem de viajar com o
   produto, senão cada cliente tem a sua versão do portão.
6. **Gating no build**: filtrar `website_status` e tier, e emitir um **build report** dizendo o que
   entrou, o que saiu e **por quê**.
7. **CI**: workflow na plataforma (lint, validação, testes) e no cliente (build real, substituindo o
   placeholder `deploy.yml`).

**Critérios de saída (os três primeiros são falsificáveis)**
- [ ] `gh workflow run` no DemoMuseum produz um **site acessível**.
- [ ] Inserir um item com `website_status: "draft"` **não** o faz aparecer no payload publicado.
- [ ] Corromper uma ficha de propósito **faz o build falhar** (e o site anterior continua no ar).
- [ ] Repo de cliente com **zero** código do MUSA e com apenas conteúdo/config/CI.

**Não faça em M0:** autenticação, banco, multi-tenant, OCR.

---

### M1 — MVP funcional

**Objetivo:** um museu real consegue operar o sistema sozinho para o caso básico.

**Entregáveis**
1. **API de acervo** com o contrato de `/collections`, `/items/{id}`, `/search`, `/schema` (§6.1 da
   spec). MVP pode ser estático; o caminho para Payload deve estar aberto.
2. **Entitlements reais**: endpoint + token de deploy; modo offline com **assinatura** verificada por
   chave pública embarcada.
3. **Object storage**: upload e resolução de assets por URL (`model_primary`).
4. **Admin mínimo**: criar coleção, subir item, publicar/despublicar, promover hero.
5. **Logger estruturado**: JSON com correlation ids de tenant → build → asset. Sem isso, depurar
   produção é arqueologia.
6. **Depurador de conteúdo**: além do log, o **build report** legível responde "por que esta peça não
   apareceu no site?" — e a resposta deve ser uma linha, não uma investigação.
7. **Servidor MCP do MUSA** — ver abaixo.
8. **DemoMuseum com conteúdo real** (o acervo demo do `source/data/catalog.json` migrado para
   `content/`, no formato do contrato).

**Servidor MCP do MUSA — por que já no MVP**
Ele serve três coisas ao mesmo tempo, o que é raro:
- **ergonomia de desenvolvimento**: operar e testar o acervo sem construir UI antes da hora;
- **superfície de produto**: é a base do assistente (o "cérebro" que responde sobre o acervo);
- **canal de operação**: a equipe MUSA resolve pedidos de cliente sem abrir o painel.

Ferramentas mínimas: `list_collections` · `get_item` · `search` · `validate_ficha` ·
`propose_ficha_correction` · `upload_asset` · `set_status` · `build_report`. Toda resposta que
afirme algo sobre o acervo **deve citar as fontes** (a regra que já está em
`docs/Musa_design implementacao-usd.md` §7).

**Critérios de saída**
- [ ] Um curador não-técnico cria uma coleção e publica um item **sem ajuda**, em **< 15 min**.
- [ ] O build report explica a inclusão/exclusão de 100% dos itens.
- [ ] `search` responde com fontes rastreáveis a `asset_id`.
- [ ] Um upgrade de versão do MUSA no cliente é: 1 linha + push, verde no CI.

---

### M2 — Pipeline de catalogação (a promessa comercial)

**Objetivo:** provar que a promessa central do produto é verdadeira, com números.

**Entregáveis**
1. **OCR em lote headless** sobre fotos de fichas (§2.3.2 da spec).
2. **Agente de correção/estruturação** → `ficha.json`.
3. **Relatório de confiança por campo**: separar o que foi **lido** do que foi **inferido**. É o que
   permite revisão humana dirigida em vez de revisão total.
4. **Fila de revisão** só para campos de baixa confiança.
5. **Embeddings + índice vetorial** (pgvector) para busca semântica.
6. **Importação de um acervo de teste** de 500–5.000 fichas.

**Critérios de saída**
- [ ] 500 fotos entram; 500 fichas válidas saem; **X% dos campos passam sem revisão humana**
      (meça e publique X — ele define o preço do serviço).
- [ ] Custo por ficha em R$ medido (OCR + LLM + armazenamento).
- [ ] Nenhuma ficha entra no índice sem validação.

**Trilha paralela:** se houver uma segunda pessoa, o M2 é independente do M1 (é Python, offline) e
pode correr em paralelo.

---

### M3 — Beta / cliente virtual

**Objetivo:** encontrar o que ninguém pensou, antes do cliente pagante.

**O cliente virtual (no `DemoMuseum`) não é um teste de fumaça — é um ator.**

1. **Personas sintéticas** — `owner@demo` e `team@demo` com rotinas:
   - *diária*: publicar 2 itens, corrigir uma ficha, subir uma imagem;
   - *semanal*: criar coleção, reorganizar subcoleção, promover hero;
   - *pontual*: despublicar, desfazer, pedir um módulo novo.
2. **Gerador de uso indevido** — arquivo grande demais, MIME errado, campo obrigatório ausente,
   `asset_id` duplicado, data inválida, `.glb` corrompido, upload interrompido, edições concorrentes,
   token expirado, **downgrade de tier no meio do caminho**.
3. **Asserções de invariante após cada ação** — nada `draft` no payload, nada de tier superior,
   contrato válido, build verde.
4. **Telemetria por cenário** → relatório por execução; **nightly no CI**, falha abre issue.
5. **Carga**: N museus × M itens; medir tempo de build e custo.
6. **SLOs com números reais** — a tabela §8.1 da spec tem alvos *propostos*; substitua-os por
   medições.
7. **Beta fechado** com um museu real (amigo, parceiro, pequeno acervo).

**Critérios de saída**
- [ ] 14 dias de nightly **sem regressão**.
- [ ] 100% dos cenários de uso indevido cobertos, e nenhum causa perda de dados.
- [ ] Lista de bugs conhecidos priorizada e publicada.
- [ ] Um museu real operou por 2 semanas sem intervenção da equipe.

---

### M4 — Produção / apresentável para clientes e investidores

**Objetivo:** vender, entregar e não quebrar.

**Segurança e conformidade**
- [ ] Gating **auditável**: um Bronze comprovadamente não recebe dados do Gold (teste, não promessa).
- [ ] Tokens por tenant, rate limits, assinatura de entitlements.
- [ ] **LGPD**: dados de visitante, áudio de quiosque, retenção e exclusão.

**Operação**
- [ ] **Backup local** (o artefato on-premise: nó na máquina do museu) + **restore ensaiado e
      cronometrado** (DR drill, não plano no papel).
- [ ] Runbook: onboarding, incidentes, rollback de versão.
- [ ] Monitoramento e alertas dos SLOs do M3.

**Produto e apresentação**
- [ ] Acessibilidade (WCAG no mínimo AA) e multi-idioma.
- [ ] Créditos e licenças de todo asset público exibidos corretamente.
- [ ] **Ambiente de demonstração** com 3 museus fictícios, cada um em um tier, e uma narrativa de
      upgrade — é isso que se mostra a um investidor ou a um cliente.
- [ ] Custo por cliente/mês conhecido, dentro da margem de cada tier.

**Comercial e jurídico**
- [ ] **Documento de IP**: o que é da plataforma, o que é do cliente, o que é de quem contribuiu. O
      material deste repositório é sensível (preços, estratégia, conversas) — mantenha tudo privado.
- [ ] Contrato de serviço (SLA, propriedade do acervo, portabilidade e saída).
- [ ] Termos de uso e política de privacidade publicados.

**Critérios de saída**
- [ ] Onboarding de um cliente real **ponta a ponta sem a equipe no loop** (exceto escaneamento 3D).
- [ ] Restore ensaiado com tempo medido.
- [ ] Auditoria de tier passa.
- [ ] Demonstração de 10 minutos, sem improviso.

---

### M5 — Horizonte (não é compromisso)

Migração para **multi-tenant** quando o custo de operação doer (referência: ~10 clientes);
onboarding self-service; marketplace de módulos; suporte N1 com runbook.

---

### Trilhas paralelas (não bloqueiam o caminho crítico)

| Trilha | Conteúdo | Quando |
|---|---|---|
| **3D / USD** | spike de USD no browser (medir carga e memória em desktop e mobile — **as bibliotecas citadas nas sessões nunca foram testadas neste repo**), variantes e "exploded view", digital twin em tempo real (backend de simulação + WebSocket) | depois do M1; é o diferencial de Silver/Gold |
| **Assistente / RAG** | STT/TTS para quiosque, qualidade de recuperação, custo por consulta, revisão de respostas em acervo novo | paralelo ao M2 |
| **Comercial / jurídico** | IP, contrato, LGPD, licenciamento de assets, precificação validada com cliente real | antes do M4 |

---

## 10. Riscos e incertezas (o que ainda **não** sabemos)

1. **USD no navegador.** As bibliotecas citadas nas sessões de design vêm de conversa, não de
   medição. Antes de prometer 3D avançado, faça o spike e meça.
2. **Qualidade do OCR em fichas manuscritas.** O produto assume que dá para automatizar; ninguém
   mediu X% ainda. É o risco número um da promessa comercial.
3. **Custo de LLM por tier.** O RAG barato é premissa, não fato. Meça por consulta antes de fixar
   preço.
4. **Autoridade dos metadados.** Quem confirma `autor`/`data`/`material` quando a IA erra? Sem isso o
   museu não assina a responsabilidade pelo dado.
5. **Pesos dos formatos.** As estimativas de tamanho de USD vs GLB são de relato de mercado, não de
   medição própria — e elas sustentam o preço de hospedagem.
6. **`venus-de-milo.glb` sem URL de origem.** O modelo existe apenas nesta máquina. Se o disco morrer,
   ele morre. Registre a URL do Sketchfab.
7. **Concentração de conhecimento.** Um único desenvolvedor no frontend. Documente enquanto decide.

---

## 11. Pendências herdadas

- [ ] `README.md` da raiz da plataforma está **vazio** — escrever a porta de entrada do repositório.
- [ ] Corrigir o gating (o `draft` que chega ao payload) — item do M0.
- [ ] Extrair o `musa-museum-template` do `source/`.
- [ ] Mover `tools/validate_catalog.py` para dentro do artefato publicado.
- [ ] Registrar a URL de origem do `venus-de-milo.glb` em `tools/fetch_models.py`.
- [ ] §8.1 da spec (métricas) tem valores **propostos**, não medidos — substituir por medição no M3.
- [ ] `source/README.md` descreve o estado do frontend, mas o README do DemoMuseum precisa ganhar o
      passo a passo real quando a pipeline estiver ligada.

---

## 12. Regra de ouro

Se você só puder guardar uma coisa deste documento:

> **O portão fica no build, o contrato é a verdade, e binário não entra no git.**
