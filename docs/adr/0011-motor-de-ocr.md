# ADR 0011 — Motor de OCR: docling (pip, headless, CPU) atrás de interface substituível

- **Status:** proposta (aguardando aprovação do dono — M2.0)
- **Data:** 2026-10-08
- **Relacionada:** ADR 0002 (tooling), spec §2.3.2, `docs/M2_plano.md` fase M2.2

## Contexto

A promessa comercial do MUSA começa com OCR em lote sobre fotos de fichas de
acervo (spec §2.3). A spec recomenda três ferramentas, todas headless e batch:
Folio-OCR (Docker/CLI, layout com GLM-OCR + PP-DocLayoutV3), docling-OCR-OnnxTR
(pip, CPU/GPU/OpenVINO) e vlm4ocr (VLMs Qwen/LLaVa).

O que pesa:

1. **A máquina de desenvolvimento é o Windows do estúdio, sem daemon Docker.**
   Folio-OCR exige Docker — no Windows isso significa Docker Desktop (pesado,
   licença comercial acima de certo porte) ou WSL2 tuning; atrito antes da
   primeira medição.
2. **OCR é o risco nº 1 do produto** (HANDOFF §10.2: qualidade em ficha
   manuscrita nunca foi medida). A decisão certa não é "o melhor OCR", é "o OCR
   que nos deixa medir mais rápido" — e trocar de motor sem reescrever a
   pipeline se a medição reprovar.
3. **Custo zero marginal**: OCR roda local, por decisão do dono (2026-09) —
   nenhum componente do M2 pode exigir subscription ou cobrança por chamada
   nesta fase.
4. **Saída normalizada importa mais que o motor**: a pipeline consome
   `ocr/*.json` (texto bruto + caixas de layout por bloco). Qualquer motor que
   emita esse formato serve.

## Decisão proposta

1. **docling como motor primário** do M2.2 — `pip install docling`, modo
   headless, batch, CPU. Sem Docker, sem serviço, sem custo.
2. **O motor fica atrás de uma interface** (`pipeline/ocr/engine.py`):
   `run(image_path) -> {text, blocks: [{text, bbox, confidence}]}`. O runner de
   lote só conhece a interface; trocar de motor = trocar um arquivo.
3. **Formato de saída fixo** (`ocr/*.json` por ficha + entrada no log
   estruturado do M1.5), independente do motor.
4. **Falha individual não derruba o lote** — ficha problemática vai para
   `ocr/failed/` com o motivo.
5. **Teste de aceite falsificável**: rodar o corpus real do M2.1 (50 fichas) e
   publicar taxa de caracteres reconhecidos e campos legíveis por ficha. Se a
   ficha manuscrita reprovar, o fallback é o M2.2 trocar o motor — não mudar o
   produto.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Folio-OCR** | Melhor análise de layout, mas exige Docker no Windows do estúdio — atrito e custo de setup antes da primeira medição. Continua como candidato nº 1 de fallback atrás da mesma interface |
| **vlm4ocr (VLMs)** | Uma VLM por página é ordens de grandeza mais lenta em CPU e pede GPU para lote de 500; pode ser o fallback específico para manuscritos se o docling reprovar neles |
| **API de OCR em nuvem** (Azure AI Vision, Google Vision) | Melhor qualidade em manuscrito, mas cobrança por chamada + dados saindo da máquina — viola a restrição de custo do M2; só se os dois motores locais reprovarem |
| **Tesseract puro** | Grátis e clássico, mas sem análise de layout — e ficha de acervo é documento de layout (rótulo: valor), não parágrafo corrido |

## Consequências

- Primeira medição de OCR em dias, não em setup de infraestrutura.
- A pipeline inteira (estruturação LLM, confiança, fila) é agnóstica ao motor —
  trocar docling por Folio-OCR ou VLM é uma mudança localizada, sem ADR nova se
  o formato de saída se mantiver.
- Risco aceito: docling pode ser fraco em manuscrito; mitigado pelo corpus real
  do M2.1 existir **antes** do runner (medimos cedo) e pelo fallback planejado.
- Nenhum dado sai da máquina do estúdio nesta fase — quando clientes reais
  entrarem (M3/M4), a questão de onde o OCR roda volta à mesa (LGPD).
