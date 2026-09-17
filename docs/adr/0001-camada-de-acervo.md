# ADR 0001 — Camada de acervo: contract-first, backend-agnóstica

- **Status:** aceita
- **Data:** 2026-09-16
- **Substitui:** a decisão implícita de usar **Tainacan** (WordPress) como backend de acervo,
  registrada em `docs/Musa_design document_technical-specs_v1.1.md` (original) e nos logs de
  sessão.

## Contexto

O documento original (`v1.0` / `v1.1`) assumia o **Tainacan** — plugin WordPress com API REST —
como "espinha dorsal" da gestão de acervo. Três restrições tornaram essa escolha inadequada para
o MUSA:

1. **Acoplamento ao WordPress.** A pilha WordPress impõe um ciclo de desenvolvimento e uma
   camada de plugins/hooks que atritam com o objetivo de prototipar o frontend (WebGL /
   WebAssembly) de forma direta, em HTML+CSS+JS.
2. **Formato de asset.** O MUSA precisa que o `.usd` (ou `.glb`, no MVP) seja a fonte de verdade
   do asset. O Tainacan não lê `.usd` nativamente; qualquer integração dependeria de um
   importador customizado — um projeto de desenvolvimento inteiro só como ponte.
3. **Custo de troca.** Amarrar o contrato de dados ao fornecedor tornaria caro migrar para um
   catálogo museológico (Omeka S / CollectiveAccess) caso um cliente exigisse padrões
   museológicos.

Além disso, a especificação v1.1 misturava, no mesmo diagrama, o **backend de acervo** e o
**backend de serviço** (painel de módulos, faturamento, fila de demandas) — acoplamento que
encarece qualquer evolução independente.

## Decisão

A camada de acervo passa a ser **contract-first e backend-agnóstica**:

- **Contrato único:** `schemas/ficha.schema.json` (JSON Schema) define a ficha universal.
  Fonte de verdade dos dados: o diretório `acervo/` em disco (pastas = coleções/subcoleções;
  arquivos = fichas + assets), versionado em Git.
- **API estável:** `/collections`, `/collections/{id}/items`, `/items/{id}`, `/schema`,
  `/search` — recursos que não mudam quando a implementação muda.
- **Sem WordPress**, em nenhum estágio.
- **Implementação por estágio:**

  | Estágio | Implementação | Dependências |
  |---|---|---|
  | MVP | índice em build-time (`catalog.json` + SQLite) sobre `acervo/`; site estático | nenhuma |
  | Escala | **Payload** (TypeScript/Next.js) sobre PostgreSQL (+ `pgvector`) | Node.js, PostgreSQL |
  | Padrões | Omeka S ou CollectiveAccess 2.0 | PHP, MySQL |

- **Ficha valida o build:** ficha fora do contrato **falha o build**, e não é publicada.
- **Campos de asset agnósticos de formato:** `model_primary` (o que o frontend carrega),
  `model_source` (arquivo-fonte, opcional), `model_formats`, `model_viewer`. Isso permite
  "GLB puro" no MVP e "USD contendo GLB" depois, sem mudar o contrato.
- **Separação de serviços:** o backend de acervo deixa de ser o mesmo artefato do backend de
  serviço (módulos, faturamento, fila de demandas).

## Alternativas consideradas

| Alternativa | Stack | Prós | Por que não (agora) |
|---|---|---|---|
| **Tainacan** | WordPress + MySQL (GPL-3.0) | maduro, API REST, adoção no Brasil | acoplamento ao WordPress; não lê `.usd`; ciclo de prototipação lento |
| **Omeka S** | LAMP (PHP + MySQL, GPL-3.0) | padrões de acervo, linked open data, multi-site | mantido como **modo padrões**, não como base: exige PHP+MySQL desde o dia 1 |
| **CollectiveAccess 2.0.11** | PHP 8.2/8.3 + MySQL (GPL-3.0) | Providence + Pawtucket2, **API GraphQL**, suporte a mídia 3D, export BagIT | idem: só quando o cliente exigir padrões museológicos |
| **Directus** | TypeScript, qualquer SQL | REST+GraphQL automáticos, Studio, MCP nativo | licença **MSCL 1.0 (source-available)** com limite de receita/empregados — risco comercial para serviço vendido em tiers |
| **Payload** | TypeScript/Next.js, PostgreSQL/MongoDB | REST+GraphQL+Local API, admin, código que possuímos | **escolhido** para o estágio de escala |
| **CollectionBuilder / Canopy IIIF** | Jekyll / Node + IIIF | site estático a partir de CSV / coleção IIIF | avaliados como referência de entrega estática; não cobrem a edição de acervo |
| **índice build-time + site estático** | Python + JSON/SQLite | zero dependências, zero banco, valida o contrato já | **escolhido** para o MVP |

### Nota sobre IIIF (verificado em `iiif.io/api`, 2026-09-16)

Especificações correntes: **Image API 3.0.0**, **Presentation API 3.0.0**, Authorization Flow 2.0,
Change Discovery 1.0, Content Search 2.0, Content State 1.0. Rascunho: **Presentation API 4.0.0
(release candidate)**. Extensões aprovadas: `navPlace`, `Text Granularity`, `Georeference`.

**Não há API IIIF para 3D.** O IIIF padroniza a entrega de imagens 2D (e é excelente nisso); o
3D permanece fora do padrão e fica com o par USD (fonte) + GLB (entrega).

### Nota sobre licenças

Omeka S e CollectiveAccess são **GPL-3.0**: o copyleft é acionado ao **distribuir** o software,
não pela hospedagem como serviço. Se o MUSA passar a instalar o software em servidores do
cliente, a obrigação de fornecer o código-fonte correspondente passa a valer.

## Consequências

**Positivas**

- O contrato de dados é independente de qualquer fornecedor; trocar de backend não migra dados.
- O MVP não tem PHP, MySQL nem WordPress: iteração rápida com assistentes de IA sobre HTML/CSS/JS.
- Validação no build mantém o "asset watertight" verificável (ficha inválida não publica).
- O frontend decide o viewer por dado (`model_viewer`), permitindo evoluir de Three.js para
  USD/WASM sem reescrever a camada de dados.

**Negativas / riscos**

- No MVP não há UI de catalogação nem controle de acesso: a edição é feita por arquivo (e por
  revisão de código). Aceitável enquanto o volume de fichas for gerido pelo pipeline.
- Recursos de acervo presentes no Tainacan/Omeka (busca facetada avançada, histórico de
  proveniência, controle de autoridade) só chegam nos estágios seguintes.
- A estratégia "modelos por estágio" exige disciplina: o contrato não pode vazar detalhes de
  Payload para o frontend.

## Referências

- `docs/Musa_design document_technical-specs_v1.1.md` §2.1, §3.1, §3.2, §5.2, §6.1, §6.2
- `docs/Musa_design document_v1.0.md` — tabela de tecnologia e diferenciais
- `docs/Components chain_design session.md` — arquitetura "USD-first", já sem WordPress
- `schemas/ficha.schema.json` — o contrato em si
