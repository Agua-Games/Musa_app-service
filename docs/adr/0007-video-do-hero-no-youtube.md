# ADR 0007 — Vídeo do hero hospedado no YouTube (exceção ao ADR 0004)

- **Status:** aceita
- **Data:** 2026-09-23
- **Relacionada:** ADR 0004 (frontend auto-hospedado) — **registra uma exceção a ela**

## Contexto

A ADR 0004 decidiu o frontend auto-hospedado: three.js vendorizado e **nenhum CDN em
tempo de execução**, para que o site funcione em redes de museu que bloqueiam terceiros.

O vídeo do hero, porém, inviabilizou a auto-hospedagem na prática:

- com qualidade mínima razoável, o arquivo ficou **acima de 11 MB** — pesado demais para
  carregar rápido no header de um site de museu;
- a montagem local disponível (`Musa_montage_02_web.mp4`) é **HEVC/H.265**, que nenhum
  navegador decodifica (verificado em 2026-09-18: `readyState: 4` com `videoWidth: 0`);
- hospedado no próprio site, o autoplay do header geraria **centenas de requisições por
  ano por visitante recorrente** só de tráfego de vídeo, sem CDN na frente.

Desde 2026-09-18 o hero monta um player do **YouTube** (`iframe_api`) em `#heroVideo`, e a
foto deixou de ser camada base — uma divergência em aberto da ADR 0004, registrada no
HANDOFF §4/§11 como candidata a ADR.

## Decisão

**O vídeo do hero fica no YouTube.** Decidido pelo dono do produto em 2026-09-23. Fica
registrada como **exceção explícita e única** à regra "sem CDN em runtime" da ADR 0004 —
que **continua valendo para todo o resto** (three.js, fontes, imagens, dados).

Mitigações já implementadas:

1. **O vídeo é do cliente, não do template.** O ID do YouTube vem do catálogo gerado
   (`museum.heroVideo`, origem: `site.heroVideo` no `museum.config.json`). Um museu sem
   vídeo configurado simplesmente não monta o player — o hero cai na foto da skin
   (`data-skin="hero"`) ou no fundo liso.
2. **A foto de base pode ser restaurada por slot** (`site.skin.hero`), sem editar o
   template.
3. O player é decorativo (mudo, sem controles): se a rede bloquear o YouTube, o hero
   degrada para a camada estática sem quebrar nenhuma funcionalidade.

## Consequências

- Se um cliente operar numa rede que bloqueia o YouTube, a recomendação é **não
  configurar `heroVideo`** e usar `skin.hero` com uma fotografia.
- A volta ao auto-hospedado continua possível: transcodificar a montagem para H.264/AVC
  (comando no HANDOFF §11) e servir de object storage — decisão por cliente, não do
  template.
