# M3.5 — Carga: N museus × M itens

> Medição local de 2026-10-12T025958Z (máquina do estúdio: AMD64 Family 23 Model 8 Stepping 2, AuthenticAMD, 34.3 GB RAM, Windows 10, Python 3.12.14). Corpus sintético **só de metadados** (cards JSON do seed do Met, sem assets) — zero rede, zero R2, zero custo. Números marcados **MEDIDO** saíram desta máquina; **ESTIMATIVA** = fórmula, extrapolação ou preço publicado. Latências abaixo de ~16 ms estão no limite do tick do agendador do Windows — ler como "rápido demais para medir com precisão neste setup".

## 1. Escala de itens por museu

| Itens | Build (s) MEDIDO | Payload api/ (MB) MEDIDO | Site total (MB) MEDIDO | Startup serve (ms) MEDIDO | /collections/items p50/p95 (ms) MEDIDO | /search p50/p95 (ms) MEDIDO | /items/{id} p50/p95 (ms) MEDIDO |
|---|---|---|---|---|---|---|---|
| 500 | 1.2 | 0.89 | 3.38 | 1703 | 15.0/16.0 | 15.0/16.0 | 0.0/16.0 |
| 2000 | 3.7 | 3.55 | 8.82 | 1656 | 23.5/32.0 | 31.0/47.0 | 0.0/16.0 |
| 5000 | 8.8 | 8.89 | 19.71 | 1688 | 47.0/63.0 | 78.0/125.0 | 0.0/16.0 |
| 10000 | 17.0 | 18.03 | 38.16 | 1671 | 109.0/156.0 | 172.0/235.0 | 0.0/16.0 |

Baseline de referência: acervo real do DemoMuseum (463 itens) = 7,3 s de build local, 36 s de CI com deploy (M3_plano.md).

## 2. Escala de museus (500 itens por instância, mesmo processo)

RSS base do processo (sem instância): 34.4 MB MEDIDO.

| Instâncias | RSS total (MB) MEDIDO | MB marginais por instância MEDIDO | /collections/items p50 (ms) MEDIDO |
|---|---|---|---|
| 1 | 65.5 | 31.1 | 15.0 |
| 2 | 69.5 | 4.0 | 11.2 |
| 4 | 77.3 | 3.9 | 15.0 |
| 8 | 92.7 | 3.9 | 11.2 |

Marginal médio por instância: **3.9 MB** MEDIDO. Extrapolação **ESTIMATIVA**: 20 museus de 500 itens ≈ 113 MB de RAM no processo host — a máquina do estúdio comporta; o dimensionamento do App Service (M4) parte daqui.

## 3. Custo por museu (Cloudflare R2) — ESTIMATIVA sobre preço publicado

Preços R2 (tabela pública, out/2026 — confirmar antes de precificar): storage US$ 0,015/GB·mês; operações Classe A (escrita) US$ 4,50/milhão; Classe B (leitura) US$ 0,36/milhão; **egress zero**. Câmbio assumido: US$ 1 ≈ R$ 5,60 (assunção, não medição).

- Payload medido por card: **1803 bytes** (média do corpus de 10000 itens, MEDIDO) — JSON puro é desprezível: 10.000 cards ≈ 18.03 MB ≈ US$ 0,0002/mês de storage.
- O custo real é dos **assets do cliente** (fotos/modelos): 2.000 peças × 1 foto de 500 KB ≈ 1 GB ≈ US$ 0,015/mês ≈ R$ 0,08 (ESTIMATIVA).
- Leituras (Class B): 100 mil páginas/mês com 5 requests ao bucket cada = 500 mil ops ≈ US$ 0,18/mês ≈ R$ 1,00 (ESTIMATIVA).
- **Conclusão**: na faixa do MVP, R2 é centavos por museu por mês; o custo que manda é o compute (App Service, M4), não o storage.

## Como reproduzir

```bash
python -m beta.load                     # tabela completa (reescreve este doc)
python -m beta.load --scales 500,2000   # parcial
```
