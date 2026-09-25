# MUSA app-service — Hand-off para o próximo agente

> Leia este documento inteiro antes de escrever a primeira linha de código. Ele existe para que você
> não redescubra na prática o que já foi aprendido, e para que não desfaça decisões que custaram
> sessões para serem tomadas.
>
> Última atualização: **2026-09-23**.

---

## 0. Como este projeto pensa

Cinco princípios explicam quase todas as decisões que você vai encontrar aqui. Quando estiver em
dúvida, decida por eles:

1. **Contrato primeiro.** A forma dos dados é definida antes da implementação e é verificável
   (`schemas/card.schema.json`). O que não valida não entra.
2. **O portão fica no build, nunca no cliente.** Filtrar no browser equivale a não filtrar: o
   payload é público. Isso vale para `draft` e para tier.
3. **Binário grande não entra no git.** Um repositório que carrega mídia para sempre é um
   repositório lento para sempre — e o git nunca esquece.
4. **Uma fonte de verdade por assunto.** O `.usd` para o asset, a `card.json` para o curadorial, o
   repo do cliente para o conteúdo, o servidor para o tier. Duas cópias divergem.
5. **Verifique, não presuma.** Neste projeto já houve um "teste verde" que não testava nada e um
   índice que dizia estar atualizado sem estar. Prefira medir a afirmar.

---

## 1. O MUSA em um parágrafo

**MUSA (Museu Digital 3D)** é um serviço para museus, galerias, salas de cinema de arte e livrarias
com acervo: digitaliza, cataloga, preserva e exibe coleções online, em **tiers** (Bronze: catálogo
2D · Silver: peças em 3D · Gold: digital twins), com um **assistente de IA** que responde sobre o
acervo no site e em quiosques físicos. O valor comercial central é uma **pipeline de catalogação
automatizada**: fotos dos cards físicas entram, cards estruturadas e validadas saem — "dias de
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
| `Agua-Games/musa-museum-template` | template do qual repos de clientes nascem | esqueleto versionado em `templates/museum-template/` (M0.2); **repo remoto pendente** |

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
    ├── 0003-onboarding-de-clientes.md         # artefato versionado, tenancy, gating
    ├── 0004-frontend-auto-hospedado.md         # three.js vendorizado, mídia licenciada
    └── 0005-publicacao-do-frontend.md          # GitHub Pages + assets materializados no CI
schemas/card.schema.json                     # O CONTRATO
source/                                       # frontend estático (o site)
tools/
├── fetch_assets.py                           # baixa 14 imagens do Wikimedia
├── fetch_models.py                           # baixa 3 modelos Khronos (o 4º é manual)
├── fetch_vendor.py                           # vendoriza three.js (sem CDN em runtime)
├── check_frontend.py                         # porta do build: import map válido e vendor presente
└── validate_catalog.py                       # valida o catálogo contra o contrato
.github/workflows/pages.yml                   # publica source/ no GitHub Pages (ADR 0005)
reasonix.toml                                 # preferências do agente neste workspace
```

---

## 3. Estado atual — verificado, com evidência

**O que existe e funciona:**

| Item | Evidência |
|---|---|
| Frontend estático completo (hero, galerias, viewer 3D, digital twin, triagem, loja, planos, admin) | `source/`, servido por `npm run dev` (porta 7100) |
| Camada de dados contract-first com modos `mock` e `live` | `source/assets/js/api.js` |
| Contrato que o catálogo **realmente** satisfaz | `python tools/validate_catalog.py` → **14 itens, 0 violações** |
| **Contrato congelado como v1** (M0.1) | `$id` versionado + `x-contract-version: 1.0.0` + `schemas/COMPATIBILITY.md` |
| **Builder `musa-app`** (M0.3/0.5/0.6): validação, gating de status/tier, build report | `builder/`; 26 testes (`python -m unittest discover -s tests` em `builder/`) → **OK** |
| **Frontend genérico (template separável do demo)** (M0.2) | chrome data-driven via `data-skin` + `museum.skin`/`salon`/`heroVideo` no catálogo; verificado em Chrome headless em 2026-09-23 |
| **Template de cliente** | `templates/museum-template/` — constrói verde com o próprio builder |
| **Dockerfile do artefato + workflows de CI/release** (M0.4/0.7) | `Dockerfile`, `.github/workflows/ci.yml` + `release.yml`, `templates/client-deploy.yml` — **ainda não exercitados na nuvem** |
| Fetchers de assets reproduzíveis | 3 modelos Khronos com tamanho exato verificado; 14 imagens Wikimedia; three.js r160 vendorizado (`tools/fetch_vendor.py`) |
| Decisões registradas | 7 ADRs |
| Repositório cliente | `DemoMuseum`, esqueleto commitado e publicado |

**O que NÃO existe ainda** (o M1 começa aqui):

- ⚠️ **Backend parcial (M1.4 fase 1)**: o builder ganhou `musa-build serve` (FastAPI,
  mesma imagem) — API de leitura dinâmica com os mesmos shapes/gating da API estática
  (`/collections`, `/items/{id}`, `/search`, `/schema`, assets gated). **Ainda não há
  escritas nem banco** (fase 2: token por tenant + SQLite); sem elas, o frontend de
  cliente segue no modo estático e o admin segue mockado.
- ✅ **Logger estruturado (M1.5)**: todo build emite `build-log.jsonl` com correlação tenant → build → asset; o report diz onde cada registro pousou. A API dinâmica (M1.4) reutiliza o mesmo logger.
- ⚠️ **Gating correto só nos builds do builder**: o demo da plataforma (Pages) ainda
  carrega o item `draft` no payload de propósito — ele é o material da demo do admin.
  Nos sites de cliente, o gating é no build e auditável (M0.6).
- ✅ **Entitlements reais (M1.2)**: o tier vem do bloco `entitlements` do
  `museum.config.json`, **assinado pela plataforma** (Ed25519, docs/entitlements.md) —
  builds de release falham sem assinatura válida; o pin de dev mantém o warning.

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

### Frontend: hospedagem e a armadilha do `file://` (2026-09-18)

O frontend **precisa ser testado por `http(s)`**. Abrir `source/index.html` direto do disco
(`file://`) produz sintomas que parecem bug de código e não são:

- o viewer 3D mostra *"WebGL viewer could not load (Three.js bundle unreachable)"* — o navegador
  recusa **módulos ES** de uma origem opaca, então `three-item.js` nunca executa nem define
  `window.MusaItemViewer`;
- o embed do YouTube não carrega (mesma origem opaca);
- o GLB em si também não seria buscado, pelo mesmo motivo.

Nada disso tem a ver com a GPU/WebGL: é política de origem para *módulos e `fetch`*, não acesso à
placa de vídeo. `main.js` agora detecta `location.protocol === "file:"` e explica isso na tela.

Para rodar local: `npm run dev` **dentro de `source/`** (a `package.json` mora ali) e abrir
`http://localhost:7100/`. Para testar online, o ADR 0005 publica `source/` no GitHub Pages.

Estado desta sessão (mudanças **ainda não commitadas** quando isto foi escrito):

| Item | Estado |
|---|---|
| Vídeo do hero | montagem do **YouTube** (vídeo `siuAaTMil6g`, carregado de `https://www.youtube.com/iframe_api`) montada em `#heroVideo` por `heroFilm()` (`main.js`); o `<video>` local, o fallback em cascata e o corte por `prefers-reduced-motion` foram **removidos**. A foto `hero-museum-hall.jpg` está **fora de `.hero-bg` de propósito** (linha comentada em `index.html` para restaurar) |
| Backdrops das seções | `<img class="sec-bg">` como primeiro filho de cada `.sec-media` (6 seções); `--sec-bg` e `.sec-media::before` foram **abandonados** — ver §7 |
| Legenda do carrossel | colada na imagem, largura 100% da imagem, sem folga |
| Viewer 3D | passa a mostrar o erro real em vez de "unreachable" |
| Hospedagem | `.github/workflows/pages.yml` publica `source/` — ADR 0005. Pages **habilitado** em 2026-09-18 (`build_type: workflow`) |
| Modelos 3D | os 4 GLB (~29,6 MB) passaram a ser **versionados**: a regra `*.glb` saiu do `.gitignore` — desvio consciente do invariante §5.3, ver §11 |
| Binários | `.gitattributes` fixa `*.glb`/`*.mp4`/imagens como `binary`: `* text=auto` decide por *sniffing* dos primeiros 8000 bytes e um GLB pequeno pode passar por texto (ver §7) |
| Ferramentas do agente | `reasonix.toml` deixa `[tools.shell]` **comentado**, para a preferência vir do config do usuário (`prefer = "pwsh"` nesta máquina); `AGENTS.md` ganhou a regra de **não** criar artefatos que o próprio shell do agente não consegue apagar |
| Hero film | classe **`.hero-film`** separada de `.sec-bg`, para o header ter opacidade própria: `--hero-film-opacity` (padrão **1**) e `--hero-film-brightness` (0.6), no topo do bloco em `style.css` |
| Viewers 3D | **corrigidos em 2026-09-18**: o import map usava *bare specifier*, o que anulava a própria chave `three` — os dois viewers nunca funcionaram em ambiente nenhum. Ver §7 |
| Portão do frontend | `tools/check_frontend.py` roda no `pages.yml` **antes** do upload: reprova import map não-URL e vendor ausente |

---

## 4. Decisões tomadas — não rediscutir

| ADR | Decisão | Se você discordar |
|---|---|---|
| **0001** | Camada de acervo **contract-first e backend-agnóstica**. **Sem WordPress.** MVP = índice em build-time; escala = **Payload** (TS/Postgres); modo padrões = Omeka S / CollectiveAccess. Directus foi rejeitado por licença (MSCL, limite de receita). | traga números, não gosto; um 4º ADR substitui |
| **0002** | Índice de codebase via MCP como fonte primária de exploração, tratado como **dado derivado**. | — |
| **0003** | MUSA é **artefato versionado e fixado**; o repo do cliente tem só conteúdo + config + CI; **runtime nunca escreve em git**; **entitlements vêm do servidor**; gating no build; **multi-deploy antes de multi-tenant**. | idem |
| **0004** | Frontend **auto-hospedado**: three.js vendorizado (sem CDN em runtime) e mídia licenciada. | — |
| **0005** | Demonstração publicada no **GitHub Pages via GitHub Actions** (a Pages recusa um subdiretório como raiz). Os binários seguem fora do git e são **materializados no build** pelos próprios fetchers. | traga números; um 6º ADR substitui |

**Descartado de propósito:** Tainacan/WordPress (bloat e acoplamento), `card.toml` (substituído pelo
USD como fonte + `card.json` derivada), Qdrant como backend do acervo (pgvector junto ao Postgres),
**.exe` + DLLs copiados para repos de clientes, admin versionando conteúdo em git, `config.json` do
cliente definindo o próprio tier.

> ✅ **Divergência do ADR 0004 resolvida (2026-09-23):** o vídeo do hero fica no YouTube —
> decisão do dono registrada na **ADR 0007** (exceção única e explícita; o resto da ADR 0004
> segue valendo). O ID do vídeo é do cliente (`site.heroVideo`), e a foto de base pode voltar
> por `site.skin.hero` sem editar o template.

---

## 5. Invariantes (violar isto é regressão)

1. **Card fora do contrato falha o build.** Sem exceção, sem aviso.
2. **Nada `draft` e nada de tier acima do contratado chega ao payload.**
3. **Zero binário grande versionado** (`*.glb`, `*.usd`, `*.jpg` de alta). Vai para o bucket, com
   URL no card. ⚠️ **Violado de propósito em 2026-09-18**: os quatro GLB (~29,6 MB) e ~50 MB de JPEG
   do demo entraram no git para o Pages funcionar sem object store. É decisão temporária — ver §11.
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
| **Import map com valor que não é URL** | os **dois viewers WebGL ficam mortos** e a página parece perfeita: `resolve`/`GLTFLoader` falham, o console diz `Resolution of specifier "three" was blocked by a null entry.` e `main.js` mostra "Three.js bundle unreachable" | o valor tem de começar com `/`, `./`, `../` ou ser URL absoluta. `"three": "assets/vendor/…"` é **bare specifier**: o parser guarda `null` na chave e a resolução **morre sem fallback**. Use `"./assets/vendor/…"`. `python tools/check_frontend.py` reprova isso no build |
| **Testar o frontend por `file://`** | viewer 3D não carrega; YouTube não carrega; um estilo que parece "não ter pegado" | sirva por http (`npm run dev` em `source/`) e faça *hard refresh* (Ctrl+Shift+R) antes de concluir que CSS/JS não mudaram. **Atenção:** a mensagem "Three.js bundle unreachable" é genérica e, em 2026-09-18, a causa real não era o `file://` — era o import map acima |
| **Shell do agente morre com `Win32 error 5`** | `bash: couldn't create signal pipe`, em toda chamada de shell (git, node, python) | é o *restricted token* do preset `workspace-write`; descomente a linha `prefer` no `reasonix.toml` (ou ponha `prefer = "pwsh"`), que resolve; alternativamente, sessão com preset `danger-full-access` |
| **GitHub Pages recusa `source/` como raiz** | em Settings → Pages só existem `/ (root)` e `/docs` | não é limitação do repo: publique via GitHub Actions (ADR 0005) |
| **`url()` relativo dentro de custom property resolve contra o CSS, não o documento** | o backdrop de todas as seções some **sem erro visível**; o `background-image` computado vira `/assets/css/assets/img/…` e dá **404** | ponha a mídia em `<img src>` no HTML (resolve contra o documento) ou declare o `--var` **dentro do `style.css`**, com caminho relativo ao próprio CSS. Confira o valor computado antes de mexer em qualquer outra coisa |
| **Espaço no nome do arquivo (e `%20`) é inocente** | suspeita-se de `demo_room (11).jpg` e o "conserto" vira renomear 55 arquivos à toa | meça antes: os 8 assets referenciados respondem **200** com `%20` (e as `<img>` do site sempre funcionaram). O defeito estava no item acima |
| **`prefers-reduced-motion` desligado nesta máquina (`MinAnimate=0`)** | o Chromium reporta `reduce`; código que remove/esconde o vídeo do hero faz o elemento **sumir do DOM** — no DevTools `.hero-bg` só tem o `<img>` | meça `matchMedia("(prefers-reduced-motion: reduce)").matches` antes de concluir "não carregou"; nunca apague o elemento por causa disso |
| **MP4 com faixa de vídeo HEVC/H.265** | o `<video>` "toca" (`readyState: 4`, `currentTime` avança) e **não pinta nada** — tela preta silenciosa, sem erro no console | confira o codec **antes** de depurar CSS/JS: `hvc1` presente e `avc1` ausente = Chrome/Edge não decodificam. Sintoma objetivo: `videoWidth === 0`. Transcode para H.264/AVC ou VP9 |
| **`--user-data-dir` do Chrome dentro do repo** | o Chrome *headless* de verificação deixa um perfil de ~1.400 arquivos que o **shell do agente não consegue apagar** (leitura, `Move-Item`, `Remove-Item`, `[IO.Directory]::Delete`, `rd` e `icacls` todos negados) | aponte `--user-data-dir` para `%TEMP%` — verificado: o Chrome escreve lá e o shell apaga limpo. E note: **não era ACL** (a `icacls` provou ACL idêntica à de `source/index.html`, que o shell apagava), é política do sandbox sobre o que um filho criou. Ver `AGENTS.md` |

---

## 8. Primeiros 30 minutos — estabeleça a verdade

```powershell
# 1. O grafo da codebase (é a fonte primária de exploração neste projeto)
#    mcp: list_projects → get_architecture({ project: "H-Musa_app-service-alpha" })

# 2. O contrato está satisfeito?
python tools\validate_catalog.py

# 2b. Rodar o site: `npm run dev` roda DENTRO de source/ (a package.json mora ali).
#     Sem http(s) não há 3D nem YouTube (ver §7, armadilha do file://).

# 3. Os assets são reproduzíveis?
python tools\fetch_models.py     # com os 4 GLB versionados: "skip ... (already present)", sai 0
                                 # (num clone sem source/assets/models/ ele baixa 3 e o venus-de-milo
                                 #  é MANUAL: sai com código 1)

# 4. Estado do git
git -C H:\Musa_app-service\alpha log --oneline
git -C H:\Musa_app-service\DemoMuseum log --oneline

# 5. Leia nesta ordem
#    docs/adr/0001 → docs/adr/0003 → docs/Musa_design onboarding.md → source/README.md

# 6. Verificar o frontend de verdade — o projeto NÃO tem teste automatizado, então
#    um navegador headless é a única forma de provar DOM/CSS no estado real.
#    Edge e Chrome estão instalados; a partir do PowerShell:
#      --headless=new --dump-dom URL                  DOM depois do JS (o #heroVideo existe?)
#      --force-prefers-reduced-motion                 reproduz ESTA máquina (ver §7)
#      --screenshot=out.png --window-size=1440,900    grava ASSÍNCRONO: espere o arquivo
#      --user-data-dir=$env:TEMP\...                  NUNCA dentro do repo (§7)
#    Estilos computados e emulação fina pedem CDP: --remote-debugging-port=9333 mais
#    o WebSocket global do Node 22 (Runtime.evaluate, Emulation.setEmulatedMedia,
#    Page.captureScreenshot). Foi assim que os defeitos de 2026-09-18 foram provados:
#    o iframe do hero, o `videoWidth: 0` do MP4 e o 404 de todos os backdrops.
```

> Se o grafo não contiver um arquivo que você sabe existir, **o índice está velho** — e um índice
> velho responde com confiança. Force a reindexação antes de concluir qualquer coisa.

---

## 9. Roadmap e milestones

Cada milestone tem **critério de saída testável**: uma verificação que pode falhar. Não avance com
critério não atingido — o projeto não tem folga para dívida escondida.

| # | Milestone | Pergunta que ele responde | Bloqueia |
|---|---|---|---|
| **M0** ✅ | Fundação | o MUSA é um produto consumível? **Sim — provado em 2026-09-23.** | tudo |
| **M1** | MVP funcional | o sistema faz o que promete, para um museu? | M3 |
| **M2** | Pipeline de catalogação | a promessa comercial ("dias → horas") se sustenta? | M4 |
| **M3** | Beta / cliente virtual | aguenta uso real e abuso? | M4 |
| **M4** | Produção / apresentável | vende, entrega e não quebra? | primeiro contrato |
| **M5** | Horizonte (escala) | o custo de operação escala? | — |

### M0 — Fundação ✅ **CONCLUÍDO em 2026-09-23**

**Objetivo:** transformar a pasta `source/` em um artefato que um repositório de cliente possa
consumir. Hoje a arquitetura está desenhada e não é executável.

**Entregáveis** — estado em 2026-09-23:
1. ✅ Contrato congelado como **v1** (`$id` versionado, `x-contract-version`, `schemas/COMPATIBILITY.md`).
2. ✅ **Template extraído** — o chrome do site virou dados (`data-skin`, `museum.skin`, `salon`,
   `heroVideo`); esqueleto de cliente em `templates/museum-template/`. Falta só o repo remoto.
3. ✅ **Builder** (`builder/`) consome `content/` + `museum.config.json` e emite site estático.
4. ⚠️ **Artefato = imagem de contêiner no ghcr.io + GitHub Releases** (ADR 0006): `Dockerfile` e
   `release.yml` escritos; a imagem só é publicada na primeira tag.
5. ✅ **O portão viaja no artefato** — `musa_build/schemas/` embute o contrato, com teste de
   sincronia contra `schemas/`.
6. ✅ **Gating no build + build report** (`build-report.json|.md`): draft e tier acima do
   contratado ficam fora do payload, com a razão em uma linha.
7. ⚠️ **CI escrito** (`ci.yml` plataforma, `templates/client-deploy.yml` cliente) — pendente o
   primeiro run real.

**Critérios de saída — todos atingidos e verificados:**
- [x] Pipeline no DemoMuseum produz um **site acessível** — run `35936934677` verde em 2026-09-24;
      site publicado e renderizando em `https://agua-games.github.io/DemoMuseum/`
      (título e marca do cliente, 3 coleções, skin e hero film configuráveis).
- [x] Inserir um item com `website_status: "draft"` **não** o faz aparecer no payload publicado —
      verificado **no site publicado**: `estudo-em-rascunho` ausente do `catalog.js` servido.
- [x] Corromper um card de propósito **faz o build falhar** (e o site anterior continua no ar) —
      verificado localmente: exit 1, report com o erro, nenhum site emitido; o deploy só roda em build verde.
- [x] Repo de cliente com **zero** código do MUSA e com apenas conteúdo/config/CI —
      o DemoMuseum roda o build dentro da imagem `ghcr.io/agua-games/musa-app:0.1.1`.

**Não faça em M0:** autenticação, banco, multi-tenant, OCR.

---

### M1 — MVP funcional

**Objetivo:** um museu real consegue operar o sistema sozinho para o caso básico.

> **Progresso:** plano de ataque em `docs/M1_plano.md`. **M1.0 concluída** (ADRs 0008–0010
> aceitas: backend FastAPI mínimo, object storage Cloudflare R2, entitlements Ed25519
> offline). **M1.1 concluída** (2026-09-25): API de acervo estática emitida pelo builder
> (`api/*.json`, shapes em `docs/api-estatica.md`), frontend em modo live estático,
> DemoMuseum servindo o acervo via API. **M1.2 concluída** (2026-09-25): entitlements
> assinados Ed25519 — release builds exigem assinatura válida; prova falsificável no CI
> (adulterar o config quebra o build). **M1.5 concluída** (2026-09-25, builder): log
> estruturado `build-log.jsonl` com correlação tenant → build → asset em todo build, e
> report com a coluna "emitted to". Próximo: M1.3 (object storage — aguarda a conta
> Cloudflare do dono) e M1.4 (admin mínimo + backend).

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

Ferramentas mínimas: `list_collections` · `get_item` · `search` · `validate_card` ·
`propose_card_correction` · `upload_asset` · `set_status` · `build_report`. Toda resposta que
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
1. **OCR em lote headless** sobre fotos de cards (§2.3.2 da spec).
2. **Agente de correção/estruturação** → `card.json`.
3. **Relatório de confiança por campo**: separar o que foi **lido** do que foi **inferido**. É o que
   permite revisão humana dirigida em vez de revisão total.
4. **Fila de revisão** só para campos de baixa confiança.
5. **Embeddings + índice vetorial** (pgvector) para busca semântica.
6. **Importação de um acervo de teste** de 500–5.000 cards.

**Critérios de saída**
- [ ] 500 fotos entram; 500 cards válidas saem; **X% dos campos passam sem revisão humana**
      (meça e publique X — ele define o preço do serviço).
- [ ] Custo por card em R$ medido (OCR + LLM + armazenamento).
- [ ] Nenhum card entra no índice sem validação.

**Trilha paralela:** se houver uma segunda pessoa, o M2 é independente do M1 (é Python, offline) e
pode correr em paralelo.

---

### M3 — Beta / cliente virtual

**Objetivo:** encontrar o que ninguém pensou, antes do cliente pagante.

**O cliente virtual (no `DemoMuseum`) não é um teste de fumaça — é um ator.**

1. **Personas sintéticas** — `owner@demo` e `team@demo` com rotinas:
   - *diária*: publicar 2 itens, corrigir um card, subir uma imagem;
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
2. **Qualidade do OCR em cards manuscritas.** O produto assume que dá para automatizar; ninguém
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
- [x] Corrigir o gating (o `draft` que chega ao payload) — **resolvido no builder** (M0.6); o demo
      da plataforma mantém o draft de propósito (material da demo do admin).
- [x] Extrair o `musa-museum-template` do `source/` — **feito** (chrome data-driven +
      `templates/museum-template/`); falta criar o repo remoto.
- [x] Mover `tools/validate_catalog.py` para dentro do artefato publicado — **feito**:
      `musa_build/contract.py` + schema embutido com teste de sincronia.
- [ ] Registrar a URL de origem do `venus-de-milo.glb` em `tools/fetch_models.py`.
- [ ] §8.1 da spec (métricas) tem valores **propostos**, não medidos — substituir por medição no M3.
- [ ] `source/README.md` descreve o estado do frontend, mas o README do DemoMuseum precisa ganhar o
      passo a passo real quando a pipeline estiver ligada.
- [x] **Commitar e publicar** as mudanças de frontend de 2026-09-18 (vídeo do hero via YouTube,
      backdrops das seções como `<img class="sec-bg">`, legenda do carrossel colada, diagnóstico do
      viewer 3D, `reasonix.toml`, `.github/workflows/pages.yml`, ADRs 0004/0005, `tools/fetch_vendor.py`)
      — feito no push desta sessão; o Pages só publica o que está no `main`.
- [x] **Settings → Pages → Source = "GitHub Actions"** (ADR 0005) — feito pelo dono. A API confirma
      `build_type: workflow` e `html_url: https://agua-games.github.io/Musa_app-service/`.
- [ ] **Confirmar os viewers WebGL em navegador real.** O defeito (import map com *bare specifier*) foi
      corrigido e o portão `tools/check_frontend.py` passa a reprová-lo no build, mas a sessão de
      2026-09-18 **não conseguiu** refazer o teste de clique: no meio da sessão o Chrome do sandbox
      deixou de funcionar (`spawn EPERM`, `--dump-dom` sem saída, `--remote-debugging-port` não abre).
      Falta: abrir o site, abrir um card de **Silver** (GLB) e a **sala Gold** (digital twin) e ver a
      malha. Confirmado só estaticamente: valor do import map, arquivos vendor presentes no artifact
      publicado e os 4 GLB com o tamanho byte-exato.
- [ ] **Verificar a legenda do carrossel** (visual, nunca medida) em navegador de verdade.
- [ ] **`Musa_montage_02_web.mp4` (4,3 MB): decidir e agir.** Verificado em 2026-09-18: a faixa de
      vídeo é **HEVC/H.265** (`hvc1` presente, `avc1` ausente) e **nenhum navegador decodifica** — o
      `<video>` reporta `readyState: 4` com `videoWidth: 0` e pinta nada. O arquivo ficou **sem
      referência** no markup e foi para o `.gitignore` com essa justificativa. Para voltar ao
      auto-hospedado (ADR 0004), transcodifique para H.264/AVC e devolva o `<video>` a `#heroVideo`:
      `ffmpeg -i Musa_montage_02_web.mp4 -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p -movflags +faststart -an montage_h264.mp4`
- [x] **ADR do vídeo do hero** — registrada como **ADR 0007** (YouTube, exceção à ADR 0004).
- [x] **Decidir sobre a foto do hero** — resolvido pelo refactor do M0.2: a foto voltou a ser
      **camada configurável** (`data-skin="hero"` + `site.skin.hero` no `museum.config.json`);
      o demo a deixa desligada de propósito enquanto o filme é verificado.
- [ ] **Reavaliar os binários versionados.** ~29,6 MB de GLB e ~50 MB de JPEG do demo entraram no git
      para o Pages funcionar sem object store (viola o §5.3 de propósito). Quando houver bucket, tire
      os binários do git **e reescreva a história** (`reflog expire --all` + `gc --prune=now`) — sem
      isso o blob fica no `.git` para sempre (§7).

---

## 12. Regra de ouro

Se você só puder guardar uma coisa deste documento:

> **O portão fica no build, o contrato é a verdade, e binário não entra no git.**
