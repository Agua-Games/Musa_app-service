# {{museum-name}}

Repositório **cliente** do **MUSA app-service**.

Este repositório contém **apenas**:

- `content/` — as cards, coleções e assets do seu acervo (a fonte de verdade curatorial);
- `museum.config.json` — identidade do museu, tier contratado e a **versão fixada** do MUSA;
- `.github/workflows/deploy.yml` — a pipeline que constrói e publica o site.

**Não contém** — e nunca deve conter — código do MUSA. O site é construído pela imagem de
contêiner publicada pela plataforma (`ghcr.io/agua-games/musa-app:<versão>`), que valida
cada card contra o contrato, aplica o gating de publicação e de tier, e emite o site
estático com um relatório de build. A justificativa completa está em
`Agua-Games/Musa_app-service → docs/adr/0003-onboarding-de-clientes.md`.

## Atualizar o MUSA

Mude **uma linha** em `museum.config.json` e dê push:

```json
"musa": "0.2.0"
```

O CI constrói com a nova imagem. As notas de cada versão estão nos
[Releases da plataforma](https://github.com/Agua-Games/Musa_app-service/releases).

## Publicar uma peça

1. Crie `content/<colecao>/<nome-da-peca>/card.json` seguindo o contrato
   (`asset_id` = nome da pasta; `colecao` = nome da pasta da coleção).
2. `website_status: "published"` publica; `"draft"` (ou ausente) **nunca** chega ao site.
3. `tier` define o mínimo para exibir: peças acima do tier contratado ficam fora do
   payload — o relatório de build explica cada exclusão em uma linha.
4. Push. Se uma card estiver fora do contrato, **o build falha** e o site anterior
   continua no ar.

## Setup único (feito pela equipe MUSA no onboarding)

1. Settings → Pages → Source = **GitHub Actions**.
2. Secret `GHCR_PULL_TOKEN` (PAT com `read:packages`) para o CI baixar a imagem do artefato.
