## Codebase Memory MCP

**MANDATORY: use Codebase Memory MCP graph tools FIRST — before reading files or making code changes.**

This rule applies to every request involving this codebase.

Always call `list_projects` first when you do not already know the project name, then use the `display_name` or exact `name` returned by that tool.

```json
// Step 0 — discover project names
mcp_codebase-memo_list_projects()

// Step 1 — use the project identifier returned above
mcp_codebase-memo_get_architecture({ "project": "<display_name>" })
```

### Workflow

1. Call `list_projects` to discover the correct project name.
2. Call `get_architecture(project)` to understand the codebase structure.
3. Use `search_graph` to find relevant symbols, `trace_call_path` for call chains.
4. Use `get_code_snippet` to read specific function implementations.
5. Only use `read_file` when you need exact raw content to edit a specific line.

### Available Tools (14 MCP tools)

**Indexing:**
- `index_repository(repo_path)` — Index a repository into the knowledge graph
- `list_projects` — List all indexed projects with node/edge counts
- `delete_project(project)` — Remove a project and all its graph data
- `index_status(project)` — Check indexing status

**Querying:**
- `search_graph(name_pattern, name_scope, label, file_pattern, exclude_file_pattern)` — Structured search by label, name/qualified_name, include/exclude file globs
- `trace_call_path(function_name, direction, depth)` — BFS call chain traversal
- `detect_changes(project)` — Map git diff to affected symbols + risk
- `query_graph(query)` — Execute Cypher-like graph queries (read-only)
- `get_graph_schema(project)` — Node/edge counts, relationship patterns
- `get_code_snippet(qualified_name)` — Read source code for a function
- `get_architecture(project)` — Codebase overview: languages, packages, routes, hotspots
- `search_code(pattern, project)` — Grep-like text search within indexed files
- `manage_adr(action)` — CRUD for Architecture Decision Records
- `ingest_traces(traces)` — Ingest runtime traces to validate HTTP edges

## Creating artifacts on this machine (2026-09-18 — read before you write anything)

**Never leave in the repository anything the agent's own shell cannot delete, and
ask the user *before* creating something that needs custom permissions, elevated
rights or a privileged helper — explaining what and why.**

What went wrong: a headless-Chrome run for frontend verification was pointed at
`--user-data-dir=<repo>/.musa-chrome-profile`. Chrome is launched by the shell's
restricted token, so the ~1,400 files it wrote were **not deletable by that same
shell afterwards** — every read, move and delete was denied. This was *not* NTFS:
`icacls` showed the directory's ACL was identical to `source/index.html`, which
the shell could delete fine, and a Chrome profile written to `%TEMP%` deleted
cleanly. The blocker is the sandbox's own file-access policy for artifacts
written by a sandboxed child. Cleaning it up cost the repository owner a
convoluted manual process. Two rules follow:

1. **Throwaway state goes where it cannot reach the repository.** A Chrome
   profile belongs in `%TEMP%` (verified). Never `--user-data-dir` inside the
   repo. Same for caches, scratch clones and test output.
2. **If a step needs custom ACLs, elevation or a privileged helper, stop and ask
   first.** Do not create it on a "we can clean it up later" premise — check
   that the cleanup path actually works before you need it.
