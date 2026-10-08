# Pipeline de catalogação (M2)

Ferramenta da **equipe da plataforma** — não faz parte da imagem do app nem do
repo do cliente. Transforma fotos de fichas físicas em `card.json` validados,
com proveniência por campo e custo logado. Plano completo: `docs/M2_plano.md`;
decisões: ADRs 0011–0013.

## Estrutura

```
pipeline/
  fetch_seed_metadata.py    # baixa metadados reais do Met Open Access (cache local)
  render_corpus.py          # renderiza fichas sintéticas + gabarito (seed fixa)
  validate_ground_truth.py  # valida o gabarito contra o contrato v1 do builder
  corpus/                   # LOCAL, gitignored — nunca vai ao git nem ao bucket
    seed/met-objects.json   # cache da API (re-run retoma de onde parou)
    images/<asset_id>.jpg   # ficha renderizada
    ground-truth/<asset_id>.json
```

## Uso (na raiz da plataforma)

```bash
python pipeline/fetch_seed_metadata.py --target 450
python pipeline/render_corpus.py --limit 450 --seed 42
python pipeline/validate_ground_truth.py
```

## OCR (M2.2)

```bash
cd pipeline
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-ocr.txt
.venv/Scripts/python.exe run_ocr.py            # resumível; falhas em corpus/ocr/failed/
.venv/Scripts/python.exe ocr_report.py         # tempo, falhas, char recall vs. gabarito
```

Baseline das 450 fichas sintéticas (2026-10-08): 0 falhas, 4.32 s/ficha, char
recall médio 0.937 (mediana 0.958). Detalhe: `docs/M2_plano.md` fase M2.2.

## Corpus real (50 fichas) — guia de coleta

O corpus sintético mede a pipeline; o corpus real mede o **produto** (HANDOFF
§10.2: OCR de ficha manuscrita nunca foi medido). Fotografar fichas/etiquetas
reais de acervo (museus com política de fotografia aberta, acervo próprio, ou
fichas históricas digitalizadas de domínio público), cobrindo:

- **manuscritas** (caneta, lápis — as mais importantes: ~15);
- **datilografadas** antigas, com fita desbotada (~10);
- **impressas modernas** (~10);
- **condições ruins**: inclinadas, sombra parcial, brilho de vidro, fundo
  poluído, baixa luz (~10);
- **multilíngues / campos faltando** (sem autor, data ilegível) (~5).

Regras: celular comum (nada de scanner), JPG como saiu da câmera, em
`corpus/real/`; o gabarito de cada uma é digitado **uma vez** em
`corpus/real/ground-truth/<id>.json` seguindo o contrato v1. Fotos de fichas de
museus terceiros **não** vão ao git nem ao bucket público (risco 3 do plano M2).
