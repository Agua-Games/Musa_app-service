# ADR 0009 — Object storage da mídia: Cloudflare R2

- **Status:** aceita
- **Data:** 2026-09-24
- **Relacionada:** ADR 0004 (frontend auto-hospedado), ADR 0006 (artefato), ADR 0008 (backend M1)

## Contexto

O M1.3 tira a mídia do repo do cliente: imagens e GLBs passam a viver em object
storage, e a ficha referencia URL pública em vez de caminho local. Isso resolve de
vez o problema já vivido no M0 (repo do DemoMuseum inchado por dezenas de MB de
fotos; push de 40 MB+ estourando timeouts) e é pré-requisito para o admin mínimo
fazer upload (M1.4).

O workload do MUSA é **serving de mídia egress-dominante**: o volume armazenado é
pequeno (~50 GB por cliente na casa das dezenas de clientes), mas cada visita ao
site baixa imagens e modelos 3D — o custo real é o **tráfego de saída**, não o
armazenamento.

Preços verificados em 2026-09-24 (fontes públicas dos fornecedores):

| Fornecedor | Armazenamento | Egress | Free tier |
|---|---|---|---|
| **Cloudflare R2** | $0,015/GB/mês | **$0** | 10 GB/mês |
| **Azure Blob (Hot)** | ~$0,0184/GB/mês | ~$0,087/GB | — |
| **Backblaze B2** | ~$0,006/GB/mês | $0,01/GB após 3× grátis (ilimitado via Cloudflare CDN) | 10 GB |

Cenário modelado: 10 clientes × 50 GB = 500 GB armazenados, ~1 TB/mês de egress
(média de 100 GB de tráfego por site de museu). Resultado: **R2 ≈ $8/mês**;
**Azure Blob ≈ $96/mês** (o egress domina); B2 ≈ $3/mês de storage + egress
coberto se servido via Cloudflare CDN.

O que pesa:

1. **Egress zero do R2** elimina o custo variável que mais assusta no modelo
   multi-cliente — cada play de vídeo, imagem e GLB servido sai de graça.
2. **API S3-compatível**: o tooling de upload (`musa_build upload`) usa
   `boto3`/AWS CLI padrão; trocar de fornecedor depois é trocar endpoint, não
   código.
3. **App Service é o alvo de hosting, mas storage ≠ compute**: usar R2 para mídia
   não impede deploy do container na Azure — o site referencia URLs públicas.
4. O free tier (10 GB) cobre toda a fase demo e os primeiros clientes pequenos.

## Decisão proposta

1. **Cloudflare R2 como object storage padrão da plataforma.**
2. **Um bucket por cliente**: `musa-assets-<museum-id>`, com CORS configurado para
   a origem do site e acesso público de leitura (ou domínio customizado por
   cliente, quando houver).
3. **Fluxo de upload no builder**: `python -m musa_build upload` envia o asset,
   reescreve a ficha com a URL pública e valida contra o contrato — o repo do
   cliente nunca mais versiona binário pesado.
4. **Azure Blob** fica como alternativa documentada para clientes que exigirem
   consolidação de fornecedor (tudo na Azure); **Backblaze B2** como opção de
   menor custo de armazenamento puro. Ambas usam a mesma interface S3-compatível
   do tooling.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Azure Blob como padrão** | Egress ~$0,087/GB torna o serving de mídia o maior custo da plataforma (~12× o R2 no cenário modelado); reservada a quem exigir consolidação Azure |
| **Backblaze B2 como padrão** | Storage mais barato, mas o egress grátis depende de servir via Cloudflare CDN (mais uma peça); R2 entrega egress zero nativo com a mesma simplicidade |
| **Assets no repo do cliente (status quo)** | Já falhou no M0: repo inchado, push lento, impossível para o admin fazer upload |
| **Assets dentro da imagem do container** | Imutável e pesada; cada troca de imagem exigiria rebuild/release — contraria a ADR 0006 |

## Consequências

- Custo de mídia vira previsível e quase fixo (só armazenamento); o crescimento de
  tráfego não escala a conta.
- Tooling de upload é S3-compatível: migrar de fornecedor é trocar endpoint e
  credenciais, sem reescrever código.
- O repo do cliente encolhe para fichas + config + seed leve — o problema de push
  do M0 desaparece estruturalmente.
- Dependência nova: conta Cloudflare da plataforma (R2 é pago além do free tier,
  exige cartão mesmo no tier gratuito) — provisionamento é passo manual do dono,
  como o PAT do GHCR foi.
- Risco aceito: R2 não tem SLA de disponibilidade tão formal quanto Azure/AWS;
  mitigado pelo uso (mídia pública de sites, re-uploadável a partir das fichas).
