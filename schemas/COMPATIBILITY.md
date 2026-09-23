# Contrato do acervo — política de compatibilidade (v1)

> O contrato é a fonte única de verdade da camada de acervo
> (`schemas/ficha.schema.json`, ADR 0001). Este documento define o que pode mudar
> **sem** quebrar um cliente que já publica com a v1, e o que exige uma v2.

Versão atual: **1.0.0** — congelada em 2026-09-23 (milestone M0, entregável 1).
A versão viaja no próprio schema, em dois lugares que devem concordar:

- `$id`: `…/schemas/ficha/v1/ficha.schema.json` — o **major** (`v1`) está no caminho;
- `x-contract-version`: `1.0.0` — a versão completa, lida pelo builder.

## O que é mudança compatível (sobe o *minor* ou o *patch*, continua `v1`)

Uma ficha que validava **continua validando**, e um consumer que lia a v1 continua
conseguindo ler. São compatíveis:

- **adicionar campo opcional** novo (o schema permite `additionalProperties: true`;
  documentar o campo novo em `properties` é *minor*);
- adicionar valor novo a um `enum` **opcional** (ex.: novo formato em
  `model_formats`, novo viewer em `model_viewer`);
- afrouxar uma restrição (aumentar `minLength` nunca; **diminuir** restrições é
  compatível: ex. aceitar mais padrões em `data`);
- melhorar `description`, exemplos e notas — *patch*.

## O que exige v2 (novo `$id`, nova pasta `schemas/ficha/v2/`)

- remover ou renomear campo;
- transformar campo opcional em **obrigatório**;
- restringir um tipo ou enum existente (ex.: remover valor de `model_status`);
- mudar a semântica de um campo mantendo o nome.

## Regras de operação

1. **A v1 não é editada de forma incompatível — nunca.** Mudança incompatível é
   arquivo novo em `schemas/ficha/v2/`, com o builder passando a aceitar as duas.
2. Todo cliente fixa a versão do **artefato** em `museum.config.json` (`musa`), e o
   artefato declara qual versão do contrato ele valida. Um builder que encontra uma
   ficha v2 sem suportá-la **falha o build** — nunca ignora.
3. Uma ficha que não valida não entra no índice nem no payload (invariante §5.1 do
   HANDOFF). O portão roda no build, dentro do artefato publicado (M0.5).
4. Versões de documento sobem em arquivo preservando o anterior (convenção §6 do
   HANDOFF) — o mesmo vale para o contrato.
