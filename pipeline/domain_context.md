# Contexto de domínio para o agente de estruturação (M2.3)

> Este arquivo é o briefing que o LLM recebe **antes** de qualquer ficha — o
> equivalente ao AGENTS.md de um repositório. Editável e versionado; o
> `structure_agent.py` o injeta no system prompt (no modo batch, é amortizado:
> pago uma vez por lote, não por ficha).

## O que você vai receber

Fotos de **fichas catalográficas de museu** já convertidas em texto por OCR.
São registros de acervos reais (pinturas, esculturas, cerâmica, artes
decorativas, antiguidades egípcias/greco-romanas/asiáticas). Dois layouts
comuns:

- **datilografada**: `Título: valor` na mesma linha (o OCR pode trocar `:` por
  `：`, `;`, ou omitir acentos: "Titulo", "Dimensões" → "Dimens6es");
- **moderna**: rótulo sozinho em caixa alta (`TÍTULO`) e o valor na linha
  seguinte.

Todo card termina com `Nº <asset_id>` — é o identificador da ficha, **nunca**
entra em nenhum campo do card.

## Convenções dos campos

- **titulo**: como impresso. Não traduza, não corrija estilo.
- **autor**: frequentemente ausente; formas reais incluem `Unknown`,
  `Unknown (Attic workshop)`, `Thutmose (workshop, attrib.)`. Se ausente ou
  ilegível, **omita** — nunca invente.
- **data**: formatos reais incluem `1665`, `ca. 1535-50`, `19th century`,
  `500–470 BCE`, `16th century`. Normalize para o contrato: ano `AAAA`; datas
  a.C. como número negativo (`500–470 BCE` → `-500`); `ca.` pode ser omitido;
  `19th century` → `1801-1900`. Se ilegível, omita.
- **material**: vocabulário típico: `Oil on canvas`, `Terracotta`, `Parian
  marble`, `Hard-paste porcelain`, `Limestone, paint`, `Silk, whalebone`.
  Mantenha como impresso (pode estar em inglês), corrigindo só erros claros
  de OCR.
- **dimensoes**: como impresso (`44.5 × 39 cm`, `2 7/8 in. (7.3 cm)`).
  Preserve ambos os sistemas quando presentes.
- **descricao**: uma frase factual baseada **somente** no texto lido. Se a
  ficha tem linha de descrição curta (ex.: `Dish — Greek — Archaic`), use-a;
  não enriqueça com conhecimento externo.
- **tags**: 2–6 palavras em português, minúsculas, derivadas do conteúdo
  (tipo de objeto, cultura, período, técnica). Sempre `llm_inferred`.

## Exemplo completo (entrada OCR → saída esperada)

Entrada:

```
TITULO
  Dish with Saint Roche
DATA
  ca. 1535–50
MATERIAL
  Maiolica (tin-glazed earthenware), lustered
DIMENSÕES
  Overall (confirmed): 2 x 10 7/8 in. (5.1 x 27.6 cm)
DESCRIÇÃO
  Dish
Nº met-185949
```

Saída (apenas o item; sem o número da ficha nos campos):

```json
{
  "card": {
    "titulo": "Dish with Saint Roche",
    "data": "1535-1550",
    "material": "Maiolica (tin-glazed earthenware), lustered",
    "dimensoes": "Overall (confirmed): 2 x 10 7/8 in. (5.1 x 27.6 cm)",
    "descricao": "Dish.",
    "tags": ["cerâmica", "maiólica", "século xvi"]
  },
  "provenance": {
    "titulo": {"source": "ocr_read", "confidence": 0.98},
    "data": {"source": "llm_corrected", "confidence": 0.9},
    "material": {"source": "ocr_read", "confidence": 0.97},
    "dimensoes": {"source": "ocr_read", "confidence": 0.95},
    "descricao": {"source": "ocr_read", "confidence": 0.9},
    "tags": {"source": "llm_inferred", "confidence": 0.8}
  }
}
```
