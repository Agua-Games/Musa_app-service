# Arquitetura do MUSA — guia para quem chega agora

> Público: devs entrando na equipe. Linguagem direta, sem pré-requisito além
> de saber ler Python e JSON. Objetivo: em 20 minutos você entende **o que
> existe, por que existe e onde mexer**. O mapa vivo de arquivos é o
> [`dev-index.md`](dev-index.md); a API endpoint a endpoint está em
> [`api-reference.md`](api-reference.md); o porquê de cada decisão, em
> [`adr/`](adr/).

## 1. O problema que o MUSA resolve

Um museu pequeno quer uma presença digital bonita — catálogo, 3D, assistente
de IA — mas não tem equipe de software. A resposta do MUSA: **o museu cuida
do conteúdo; nós cuidamos de todo o resto, centralizadamente.**

Isso gera a regra de ouro que organiza toda a arquitetura:

> **"Construir uma vez, distribuir para muitos"**: o código do aplicativo e
> o controle de funcionalidades são nossos e imutáveis pelo cliente; o
> acervo é do cliente e vive num repositório dele.

## 2. As três peças fundamentais

### 2.1 O repositório do cliente (a "semente")

Cada museu tem um repositório Git **próprio** contendo apenas:

```
museum.config.json      ← identidade, versão pinada do MUSA, entitlements
content/<colecao>/collection.json
content/<colecao>/<peça>/card.json    ← a ficha técnica (o contrato)
content/<colecao>/<peça>/<assets>     ← imagens, modelos 3D locais (ou URLs)
content/site.json                     ← filmes, produtos, hotspots (opcional)
content/paginas/<slug>.md             ← páginas institucionais (opcional)
```

Zero código MUSA. O formato do card é **público e versionado**
(`schemas/card/v1/`) — portabilidade é uma decisão de produto, não um risco:
o cliente fica porque o serviço é bom, não porque está preso (ver §7 do
contrato de serviço, `docs/contrato-servico.md`).

### 2.2 O artefato (o "motor")

`builder/musa_build/` vira uma **imagem de contêiner** versionada
(`ghcr.io/agua-games/musa-app:0.6.0`) publicada pelo workflow de release
(tag `v*` → gate → build → smoke dentro da imagem → push → GitHub Release).
O cliente referencia uma versão no pin `"musa": "0.6.0"` do config; atualizar
o pin é o mecanismo de upgrade do software.

A imagem tem dois modos:

| Modo | O que faz | Quando roda |
|---|---|---|
| `build` | repo → site estático (HTML + `data/catalog.json` + API estática) | CI do cliente (push → Pages) |
| `serve` | API dinâmica + painel admin (login, publicar peça em tempo real) | instância do museu |

### 2.3 Os entitlements (o "contrato digital")

Um arquivo no config do cliente, **assinado com a chave privada Ed25519 da
plataforma**, dizendo: tier (bronze/silver/gold), módulos ativos, validade.
O build e o serve **verificam a assinatura** — sem ela (ou adulterado), o
sistema não sobe. É assim que funcionalidade é controlada no servidor, não
na interface: recurso não contratado responde 404 como se não existisse
(a "regra stealth"). **Upgrade de plano = re-assinar esse arquivo** — a
narrativa de investidor (`tools/demo_narrative.py`) demonstra isso ao vivo.

## 3. O caminho do dado (build)

```
card.json ──► valida contra o schema (contract.py)
          ──► gate (gate.py): draft fora; tier acima do entitlement fora
          ──► assets: copia os locais; URLs do bucket são HEAD-verificadas
          ──► payload: data/catalog.json + api/ estática + páginas .html
          ──► build-report.json/md: o que entrou, o que ficou fora, por quê
```

Dois invariantes que você deve internalizar:

1. **Um registro excluído pelo gate nem vira arquivo** — não existe rota
   que sirva um draft por engano, porque o bytes dele não existem no site.
2. **O build é total ou nada**: se algo falha, o site anterior fica no ar.

## 4. O caminho do dado (serve / admin)

O `serve` sobe a mesma lógica sobre FastAPI. As escritas do curador (publicar
peça, corrigir card) vão para um **overlay** SQLite em `.musa/` — o repo do
cliente permanece a fonte da verdade (a "semente"); o overlay são as edições
do dia a dia. Consequências que você verá em todo o código:

- **RPO**: acervo versionado = 0 (é git); edições do painel = até o backup
  do overlay (M4.4 — backup/restore cronometrado, DR drill ensaiado).
- **Concorrência otimista** (`_rev`) nos writes; limites de escrita e login
  server-side; sem `MUSA_ADMIN_TOKEN` a instância é estritamente read-only.
- **Rebuild não é necessário para publicar**: a API serve o estado atual
  (overlay + seed) em tempo real; o site estático é regenerado no CI.

## 5. As peças de apoio

| Peça | Papel | Doc |
|---|---|---|
| `pipeline/` | Catalogação assistida por IA: foto de ficha → OCR → LLM estrutura → card pronto para revisão (M2) | `pipeline/README.md` |
| `mcp_server/` | Servidor MCP stdio com 8 ferramentas — operar o acervo a partir de agentes/IDEs; base do assistente | `docs/mcp-server.md` |
| `beta/` | Cliente virtual: personas de uso diário, gerador de uso indevido, bateria de 24 edge cases — tudo executável | `docs/M3_plano.md`, §M4.5 |
| Assistente | Endpoint server-side com anti-abuso em camadas (rate limit, Turnstile, guarda de escopo de acervo) | `docs/M4_plano.md` §M4.2 |

## 6. Como as decisões se encadeiam (leia nesta ordem se quiser o "porquê")

1. `docs/adr/0003-onboarding-de-clientes.md` — repo do cliente como seed.
2. ADR 0006 — artefato = imagem de contêiner + GitHub Releases.
3. ADR 0008 — API estática primeiro; dinâmica depois, mesmas formas.
4. ADR 0009 — uploads de mídia: por que o stub honesto antes do upload real.
5. `docs/entitlements.md` — o modelo de licenciamento assinado.
6. `docs/M3_slos.md` — os números medidos que viraram SLO contratual.

## 7. Onde mexer para…

- **Mudar o contrato do card** → `schemas/card/v1/` + versão em
  `builder/musa_build/__init__.py` (`CONTRACT_VERSION`) + a cópia embutida
  (o teste de drift falha se divergirem). Regras de compatibilidade:
  `schemas/COMPATIBILITY.md`.
- **Adicionar um endpoint** → `serve.py` + anotação em `api_reference.py`
  (sem anotação, o build da doc falha) + teste em `builder/tests/`.
- **Mudar a landing/admin** → `source/` (é o template que todo cliente
  herda). Rode `tools/check_frontend.py`.
- **Nova ferramenta de plataforma** → `tools/<nome>.py` com docstring de uso,
  entrada em `docs/comandos-dev.md`, e regenere `docs/dev-index.md`.

## 8. Verdades operacionais (evite aprender na dor)

- **Testes antes de push**, sempre: as 3 suítes de `docs/comandos-dev.md`.
- **Logs**: leia com `tools/logread.py` (colapsa repetições), nunca `cat`.
- **Nada de agendamentos/custos de nuvem ativos** sem cliente pagante —
  decisão do dono registrada nos workflows.
- **O repo é privado e sensível** (preços, estratégia): não copie trechos
  para lugares públicos.
- Git Bash no Windows: caminhos com `/tmp` não resolvem no Python nativo —
  use `cygpath -w` ou paths `H:/...`.
