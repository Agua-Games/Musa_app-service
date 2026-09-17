# ADR 0003 — Onboarding de clientes e topologia de entrega

- **Status:** aceita
- **Data:** 2026-09-17
- **Relacionada:** ADR 0001 (camada de acervo), ADR 0002 (tooling de desenvolvimento)

## Contexto

Com o frontend funcional (ver `source/`), surgiu a primeira pergunta de **processo**: como
entregar um site novo para um museu cliente, de forma repetível e com manutenção mínima.

A proposta inicial era:

1. a equipe MUSA clona um repo-template ("Demo Museum") para um repo novo, com o MUSA dentro
   como *third-party library*;
2. o repo do cliente contém apenas assets em pastas dedicadas + `config.json`/`.toml` com os
   módulos ativados;
3. compila-se o repo clonado;
4. o admin do museu (ou a equipe) entra no frontend, cria coleções e sobe imagens; o app **cria a
   pasta dedicada no repo** e grava ali;
5. o MUSA chega aos clientes como **binários compilados (`.exe` + DLLs)**, de modo que atualizações
   se propaguem para os repos dos clientes.

A espinha dessa proposta está certa: repo por cliente com **só conteúdo e configuração**, gerado
de um template. Mas três elementos dela são incompatíveis com os objetivos do produto.

### Por que `.exe` + DLLs copiados para repos de clientes não funciona

- Um site é servido por um host, quase sempre Linux. Publicar o frontend como `.exe` elimina CDN,
  containers e escala horizontal.
- Conceitualmente, **copiar o produto para dentro de N repos não propaga atualização, propaga
  divergência**. Cada repo de cliente vira uma ramificação do produto: N versões em produção, merge
  manual de cada atualização, e nenhum rollback atômico.

### Por que o admin não deve escrever no repo

- Exige credencial de git no processo da aplicação.
- Dois curadores editando ao mesmo tempo produzem conflito de merge — um sistema de controle de
  versão sendo usado como CMS.
- Upload de imagens e modelos **devolve binário para o git**: exatamente os 26 MB de GLB que foram
  retirados do histórico em 2026-09-17 (ver ADR 0002 e o `.gitignore`).

### Por que o `config.json` do cliente não pode definir o tier

Tier é receita: se o que define o tier é um arquivo que o cliente possui, ele habilita o Gold
editando uma linha.

E o gating precisa ocorrer **onde o conteúdo é servido**. Isso já é um defeito verificável hoje:

```
source/data/catalog.json  →  14 itens, dos quais 1 com website_status = "draft"
main.js                   →  filtra "published" no cliente
```

Numa build estática, filtrar no cliente equivale a não filtrar: o `draft` está no payload e basta
abrir o devtools. Pelo mesmo motivo, um cliente Bronze não pode receber os dados do Gold: se
receber, tem o produto sem pagar.

## Decisão

**Inverter a direção: o MUSA puxa o conteúdo do cliente; o produto não é copiado para o cliente.**

1. **MUSA é um artefato versionado.** Publicado como pacote (`@musa/app@<versão>`), imagem de
   container ou bundle estático. O repo do cliente **fixa uma versão** e não contém código do MUSA.
2. **Repo do cliente = conteúdo + configuração + CI.** Gerado de um **template** do GitHub, que
   nasce com um commit novo e **sem parentesco de histórico** — não existe, nem por acidente, merge
   upstream.
3. **Runtime não escreve em git.** Uploads de curadoria vão para object storage + banco. O repo
   guarda o **seed** (o acervo inicial importado, auditável) e, opcionalmente, *snapshots*
   periódicos como export/backup.
4. **Entitlements vêm do servidor MUSA, não do cliente.** O build obtém tier e módulos da API do
   MUSA com um token de deploy; para instalações offline/on-premise, um arquivo **assinado** pelo
   servidor, verificado com chave pública embarcada na plataforma.
5. **Gating acontece no build e na borda.** O site de um cliente só é gerado com o conteúdo que
   ele contratou e publicou. Conteúdo servido por API/RAG exige token por tenant.
6. **Topologia por fase:** multi-deploy (uma build por cliente) até o custo de operação doer —
   tipicamente ~10 clientes —, migrando então para multi-tenant, com os repos de conteúdo
   continuando a ser a fonte.
7. **Binário compilado é para componente on-premise**, não para o site: nó de backup local na
   máquina do museu, quiosque físico, pipeline de digitalização na rede local. Preferir container a
   `.exe` por portabilidade, reservando o executável nativo para onde o cliente exige instalação
   Windows.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| MUSA copiado/forkado em cada repo de cliente | N ramificações do produto: atualização vira merge manual em N repos, sem rollback atômico |
| Distribuir o site como `.exe` + DLLs | Amarra a entrega a Windows; perde CDN, containers e escala horizontal |
| Admin versionando conteúdo direto no git | Credencial de git no app, conflito entre curadores, binário de volta ao histórico |
| `config.json` do cliente definindo o tier | Vazamento de receita: o cliente se promove editando um arquivo |
| Multi-tenant desde o primeiro cliente | Custo de engenharia antes de existir volume; atrasa o primeiro contrato |
| Manter tudo estático e filtrar no cliente | O payload contém o que não foi publicado nem contratado (defeito atual) |

## Consequências

**Positivas**

- Atualizar 40 clientes é subir um número de versão e reconstruir — sem merge, sem divergência.
  Com runtime compartilhado, a atualização é instantânea para todos.
- O repo do cliente é pequeno e legível: conteúdo e configuração, sem código.
- O conteúdo do cliente permanece **portável**: um museu pode levar seu acervo embora, o que
  fortalece a promessa de preservação e reduz a objeção de aprisionamento.
- O gating deixa de ser cosmético e passa a ser verificável no build.

**Negativas / riscos**

- Exige versionamento disciplinado: uma versão quebrada do MUSA quebra N builds no próximo
  *bump*. Mitigação: o validador de contrato roda no build do cliente e falha antes do deploy.
- Multi-deploy tem custo de operação linear no número de clientes; a migração para multi-tenant
  precisa ser planejada, não descoberta.
- Entitlements assinados adicionam um passo de chave pública na plataforma e um processo de
  emissão no lado do serviço.

## Pendências

- Verificar no build estático que `website_status = draft` **não** chega ao payload (hoje chega).
- Definir o formato do token de deploy e o endpoint de entitlements.
- Decidir o gatilho concreto da migração para multi-tenant (nº de clientes, custo, ou requisito
  de latência).
- Escolher onde rodam os componentes on-premise e qual o artefato (container × executável).

## Referências

- `docs/Musa_design onboarding.md` — o processo operacional passo a passo
- `docs/adr/0001-camada-de-acervo.md` — contrato da camada de acervo
- `docs/adr/0002-tooling-de-desenvolvimento.md` — política de repositório e binários
- `source/README.md` — estado atual do frontend e a camada `MusaAPI`
