# Entitlements assinados (M1.2, ADR 0010)

> Como tier e módulos chegam ao build de um cliente sem que ele possa se
> auto-promover — e sem nenhum servidor online.

## O mecanismo em uma página

1. **A plataforma tem um par de chaves Ed25519.** A privada vive fora de
   qualquer repositório (hoje: `H:\Musa_app-service\secrets\musa-entitlements-ed25519.key`
   na máquina do dono — um secret como o `GHCR_PULL_TOKEN`). A pública vai
   **embarcada na imagem** (`builder/musa_build/data/entitlements-public.key`) —
   o cliente não a controla porque não controla a imagem (ADR 0006).
2. **Assinar = aprovar.** `tools/sign_entitlements.py sign --repo <cliente> --key <privada>`
   lê `tier`/`modules` do `museum.config.json` (o arquivo é o *pedido*), carimba
   `museum_id`, `issued`, `expires` e grava a `signature`. Rodado por nós a cada
   onboarding ou mudança de tier.
3. **O build verifica.** Imagens de release (qualquer pin que não
   `0.0.0-unreleased`) **falham o build** se a assinatura faltar, não conferir,
   estiver expirada, ou se o `museum_id` não for o do museu. O pin de
   desenvolvimento aceita config não assinado com *warning* — é o modo de
   iterar localmente.

## O que a assinatura cobre

Os bytes assinados são o JSON canônico (chaves ordenadas, sem espaços, UTF-8)
de exatamente cinco campos:

```json
{"expires":"2027-09-25","issued":"2026-09-25","modules":["assistant","..."],"museum_id":"demo-museum","tier":"gold"}
```

`modules` é ordenada antes de assinar. Campos fora da assinatura: `source`
(anotação de onde o endpoint online vai servir o mesmo payload, na fase 2 com o
backend do M1.4) e a própria `signature`.

## Operação

| Tarefa | Como |
|---|---|
| Onboarding de cliente novo | editar `tier`/`modules` no config dele → rodar `sign` → commit |
| Mudança de tier/módulo | idem — a assinatura anterior morre com qualquer edição |
| Expiração | o build falha na data; re-assinar (renova) sem trocar chave |
| Troca de chave (rotação/comprometimento) | novo par → pública entra na próxima release da imagem → **re-assinar todos os clientes** (operação manual e rara) |
| Perda da chave privada | mesma coisa que rotação — por isso ela tem backup fora do repo |

## Prova falsificável (critério de saída da fase)

Adulterar o `museum.config.json` do DemoMuseum (ex.: adicionar um módulo
mantendo a assinatura) **falha o build** com:

```
museum.config.json: entitlements.signature does not verify — the block was
edited after the platform signed it (tier/modules cannot be changed client-side)
```

Coberto por `builder/tests/test_entitlements.py` (11 testes: assinatura válida,
tier adulterado, módulo adicionado, assinatura ausente, museu errado, expirado,
canonicalização, e os quatro cenários end-to-end no build).

## Token de deploy por cliente (preparação M3/M4)

Não implementado nesta fase — o deploy atual é Pages via Actions, autenticado
pelo próprio GitHub. Quando houver deploy fora do Pages (App Service, M3+), o
formato previsto é um token por cliente com escopo `{museum_id, ações}` emitido
pela mesma ferramenta e verificado pelo backend — o endpoint online de
entitlements (fase 2) é quem o emite e revoga. Até lá, a assinatura offline
cobre o único ponto de enforce que existe: o build.
