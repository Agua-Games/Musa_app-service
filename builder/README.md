# musa-app — o builder do MUSA app-service

> Transforma o repositório de um cliente (`museum.config.json` + `content/`) no site
> estático do museu. É aqui que moram o **portão do contrato** e o **gating de tier** —
> eles viajam dentro do artefato publicado, nunca no repositório do cliente
> (invariantes §5.1–§5.2 do HANDOFF; ADR 0003 e ADR 0006).

## Como é distribuído

Como **imagem de contêiner** (`ghcr.io/agua-games/musa-app:<versão>`, ADR 0006). O CI do
cliente roda:

```bash
docker run --rm -v "$PWD:/work" ghcr.io/agua-games/musa-app:0.1.0 \
  build --repo /work --frontend /app/frontend --out /work/_site
```

Para desenvolvimento local (neste repositório):

```bash
python -m musa_build build --repo <repo-cliente> --frontend source --out _site   # de builder/
python -m unittest discover -s tests                                             # a suíte, de builder/
```

## O que o build faz, em ordem

1. **Lê `museum.config.json`** — identidade, versão fixada do MUSA, entitlements.
   Um pin que não corresponde à versão do builder **falha o build** (atualizar é trocar
   a tag da imagem, não editar código).
2. **Valida cada `ficha.json`** contra o contrato v1 embutido
   (`musa_build/schemas/ficha.schema.json`, mantido idêntico a `schemas/` por teste).
   Qualquer violação → o build falha e o site anterior continua no ar.
3. **Aplica o gating** — `website_status != "published"` fica de fora; item ou coleção
   com `tier` acima do tier contratado fica de fora. *Fail closed*: status ausente é
   tratado como rascunho; tier desconhecido é excluído.
4. **Emite o site** — frontend genérico (sem conteúdo demo), `data/catalog.js|json`
   gerados, e **somente os assets dos itens incluídos** copiados para
   `assets/content/…` (um rascunho não contribui um byte sequer ao payload).
5. **Escreve o build report** (`build-report.json` + `build-report.md`): o que entrou,
   o que saiu e **por quê** — a resposta de uma linha para "por que esta peça não está
   no site?".

## Formato do repositório do cliente

```
museum.config.json          identidade, pin de versão, entitlements, skin
content/
  site.json                 (opcional) salon, films, products, wallHotspots
  <colecao>/
    collection.json         (opcional) title, description, cover, tier, subcollections
    <item>/
      ficha.json            campos do contrato + website_status, tier, image, hero…
      images/ models/       assets locais (ou URLs de object storage na ficha)
```

Regras de identidade: o `asset_id` da ficha **é** o nome da pasta do item, e `colecao`
**é** o nome da pasta da coleção — divergência falha o build.

Campos de apresentação (não fazem parte do contrato, vivem na ficha):
`website_status` (`published`/`draft`), `tier` (`bronze`/`silver`/`gold` — o mínimo para
exibir), `image`, `hero`, `featured_on`, `subcolecao`.

## `museum.config.json` — referência

| campo | obrigatório | significado |
|---|---|---|
| `museum.id` / `museum.name` | sim | identidade do museu (vira título e marca do site) |
| `museum.tagline`, `museum.locale`, `museum.domain` | não | apresentação |
| `musa` | sim | versão fixada do artefato (`"0.1.0"`; `"0.0.0-unreleased"` só em desenvolvimento) |
| `entitlements.tier` | sim | `bronze` / `silver` / `gold` — o teto do que o site exibe |
| `entitlements.modules` | não | módulos contratados (registrados no payload e no report) |
| `entitlements.signature` | não | assinatura do servidor (M1; hoje gera *warning*) |
| `site.heroVideo` | não | ID de vídeo do YouTube para o hero (ADR 0007) |
| `site.skin.<slot>` | não | imagem de um slot decorativo (`hero`, `collections`, `wall`, `salon`, `bronze`, `silver`, `twin`, `store`, `admin-placeholder`) — caminho no repo ou URL |

## Códigos de saída

- `0` — build verde; site emitido com o report.
- `1` — build falhou (ficha fora do contrato, config inválida, pin errado); o report é
  escrito mesmo assim, com os erros.

## Avisos conhecidos (por desenho, não defeito)

- **Entitlements vêm do arquivo** enquanto o servidor de entitlements não existe (M1) —
  o report registra o *warning* toda vez.
- O plano de fundo de seções sem skin configurada fica vazio: decoração é conteúdo do
  cliente, não do template.
