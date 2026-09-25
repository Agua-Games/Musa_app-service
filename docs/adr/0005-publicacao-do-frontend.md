# ADR 0005 — Publicação do frontend (GitHub Pages) e assets materializados no build

- **Status:** aceita
- **Data:** 2026-09-18
- **Relacionada:** ADR 0003 (onboarding de clientes), ADR 0004 (frontend auto-hospedado)

## Contexto

O frontend precisa ser testado **online**, não apenas aberto do disco. Abrir
`source/index.html` por `file://` não funciona para boa parte do produto: o navegador
recusa carregar **módulos ES** e **`fetch`** a partir de uma origem opaca, o que derruba o
viewer 3D (`three.js` e o GLB) e o embed do YouTube. O GitHub Pages resolve isso porque
serve por `http(s)`.

O obstáculo é que o GitHub Pages **não aceita um subdiretório**: "Deploy from a branch" só
oferece `/ (root)` ou `/docs`. O site mora em `source/`, e `docs/` é a documentação do
projeto — nenhuma das duas opções serve.

## Decisão

1. **Publicar `source/` via GitHub Actions** (`.github/workflows/pages.yml`), não por
   "Deploy from a branch". O workflow usa `actions/upload-pages-artifact` com
   `path: source`, então a raiz publicada é `source/` sem renomear nada e sem despejar a
   documentação na raiz.
2. **Os binários continuam fora do git.** O `.gitignore` (`*.glb`) e o ADR 0004 (three.js
   vendorizado, não versionado) seguem valendo. O workflow **materializa** os assets em
   tempo de build, rodando `tools/fetch_vendor.py` e `tools/fetch_models.py` — o artefato
   publicado é completo sem que o repositório carregue binário grande.
3. **O portão viaja com o build.** `tools/validate_catalog.py` roda no workflow: um card
   fora do contrato **falha o deploy**, em vez de chegar ao site (invariante §5).

## Consequências

- O site é servido em `https://<owner>.github.io/<repo>/`. Todas as URLs do frontend são
  relativas, então o subcaminho funciona sem `<base>` nem reescrita.
- `venus-de-milo.glb` é passo manual e **não** entra no build publicado: o viewer daquela
  peça cai no estado degradado. Ou se registra a URL de origem (pendência herdada) e ela
  vira um `SOURCES` de `fetch_models.py`, ou a peça fica sem 3D online.
- Os fetchers deixam de ser só conveniência e passam a ser **requisito de build**: se o
  upstream mudar o tamanho de um modelo, `fetch_models.py` falha de propósito.
- Configuração manual, uma vez: **Settings → Pages → Source = "GitHub Actions"**.

## Nota de escopo

Isto publica a **demonstração**. O artefato versionado e consumível por repo de cliente
(`musa-museum-template`, M0 item 2) continua pendente — este ADR não o substitui.
