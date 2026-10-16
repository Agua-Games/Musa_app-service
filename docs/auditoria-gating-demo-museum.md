# Auditoria de gating — demo-museum

> Gerado por `musa-build audit` em 2026-10-16 · plataforma v0.4.0 · contrato do card v1.1.0. Documento gerado por teste automatizado — não editado à mão.

## O que este relatório prova

O museu **demo-museum** tem contrato de tier **gold**. O portão de conteúdo (a regra que separa o que o público pode ver) foi testado de verdade, sonda a sonda, contra a API real:

- **Rascunhos** (143): nenhum aparece no site público — nem o cadastro (JSON), nem as imagens/modelos 3D, nem na busca.
- **Acima do tier** (0 item(ns) e 0 coleção(ões)): invisíveis para o público **e continuam invisíveis até com o token de administrador** — o tier contratado nunca relaxa.
  - _Nenhum registro acima do tier existe neste acervo (esperado no gold, o tier máximo): esta verificação é vacuamente verdadeira aqui. O caminho é exercido de verdade na suíte da plataforma (`builder/tests/test_audit.py`, fixture silver com registro gold)._
- **Controle positivo**: com o token de administrador os rascunhos aparecem — ou seja, os 404 do público são decisão do portão, não dado faltando.
- **Contrato**: todo item público é válido pelo contrato congelado do card.

## Resultado: **APROVADO** ✔

6 verificações, 1071 sondas HTTP no total.

| Verificação | Sondas | Resultado |
|---|---|---|
| Todo item público é válido pelo contrato do card | 321 | ✔ |
| Nenhum rascunho aparece no público (JSON e arquivos) | 143 | ✔ |
| Nada acima do tier contratado (gold) vaza | 0 | ✔ |
| Controle positivo: admin vê rascunhos; tier nunca relaxa | 143 | ✔ |
| A busca pública não devolve registros excluídos | 143 | ✔ |
| Descritores internos (card.json) e dotfiles não são baixáveis | 321 | ✔ |

## Detalhes por verificação

### Todo item público é válido pelo contrato do card

321 item(ns) público(s) validados um a um.

### Nenhum rascunho aparece no público (JSON e arquivos)

143 rascunho(s), cada um sondado no JSON e em cada arquivo local.

### Nada acima do tier contratado (gold) vaza

0 item(ns) e 0 coleção(ões) acima do tier, sondados em JSON e arquivos.

### Controle positivo: admin vê rascunhos; tier nunca relaxa

cada rascunho re-sondado com token (deve aparecer) e cada registro acima do tier re-sondado com token (deve sumir mesmo assim).

### A busca pública não devolve registros excluídos

cada registro excluído pesquisado pelo token mais distintivo do título.

### Descritores internos (card.json) e dotfiles não são baixáveis

card.json de cada item público com diretório próprio, sondado.

## Inventário

- Itens no repositório: 464
- Públicos (publicados e dentro do tier): 321
- Rascunhos (excluídos do público): 143
- Acima do tier gold (excluídos do público): 0 item(ns), 0 coleção(ões)

## Como reproduzir

```bash
cd builder && python -m musa_build audit --repo <repositório do museu> --out auditoria.md
```
