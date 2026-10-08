# ADR 0013 — Índice vetorial: sqlite-vec por museu, embeddings locais, índice derivado

- **Status:** proposta (aguardando aprovação do dono — M2.0)
- **Data:** 2026-10-08
- **Relacionada:** ADR 0003 (onboarding), ADR 0012 (LLM), spec §2.4,
  `docs/M2_plano.md` fase M2.5

## Contexto

O M2 entrega embeddings + índice vetorial para busca semântica (entregável 5),
base do RAG que o assistente de IA usará depois (spec §2.4). O HANDOFF sugere
pgvector — mas o que pesa:

1. **O serve do M1.4 já usa SQLite por museu** (overlay `.musa/`, arquivo único,
   descartável). Um índice vetorial em SQLite é uma extensão do que existe, não
   infraestrutura nova.
2. **Não há Postgres rodando em lugar nenhum** — nem no estúdio, nem no cliente.
   pgvector exigiria provisionar, operar e fazer backup de um servidor de banco
   para um índice de centenas de vetores. Custo operacional sem benefício nesta
   escala.
3. **Embeddings podem ser locais e grátis**: modelos multilíngues pequenos (ex.
   multilingual-e5-small) rodam em CPU via sentence-transformers com qualidade
   competente em PT-BR — alinhado à regra de custo do dono (sem subscription,
   sem cobrança por chamada nesta fase).
4. **O índice é derivado, nunca fonte da verdade**: a verdade são os
   `card.json`. O índice deve ser regenerável do zero a qualquer momento —
   isso simplifica backup, migração e recuperação de desastre.
5. **O contrato v1 já prevê `embedding`** (campo opcional), mas gravar vetores
   nos cards versionados em git incharia o repo do cliente — exatamente o que o
   M1.3 tirou do git. Vetores pertencem ao overlay.

## Decisão proposta

1. **sqlite-vec** como índice vetorial, dentro do overlay SQLite por museu que o
   `musa-build serve` já mantém — tabela `vec_items` derivada dos cards no
   carregamento, reconstruída quando o conteúdo muda.
2. **Embeddings locais** (multilingual-e5-small ou equivalente, CPU) gerados no
   serve/build da plataforma — custo zero, offline, PT-BR.
3. **Vetores fora do git e fora dos cards**: o campo `embedding` do contrato
   permanece opcional e não é usado pelo M2; o índice vive só no overlay.
4. **O MCP do M1.6 ganha `search_semantic`** ao lado do `search` lexical —
   mesma regra de citar `asset_id` + caminho do card em toda resposta; a busca
   lexical não muda.
5. **Caminho de migração documentado**: quando o backend multi-tenant chegar
   (M3+), o índice por museu pode subir para pgvector no servidor — os vetores
   se regeneram dos cards, então migrar = reindexar.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **pgvector** | Exige Postgres operado desde já (provisionar, backup, atualizar) para centenas de vetores; é a escolha certa para o backend multi-tenant do M3+, não para o índice por museu do M2 |
| **Qdrant / Weaviate / Milvus** | Mais um servidor para operar; mesma objeção do pgvector com ainda mais peças |
| **Embeddings via API (OpenAI etc.)** | Cobrança por chamada e dados saindo da máquina; o modelo local tem custo zero e qualidade suficiente para a escala do M2 — e a interface permite trocar depois |
| **Gravar `embedding` nos cards (contrato prevê)** | Incha o repo do cliente com vetores binários — a mesma lição do M0 que tirou os GLB do git; o índice é derivado e regenerável |
| **FAISS em arquivo próprio** | Bom motor, mas um segundo formato de arquivo para gerenciar; sqlite-vec mora no arquivo que já existe |

## Consequências

- Busca semântica funciona offline, por museu, sem nenhum serviço novo — o
  DemoMuseum ganha `search_semantic` sem um centavo de infraestrutura.
- Backup e restore do índice = copiar (ou simplesmente regenerar) um arquivo
  SQLite — ensaio de DR do M4 fica mais simples.
- Migrar para pgvector no futuro não é reescrita: a interface de busca semântica
  e o gerador de embeddings permanecem; só o armazenamento troca.
- Risco aceito: sqlite-vec é jovem e sua performance em dezenas de milhares de
  vetores não foi medida aqui — irrelevante na escala do M2 (centenas) e medida
  antes de qualquer acervo grande (critério de carga do M3).
