# ADR 0008 — Backend do acervo no M1: API própria mínima (FastAPI), Payload adiado

- **Status:** aceita
- **Data:** 2026-09-24
- **Relacionada:** ADR 0001 (camada de acervo), ADR 0003 (onboarding), ADR 0006 (artefato)

## Contexto

O M1 precisa de uma API de acervo real (`/collections`, `/items/{id}`, `/search`,
`/schema` — spec §6.1) para tirar o frontend do mock e sustentar o admin mínimo (M1.4).
A ADR 0001 já fixou a estratégia por estágios: **MVP = índice em build-time; escala =
Payload (TS/Postgres)**. A pergunta que esta ADR responde é: o M1 entra direto no
Payload, ou há um estágio intermediário que vale a pena?

O que pesa:

1. **O builder já é Python e já serve o contrato.** A imagem `musa-app` valida fichas,
   aplica gating e emite o site. Uma API mínima em **FastAPI** reutiliza o mesmo código
   de contrato/gating e a mesma estratégia de artefato (ADR 0006) — um `serve` ao lado do
   `build`, na mesma imagem ou em imagem irmã.
2. **Payload é um CMS inteiro** (Node + Postgres + admin). Em M1.4 o admin mínimo pode
   revelar necessidade de CMS (revisão, histórico, usuários) — mas trazer isso antes da
   primeira operação real é pagar o custo (dois runtimes, banco, migração) antes de medir
   a necessidade.
3. **A API é estável por desenho (ADR 0001).** Se o frontend fala `/collections` e
   `/items/{id}` com os shapes do contrato, trocar FastAPI por Payload depois é trocar a
   implementação, não o contrato — nenhum código de view muda.

## Decisão proposta

1. **M1 usa API própria mínima em FastAPI**, distribuída na mesma linha de artefato do
   builder (imagem `musa-app`, comando `serve`), servindo:
   - leitura: `/collections`, `/collections/{id}/items`, `/items/{id}`, `/search`,
     `/schema` — com o **mesmo gating do build** (nada `draft`, nada acima do tier);
   - escrita (M1.4): criar coleção/item, publicar/despublicar, promover hero — atrás de
     token por tenant.
2. **Antes da API dinâmica, o modo estático:** o builder emite a mesma API em JSON
   (`api/collections.json`, `api/items/<id>.json`, …) — o frontend liga o modo `live`
   contra os JSONs primeiro, e contra o FastAPI depois, sem mudança de view.
3. **Payload permanece a escolha de escala** (ADR 0001): entra quando o admin exigir CMS
   de verdade (revisão, histórico, papéis) — reavaliar no fim do M1.4 com evidência, não
   antes.
4. **Fonte de verdade em M1:** o repo do cliente (seed) + banco leve da API para as
   edições do dia a dia (SQLite por instância basta no multi-deploy; Postgres quando
   virar multi-tenant).

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Payload desde o M1** | Dois runtimes (Python do builder + Node do CMS), Postgres e migrações antes da primeira operação real; o admin mínimo ainda não provou precisar de CMS |
| **Supabase / Firebase** | Backend-as-a-service amarra auth, banco e storage a um fornecedor; o contrato é nosso e o gating precisa rodar no nosso build |
| **Só API estática, sem FastAPI** | Não sustenta escrita (admin mínimo, M1.4) nem entitlements online (M1.2 fase 2) |
| **Express (Node) em vez de FastAPI** | Duplica o código de contrato/gating em outra linguagem; o builder é Python |

## Consequências

- Um runtime só no M1 (Python), um pipeline de artefato só (ADR 0006).
- O gating roda em três lugares com o mesmo código: build, API estática, API dinâmica.
- A migração para Payload, quando vier, é de implementação — o contrato e os shapes de
  resposta documentados na spec §6.1 não mudam.
- Risco aceito: se o admin mínimo revelar necessidade de CMS cedo, o FastAPI vira
  descartável — mitigado por ele ser pequeno por desenho (leitura + 4 escritas).
