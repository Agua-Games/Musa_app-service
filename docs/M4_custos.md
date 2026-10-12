# Custos mensais de manutenção do Musa — tabela consolidada (M4)

> Para discussão interna da equipe e base de orçamentos. Criado em 2026-10-12.
> Todo número é marcado: **MEDIDO** (saiu das nossas bancadas — `docs/M3_carga.md`,
> M2), **TABELA** (preço público do fornecedor, verificado em out/2026 — links
> ao final) ou **ESTIMATIVA** (pressuposto nosso, sujeito a revisão).
> Câmbio assumido: **US$ 1 = R$ 5,60** (assunção, não cotação).
> Esta tabela substitui a visão parcial da ADR 0017 (que compara hosting);
> atualizá-la a cada mudança de preço ou de perfil de uso.

## Pressupostos por museu (perfil típico do MVP — ESTIMATIVA)

- Acervo: 500 peças; assets = 500 fotos × 500 KB + 100 GLBs × 5 MB ≈ **0,75 GB**
- Tráfego público: 100 mil pageviews/mês × ~5 requests de asset = **500 mil leituras/mês** no R2
- Curador: **20 sessões de admin/mês** × 5 min de API ativa
- Assistente: **2.000 consultas/mês** (~67/dia), ~3.000 tokens de entrada (RAG top-k + prompt, 50% cache hit) e ~300 de saída; uso 50% peak / 50% off-peak
- Catalogação: 50 fichas novas/mês (estruturação em batch — custo desprezível, MEDIDO: ~150 tokens/ficha)

## Linha a linha (por mês)

| Item | Base de cálculo | Por museu | Observação |
|---|---|---|---|
| **GitHub** (Pages + Actions + ghcr) | repos públicos: Actions ilimitado + Pages grátis (TABELA) | **R$ 0** | Cliente usa a própria conta free (2.000 min/mês ≈ 3.300 builds de 36 s MEDIDO — folga enorme). Ponto de atenção: pacote ghcr **privado** tem 500 MB grátis — limitar tags publicadas ou tornar o pacote público |
| **Cloudflare R2** | storage 0,75 GB × US$ 0,015 + 500 mil Class B × US$ 0,36/M + ~5 mil Class A × US$ 4,50/M; egress zero (TABELA) | **≈ R$ 1,20** | Vídeo/streaming pesado multiplica as leituras Class B — vigiar por museu |
| **Azure Container Apps** (API dinâmica) | 2.000 vCPU·s + 2.000 GiB·s + ~22 mil requests/museu vs. grant gratuito de 180k vCPU·s + 360k GiB·s + 2M requests (TABELA + perfil ESTIMADO) | **R$ 0 até ~90 museus** | Scale-to-zero: museu parado = custo zero. Armadilhas documentadas: `minReplicas > 0` (réplica morna ≈ US$ 4/mês cada) e Log Analytics |
| **DeepSeek** (assistente) | 6M tokens entrada (3M miss × US$ 0,15–0,30 + 3M hit × US$ 0,003–0,006) + 0,6M saída (× US$ 0,60–1,20), mix peak/off-peak 50/50 (TABELA set/2026) | **≈ R$ 6,90** (faixa R$ 4,60–9,20) | Maior linha variável. Se o assistente for embutido na página **pública**, o volume de consultas explode — orçar por museu antes de ligar |
| **Domínio da plataforma** (musa.app ou similar) | ~US$ 15/ano (TABELA) | fixo **≈ R$ 7/mês** | Domínio de cada museu é conta do cliente (~R$ 40/ano, registro.br) |
| **Cloudflare Turnstile** (anti-abuso, M4.2) | gratuito (TABELA) | **R$ 0** | — |
| **Monitoramento/backup** | GitHub + scripts próprios nesta fase | **R$ 0** | Ferramenta paga só se o M4.4 concluir necessidade |

## Totais por cenário (R$/mês)

| Museus | GitHub | R2 | Azure | DeepSeek | Fixo (domínio) | **Total/mês** | Por museu |
|---|---|---|---|---|---|---|---|
| **2** | 0 | 2,40 | 0 | 13,80 | 7 | **≈ R$ 23** | ≈ R$ 11,60 |
| **5** | 0 | 6,00 | 0 | 34,50 | 7 | **≈ R$ 48** | ≈ R$ 9,50 |
| **10** | 0 | 12,00 | 0 | 69,00 | 7 | **≈ R$ 88** | ≈ R$ 8,80 |
| **20** | 0 | 24,00 | 0 | 138,00 | 7 | **≈ R$ 169** | ≈ R$ 8,50 |

Faixa de incerteza (DeepSeek peak/off-peak e cache): 2 museus R$ 17–30 ·
5 museus R$ 36–60 · 10 museus R$ 65–113 · 20 museus R$ 123–219.

## O que muda o cenário (gatilhos a vigiar)

1. **~90 museus** neste perfil: o grant do Container Apps estoura → Azure passa
   a custar alguns US$/mês por museu, ou migramos ao App Service B1
   (≈ R$ 73/mês flat, gatilho da ADR 0017) — o que for menor.
2. **Assistente na página pública**: o pressuposto de 2.000 consultas/mês é de
   curador + testes; público geral pode multiplicar por 10–50×. A cota de
   tokens/museu com circuit breaker (M4.2) é o teto de gasto — define o custo
   máximo, não o esperado.
3. **Vídeo/streaming em acervos**: leituras Class B saem de centavos para
   reais por museu; precificar plano com limite de banda.
4. **Pacote ghcr privado > 500 MB**: mover para público (a imagem é o produto,
   não contém segredos) ou pagar storage — revisar a cada release.
5. **Conta Cloudflare pessoal (nota do HANDOFF)**: os números de R2 acima
   pressupõem a conta da empresa/clientes — hoje esse custo está no cartão
   pessoal do dono e deve ser migrado antes do primeiro cliente.

## Fontes dos preços (verificadas em 2026-10-12)

- Azure Container Apps: grant + US$ 0,000024/vCPU·s ativo, US$ 0,000003/GiB·s,
  US$ 0,40/M requests — [página oficial de preços](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- Cloudflare R2: US$ 0,015/GB·mês, Class A US$ 4,50/M, Class B US$ 0,36/M,
  egress zero — tabela pública da Cloudflare (ADR 0009)
- DeepSeek V4.1 Flash: off-peak US$ 0,15/1M entrada (miss), US$ 0,003 (hit),
  US$ 0,60/1M saída; peak = dobro — [api-docs.deepseek.com](https://api-docs.deepseek.com/)
- GitHub Free: repos ilimitados, Actions ilimitado em repos públicos, 2.000
  min/mês em privados, Pages grátis — [docs.github.com](https://docs.github.com/get-started/learning-about-github/githubs-products)
