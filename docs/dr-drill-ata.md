# Ata de DR drill — recuperação de desastre do overlay

> Executado em 2026-10-16
> por `tools/dr_drill.py` — não editado à mão. Alvo (SLO, `docs/M3_slos.md`):
> **RPO 0 / RTO < 5 min** para as edições de admin do overlay `.musa/`.

## Cenário ensaiado

Perda total da máquina que servia o museu (`DemoMuseum`): repositório **e**
overlay apagados. A recuperação usa as duas cópias que existem por desenho:
o **seed** no git (re-clone) e o **último backup local** do overlay
(fora da máquina). Antes do desastre, o drill fez edições de admin que
existiam **só no overlay** (1 coleção, 2 itens — 1 publicado, 1 rascunho) —
é elas que o backup precisa trazer de volta.

## Linha do tempo

| Etapa | Tempo |
|---|---|
| Cópia do repositório (setup, fora do relógio) | 0.8 s |
| Backup agendado (operação normal, fora do relógio) | 0.0 s |
| **T0 — desastre confirmado** (serve morto, repo + overlay destruídos) | 0,0 s |
| Re-clone do seed + restore do backup + boot + verificação | 4.5 s |
| **T1 — serviço verificado de volta** | **RTO = 4.5 s** |

## Veredito: **RTO CUMPRIDO** ✔

- RTO medido **4.5 s** contra alvo de 300 s.
- Payload público após o restore **byte-idêntico**
  ao snapshot pré-desastre (322 itens públicos).
- O app bootou sobre o estado restaurado e contou
  466 itens / 5 coleções.

## Limites honestos deste ensaio

- Rodou numa única máquina, com discos locais. Em produção somam-se o clone
  real do GitHub e o pull da imagem — ambos cobertos pelo SLO de publicação
  (mediana ~36 s medida, `docs/M3_slos.md`), e mesmo somados ficam dentro do
  alvo com folga.
- O backup testado é **local**: a política de retenção (quantas cópias, onde,
  por quanto tempo) é decisão de operação por cliente — ver `docs/runbook.md`.

## Como reproduzir

```bash
python tools/dr_drill.py --repo <repositório do museu> --out docs/dr-drill-ata.md
```
