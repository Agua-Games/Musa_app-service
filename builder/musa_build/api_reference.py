"""Generate the HTTP API reference (docs/api-reference.md) from the running
app — never by hand.

The doc is rendered by introspecting the FastAPI routes of `serve.create_app`
(built on the fixture museum) and merging them with the curated annotations
below. The merge is strict: an endpoint without an annotation — or an
annotation without an endpoint — raises, so the reference can never silently
drift from the code. The freshness test (builder/tests/test_api_reference.py)
fails the pre-push suite when the committed doc is stale.

Regenerate:  cd builder && python -m musa_build api-reference
Check only:  cd builder && python -m musa_build api-reference --check
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from fastapi.routing import APIRoute

from . import __version__

PLATFORM_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_REPO = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "client-ok"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "card.schema.json"
DEFAULT_OUT = PLATFORM_ROOT / "docs" / "api-reference.md"

_SKIP_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

# Curated documentation per endpoint. Keys MUST match the discovered
# (method, path) set exactly — generate() refuses to render otherwise.
ANNOTATIONS: dict[tuple[str, str], dict] = {
    ("GET", "/health"): {
        "secao": "ops",
        "descricao": "Liveness. Informa versão da plataforma, versão do contrato "
                     "e se a instância aceita escritas (`writes`).",
        "auth": "público",
        "resposta": '`{"status": "ok", "museum": "…", "version": "…", "contract": "…", "writes": "enabled|disabled"}`',
        "erros": {},
    },
    ("GET", "/schema"): {
        "secao": "ops",
        "descricao": "O contrato do card (`card.schema.json`), verbatim — o mesmo "
                     "arquivo que o build usa no portão de validação.",
        "auth": "público",
        "resposta": "o JSON Schema do contrato, sem envelope",
        "erros": {},
    },
    ("GET", "/collections"): {
        "secao": "leitura",
        "descricao": "Coleções **incluídas** (publicadas e dentro do tier). Uma "
                     "coleção excluída pelo portão não aparece nem como existente.",
        "auth": "público",
        "resposta": "envelope com lista de coleções",
        "erros": {},
    },
    ("GET", "/collections/{collection_id}/items"): {
        "secao": "leitura",
        "descricao": "Itens incluídos da coleção. `?include_drafts=1` exige token e "
                     "devolve também os rascunhos (visão do admin).",
        "auth": "público; `include_drafts=1` exige token",
        "resposta": "envelope com lista de cards",
        "erros": {
            "401": "`include_drafts=1` sem token válido",
            "404": "coleção inexistente **ou excluída pelo portão** (draft/tier) — não vaza nem a existência",
            "503": "instância sem `MUSA_ADMIN_TOKEN` (writes disabled) ao pedir drafts",
        },
    },
    ("GET", "/items/{asset_id}"): {
        "secao": "leitura",
        "descricao": "Card completa de uma peça. Com token, o admin enxerga os "
                     "próprios rascunhos; o portão de tier nunca relaxa.",
        "auth": "público; drafts só com token",
        "resposta": "envelope com o card",
        "erros": {"404": "item inexistente, draft sem token, ou acima do tier"},
    },
    ("GET", "/search"): {
        "secao": "leitura",
        "descricao": "Busca por interseção de tokens sobre o índice dos itens "
                     "públicos. `q` vazio devolve lista vazia.",
        "auth": "público",
        "resposta": "envelope com os cards que contêm **todos** os tokens",
        "erros": {},
    },
    ("GET", "/cinema/programme"): {
        "secao": "leitura",
        "descricao": "Programação de cinema do museu (seção da loja/vitrine; "
                     "módulo `cinema`).",
        "auth": "público",
        "resposta": "envelope com lista de sessões/filmes",
        "erros": {},
    },
    ("GET", "/store/products"): {
        "secao": "leitura",
        "descricao": "Produtos da loja (módulo `store`).",
        "auth": "público",
        "resposta": "envelope com lista de produtos",
        "erros": {},
    },
    ("GET", "/plans"): {
        "secao": "leitura",
        "descricao": "Planos de assinatura exibidos pelo site do museu.",
        "auth": "público",
        "resposta": "envelope com lista de planos",
        "erros": {},
    },
    ("POST", "/assistant/ask"): {
        "secao": "assistente",
        "descricao": "Pergunta em linguagem natural sobre o acervo (módulo "
                     "`assistant`). A resposta é **grounded**: o provedor de LLM "
                     "só recebe as fichas públicas recuperadas do índice de busca "
                     "e um system prompt que descreve os campos do card e proíbe "
                     "inventar além delas. Camadas anti-abuso, da mais barata à "
                     "mais cara: Turnstile (só com `MUSA_TURNSTILE_SECRET` "
                     "configurado), rate limit por IP (`MUSA_ASSISTANT_RPM`, "
                     "padrão 10/min), respostas prontas para saudações e visão "
                     "geral do acervo (custo zero), recusa de off-topic **sem "
                     "chamar o provedor**, cota diária de tokens por museu "
                     "(`MUSA_ASSISTANT_DAILY_TOKENS`, padrão 200 mil) e circuit "
                     "breaker de provedor (5 falhas seguidas abrem por 5 min). "
                     "Corpo: `{question, context?}`; o token do Turnstile vai em "
                     "`turnstile_token` ou `context.turnstile_token`. Cada ask é "
                     "logado (`assistant_ask`) com estimativa de custo e hash do "
                     "IP (nunca o IP cru). Sem provedor configurado "
                     "(`DEEPSEEK_API_KEY` ou `MUSA_LLM_FAKE=1`) → 503.",
        "auth": "público (rate-limited)",
        "resposta": '`{"answer": "…", "suggestedArtifacts": [{id, title}]}` — **sem envelope**',
        "erros": {
            "403": "verificação Turnstile falhou (quando configurada)",
            "404": "museu sem o módulo `assistant` — não vaza nem a existência",
            "422": "`question` vazia ou acima de 2000 caracteres",
            "429": "rate limit por IP **ou** cota diária de tokens esgotada (header `Retry-After`)",
            "503": "assistente não configurado, ou provedor fora do ar (circuit breaker aberto)",
        },
    },
    ("POST", "/auth/login"): {
        "secao": "escrita",
        "descricao": "Login do admin do tenant: o **token do tenant vai no campo "
                     "`password`**. Devolve o token e um perfil mínimo. Contas com "
                     "papéis/SSO chegam com o backend de escala (ADR 0008).",
        "auth": "corpo: `{email, password}`",
        "resposta": '`{"token": "…", "user": {email, name, role, org, note}}`',
        "erros": {
            "401": "credenciais inválidas",
            "503": "instância sem `MUSA_ADMIN_TOKEN` configurado",
        },
    },
    ("POST", "/collections"): {
        "secao": "escrita",
        "descricao": "Cria coleção. Corpo: `{id, title, description?, tier?, "
                     "cover?, website_status?}` — `id` é slug minúsculo; tier "
                     "padrão `bronze`. Coleção criada como draft responde "
                     "`visible: false` (existe, mas o público não vê).",
        "auth": "token (admin)",
        "resposta": "201 + envelope com a coleção criada",
        "erros": {
            "401": "sem token válido",
            "409": "coleção já existe — nunca sobrescreve",
            "422": "`id` fora do padrão de slug (`a-z`, `0-9`, `-`)",
            "503": "instância sem `MUSA_ADMIN_TOKEN`",
        },
    },
    ("POST", "/items"): {
        "secao": "escrita",
        "descricao": "**Patch** de card existente (`{asset_id, ...campos}`) ou "
                     "**criação** (card completo; nasce `draft` — publicar é um "
                     "patch explícito). Guardas (achados do M3.2): corpo de "
                     "criação (com `colecao`) para `asset_id` existente → 409; "
                     "`_rev` implementa concorrência otimista (patch com `_rev` "
                     "velho → 409); patch sem `_rev` é last-write-wins, por "
                     "desenho. Um escritor por vez (lock de escrita).",
        "auth": "token (admin)",
        "resposta": "200 + envelope com o card resultante",
        "erros": {
            "401": "sem token válido",
            "409": "create duplicado **ou** `_rev` estagnado — re-ler e reaplicar",
            "422": "slug inválido, coleção desconhecida ou card fora do contrato (mensagem aponta o campo)",
            "503": "instância sem `MUSA_ADMIN_TOKEN`",
        },
    },
    ("GET", "/assets/content/{collection}/{rest:path}"): {
        "secao": "assets",
        "descricao": "Binário de um asset (imagem, `.glb`, …). Somente assets de "
                     "registros **incluídos**: coleção excluída, dotfile, nome "
                     "reservado (`card.json`, …) ou fuga de diretório → 404. "
                     "`_skin/<arquivo>` serve os arquivos de skin da raiz do repo.",
        "auth": "público (gated)",
        "resposta": "o arquivo binário (`FileResponse`)",
        "erros": {"404": "asset inexistente ou bloqueado pelo portão"},
    },
}


def _discover_routes():
    """Instantiate the app on the fixture museum and read its routes."""
    import tempfile

    from .serve import create_app

    # data_dir in a throwaway dir: introspection must not leave a .musa/
    # overlay inside the fixture. The overlay SQLite must be closed before
    # cleanup or Windows refuses to delete it.
    tmp = tempfile.TemporaryDirectory()
    try:
        app = create_app(FIXTURE_REPO, data_dir=Path(tmp.name))
        routes = []
        for route in app.routes:
            if not isinstance(route, APIRoute) or route.path in _SKIP_PATHS:
                continue
            for method in sorted(route.methods):
                routes.append((method, route.path, route.endpoint))
        return routes
    finally:
        app.state.serve.store.close()
        tmp.cleanup()


def _query_params(path: str, endpoint) -> list[tuple[str, str, str]]:
    """(name, type, default) for signature params that are not path/body/request."""
    import re

    # Path params may carry a converter: "{rest:path}" is the param "rest".
    path_params = set(re.findall(r"\{([^}:]+)(?::[^}]*)?\}", path))
    params = []
    for name, p in inspect.signature(endpoint).parameters.items():
        if name in path_params or name in ("request", "response", "body"):
            continue
        tipo = getattr(p.annotation, "__name__", str(p.annotation))
        default = "(obrigatório)" if p.default is inspect.Parameter.empty else f"padrão `{p.default!r}`"
        params.append((name, tipo, default))
    return params


def _type_summary(prop: dict) -> str:
    if "enum" in prop:
        return "enum: " + ", ".join(f"`{v}`" for v in prop["enum"])
    if prop.get("type") == "array":
        items = prop.get("items", {})
        if "enum" in items:
            return "lista de enum: " + ", ".join(f"`{v}`" for v in items["enum"])
        return f"lista de {items.get('type', 'any')}"
    tipo = prop.get("type", "any")
    if prop.get("pattern"):
        tipo += f" · pattern `{prop['pattern']}`"
    return tipo


def generate() -> str:
    """Render docs/api-reference.md deterministically (no timestamps)."""
    routes = _discover_routes()
    discovered = {(m, p) for m, p, _ in routes}
    annotated = set(ANNOTATIONS)
    missing = discovered - annotated
    extra = annotated - discovered
    if missing or extra:
        raise RuntimeError(
            "API reference out of sync with the code — "
            f"endpoints sem anotação: {sorted(missing)}; "
            f"anotações sem endpoint: {sorted(extra)}. "
            "Atualize ANNOTATIONS em musa_build/api_reference.py."
        )

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    contract = schema.get("x-contract-version", "?")

    lines: list[str] = []
    add = lines.append
    add("# API reference — MUSA collection API (`musa_build serve`)")
    add("")
    add("> **Gerado automaticamente — não editar à mão.** Regenere com "
        "`cd builder && python -m musa_build api-reference` (a suíte de testes "
        "falha se este doc ficar velho em relação ao código). Conceitos, "
        "justificativas e o porquê das decisões: `docs/api-dinamica.md` e "
        "`docs/api-estatica.md`.")
    add("")
    add(f"Plataforma **v{__version__}** · contrato do card **v{contract}** "
        f"(`schemas/card/v1/card.schema.json`).")
    add("")
    add("## Convenções")
    add("")
    add("- **Envelope**: toda rota de dados responde `{ data, meta }` — "
        "`meta` carrega `contract`, `generated`, `museum` e `count` (listas). "
        "Exceções: `/health`, `/schema`, `/auth/login`, `/assistant/ask` e os "
        "binários de `/assets/…`. Detalhes em `docs/api-estatica.md`."
        )
    add("- **Auth**: escritas e visão de rascunhos exigem "
        "`Authorization: Bearer <MUSA_ADMIN_TOKEN>`. Sem token configurado a "
        "instância é read-only e escritas respondem 503.")
    add("- **Portão (gate)**: registros `draft` ou acima do tier do museu são "
        "404 para o público — não vazam nem a existência.")
    add("- **Erros**: corpo `{ \"detail\": \"…\" }` (FastAPI). Tabela completa "
        "por endpoint abaixo; resumo:")
    add("")
    add("  | Código | Significado |")
    add("  |---|---|")
    add("  | 401 | token ausente/inválido em rota protegida |")
    add("  | 403 | verificação anti-robô (Turnstile) falhou |")
    add("  | 404 | recurso inexistente **ou** excluído pelo portão |")
    add("  | 409 | conflito: duplicado ou `_rev` estagnado |")
    add("  | 422 | validação (slug, coleção, contrato) — a mensagem aponta o campo |")
    add("  | 429 | rate limit ou cota diária do assistente (header `Retry-After`) |")
    add("  | 503 | instância sem `MUSA_ADMIN_TOKEN` (writes disabled) ou assistente indisponível |")
    add("")

    secao_titulo = {"ops": "Ops", "leitura": "Leitura (pública)",
                    "assistente": "Assistente (M4.2)",
                    "escrita": "Escrita (admin)", "assets": "Assets (binários)"}
    for secao in ("ops", "leitura", "assistente", "escrita", "assets"):
        group = [(m, p, e) for m, p, e in routes
                 if ANNOTATIONS[(m, p)]["secao"] == secao]
        if not group:
            continue
        add(f"## {secao_titulo[secao]}")
        add("")
        for method, path, endpoint in group:
            ann = ANNOTATIONS[(method, path)]
            add(f"### `{method} {path}`")
            add("")
            add(ann["descricao"])
            add("")
            add(f"- **Auth**: {ann['auth']}")
            for name, tipo, default in _query_params(path, endpoint):
                add(f"- **Query** `{name}` ({tipo}, {default})")
            add(f"- **Resposta**: {ann['resposta']}")
            if ann["erros"]:
                add("- **Erros**:")
                for code, meaning in ann["erros"].items():
                    add(f"  - `{code}` — {meaning}")
            add("")

    add("## Contrato do card (campos)")
    add("")
    add(f"Fonte: `builder/musa_build/schemas/card.schema.json` "
        f"(v{contract}). Obrigatórios: "
        + ", ".join(f"`{r}`" for r in schema["required"]) + ".")
    add("")
    add("| Campo | Tipo | Descrição (verbatim do contrato) |")
    add("|---|---|---|")
    for name, prop in schema["properties"].items():
        req = " **(obrigatório)**" if name in schema["required"] else ""
        desc = prop.get("description", "").replace("|", "\\|").replace("\n", " ")
        add(f"| `{name}`{req} | {_type_summary(prop)} | {desc} |")
    add("")
    add("Regra condicional: se `model_status` é `available`, `model_primary` "
        "passa a ser obrigatório (`allOf` do schema). Campos extras são "
        "permitidos (`additionalProperties: true`).")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="musa-build api-reference",
        description="Generate the HTTP API reference doc from the code.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="output path (default: docs/api-reference.md)")
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit 1 if the doc on disk is stale")
    args = parser.parse_args(argv)

    rendered = generate()
    out = Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current.replace("\r\n", "\n") != rendered:
            print(f"STALE: {out} — rode `python -m musa_build api-reference`")
            return 1
        print(f"api-reference OK — {out} está em sincronia com o código")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"api-reference written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
