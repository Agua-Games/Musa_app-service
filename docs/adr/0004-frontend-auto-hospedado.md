# ADR 0004 — Frontend auto-hospedado: three.js vendorizado e mídia licenciada

- **Status:** aceita
- **Data:** 2026-09-18
- **Relacionada:** ADR 0001 (camada de acervo), ADR 0002 (tooling)

## Contexto

A landing page do `source/` carregava three.js por um **import map apontando para o CDN**
(jsDelivr). Em uso real o visualizador WebGL falhava com *"The WebGL viewer could not load
(Three.js CDN unreachable)"*: uma rede que bloqueia CDNs de terceiros não degrada o 3D — ela o
**desliga inteiro**, em silêncio, e o erro só aparece na interação do visitante. O mesmo problema
não afeta três.js sozinho: qualquer dependência de runtime que o site busque fora de si tem esse
modo de falha.

Ao mesmo tempo, o player do cinema (`source/data/catalog.js → films`) apontava para clipes de
amostra genéricos do Google, sem relação com a programação de arte anunciada.

Estas escolhas não estavam registradas em nenhum ADR. Elas são registradas agora.

## Decisão

1. **three.js é fixado e vendorizado, não buscado em CDN.** O import map em `source/index.html`
   aponta para `source/assets/vendor/three/`. A revisão está fixada em **r160** e é reproduzível
   por `tools/fetch_vendor.py` (mesmo padrão de `tools/fetch_models.py`). O CDN deixa de ser
   dependência de runtime.
2. **O filme do header é o material do próprio cliente** (a montagem da Agua Games no YouTube),
   injetado em runtime pela IFrame Player API: sem controles, sem marca, em loop. A fotografia
   ainda em `assets/img/hero-museum-hall.jpg` permanece como camada-base e **fallback** — se o
   YouTube não resolver, ou se o visitante pedir `prefers-reduced-motion`, o header continua.
3. **O cinema embute cópias autorizadas de domínio público do Internet Archive:**
   *Metropolis* (1927), *Nosferatu* (1922) e *The Cabinet of Dr. Caligari* (1920). *Modern Times*
   (1936) **sai da grade** — ainda protegido nos EUA — e é **substituído** por Caligari, também em
   domínio público. Cada filme exibe sua linha de crédito/licença no player.
4. **A imagem da sala (The Room / Collections) passa a ser fotografia `demo_*` do cliente**
   (`demo_room (16)`), no lugar da foto de banco. Os fundos das seções usam a mesma família de
   imagens, com um zoom lento.

## Consequências

**Positivas**

- O 3D funciona **sem rede externa** (fonts do Google continuam sendo CDN, mas são decorativas).
- Crédito e licença de cada stream são explícitos, o que é o requisito de M4.

**Negativas / riscos**

- O `vendor/` é **entrada de build reproduzível**, não fonte editada à mão: precisa ser gerado por
  `tools/fetch_vendor.py` após um clone (ou versionado conscientemente — decisão que segue a
  invariante nº 3 em `docs/HANDOFF.md`). O `BufferGeometryUtils.js` vendorizado é um subconjunto
  mínimo (só o símbolo que o `GLTFLoader` importa); o script traz o arquivo canônico completo.
- As imagens `demo_*` são binários grandes (~50 MB) e **não** entram no git pela mesma política dos
  `.glb` — hoje ainda estão soltas em `source/assets/img/`.
- Os streams vêm do Internet Archive, fora do nosso controle: são externos e pesados. É aceitável
  no scaffold; a produção usa a pipeline de streaming.

## Referências

- `source/index.html`, `source/assets/vendor/three/`, `tools/fetch_vendor.py`
- `source/data/catalog.js` (filmes), `source/assets/js/main.js` (header/carrossel/viewer)
- `docs/HANDOFF.md` (invariantes), `docs/adr/0001-camada-de-acervo.md`
