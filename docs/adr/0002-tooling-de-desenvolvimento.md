# ADR 0002 — Tooling de desenvolvimento assistido por IA

- **Status:** aceita
- **Data:** 2026-09-16
- **Relacionada:** ADR 0001 (camada de acervo)

## Contexto

O MUSA é um projeto pequeno com muita superfície: frontend 3D, pipeline de dados, USD, RAG.
O objetivo declarado do responsável pelo frontend é **maximizar o retorno por hora** —
automatizar o máximo possível e atuar como consultor, não como operador.

Nesse cenário, a restrição prática não é "qual é a melhor ferramenta de IA", e sim: **como um
agente de IA enxerga o repositório**. Sem um índice, o agente adivinha caminhos de arquivo, lê
arquivos errados e afirma coisas com confiança sobre código que não existe.

## Decisão

**Usar um índice de codebase exposto por MCP como fonte primária de exploração**, e tratá-lo
como dado derivado (nunca como fonte de verdade).

Configuração atual, verificada nos arquivos do repositório:

| Arquivo | Servidor | Comando |
|---|---|---|
| `.vscode/mcp.json` | `codebase-memo` | `codebase-memory-mcp.exe` (extensão `tunakite03.codebase-memory-mcp`) |
| `.cursor/mcp.json` | `codebase-memo` | idem |

Regras de uso, registradas em `AGENTS.md` e em `.github/copilot-instructions.md`:

1. `list_projects` **primeiro**, para descobrir o identificador do projeto. Nunca adivinhar.
2. `get_architecture` antes de qualquer mudança, para não editar no escuro.
3. `search_graph` / `trace_path` para localizar símbolos; `get_code_snippet` para ler.
4. Ferramentas de busca textual entram **depois**, para confirmar uma string exata que o grafo
   afirma — não para explorar.

## Limitações conhecidas (verificadas em uso, 2026-09-16)

- **`index_repository` é no-op quando o projeto já está indexado.** Contagens de nós/arestas e
  `size_bytes` idênticos significam que **nada** foi re-extraído — arquivos novos continuam
  invisíveis. O caminho que funciona é `delete_project` + `index_repository` (o grafo é dado
  derivado, então apagar é seguro, mas é uma ação que se aprova antes).
- **Neste repositório o grafo não tem símbolos de código.** Enquanto o repo for só documentação,
  o índice contém nós `Section` de Markdown e nenhuma função — consultas de símbolo retornam
  vazio, e isso é esperado, não um bug.
- **Busca textual pelo grafo não é grep confiável.** Uma string pode existir no arquivo e não
  aparecer no resultado. Confirmar literais com a busca de texto do editor antes de afirmar que
  algo não existe no código.

## Ferramentas avaliadas e **não** adotadas

Durante as sessões de design foram levantadas ferramentas de terceiros (geradores de site por
prompt, MCPs de busca por contexto longo, indexadores de repositório). Nenhuma foi adotada, e as
afirmações sobre elas — preço, licença, capacidade — **vieram de uma conversa e nunca foram
verificadas neste repositório**. Ficam registradas como hipóteses, não como stack:

- gerador de site imersivo por prompt com servidor MCP;
- MCP de busca em codebase por janela de contexto longa;
- indexadores de repositório para navegação semântica;
- agentes de codificação de terceiros.

Adotar qualquer uma exige o mesmo teste: instalar, rodar contra este repositório, medir.

## Consequências

**Positivas**

- O agente consulta uma estrutura antes de ler arquivos, o que reduz edições em alvos errados.
- O índice é derivado e descartável: nenhuma decisão de arquitetura depende dele.

**Negativas / riscos**

- Um índice **desatualizado responde com confiança** — o pior modo de falha deste repositório.
  Por isso o procedimento de reindexação (`delete_project` + `index_repository`) entra no
  fluxo de trabalho, e não na memória de quem lembrar.
- O `.gitignore` mantém `.codebase-memory/` fora do controle de versão: o índice é local.

## Referências

- `.vscode/mcp.json`, `.cursor/mcp.json`
- `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/codebase-workflow.instructions.md`
- `docs/adr/0001-camada-de-acervo.md`
