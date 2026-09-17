# 🚀 MUSA — Onboarding de um cliente (museu)

> Processo operacional. A decisão de arquitetura que sustenta este processo está em
> `docs/adr/0003-onboarding-de-clientes.md`. Documento de implementação do produto:
> `docs/Musa_design implementacao-usd.md`.

O objetivo é que criar o site de um museu seja **um comando para o repo, um comando para o build**,
e que o trabalho humano fique onde ele tem valor: escanear, modelar e conferir metadados.

---

## 1. O que o cliente recebe

| Item | Onde vive |
|---|---|
| Site publicado | CDN / host estático, domínio do museu |
| Repo de conteúdo | `Agua-Games/museum-‹slug›` (privado), gerado do template |
| Assets pesados (GLB, USD, imagens originais) | object storage (bucket por cliente) + backup local opcional |
| Conteúdo vivo (edições de curadoria) | banco + índice |
| Componente on-premise (opcional) | nó de backup local, quiosque, pipeline de digitalização |

---

## 2. Anatomia do repo do cliente

**Sem código do MUSA.** Conteúdo, configuração e o workflow de build:

```
museum-‹slug›/
├── museum.config.json          # identidade + versão do MUSA + entitlements (do servidor)
├── content/
│   ├── colecao_‹id›/
│   │   ├── collection.json     # metadados da coleção
│   │   └── ‹peca›/
│   │       ├── ficha.json      # conforme schemas/ficha.schema.json
│   │       └── images/         # imagens de apresentação (2D)
│   └── ...
├── .github/workflows/deploy.yml
└── README.md                   # específico do cliente: contatos, domínio, tier
```

**Regra:** se é binário grande (`.glb`, `.usd`, `.jpg` de alta resolução), vai para o bucket e a
`ficha.json` referencia por URL (`model_primary`, `model_source`). O repo carrega texto.

---

## 3. `museum.config.json`

```json
{
  "museum": {
    "id": "museu-nacional",
    "name": "Museu Nacional",
    "locale": "pt-BR",
    "domain": "acervo.museunacional.org"
  },
  "musa": "1.4.2",
  "entitlements": {
    "source": "https://api.musa.example/v1/entitlements/museu-nacional",
    "tier": "silver",
    "modules": ["assistant"],
    "issued": "2026-09-17",
    "signature": "<emitida pelo servidor MUSA>"
  },
  "storage": {
    "assetsBaseUrl": "https://assets.musa.example/museu-nacional/"
  }
}
```

- `musa` é uma **versão fixada**, não `latest`. É isso que torna a atualização um passo explícito e
  reversível.
- `entitlements` é obtido do servidor (ou verificado por assinatura, no modo offline). **O cliente
  nunca edita o próprio tier** — ver ADR 0003.

---

## 4. Passo a passo

### Passo 1 — Criar o repo do cliente

```bash
gh repo create Agua-Games/museum-museu-nacional \
  --template Agua-Games/musa-museum-template \
  --private \
  --clone
```

O repo nasce com um commit novo e sem parentesco com o template: não há merge upstream possível.

### Passo 2 — Importar o acervo inicial (o *seed*)

1. Pipeline de OCR/IA gera as fichas
   (`docs/Musa_design implementacao-usd.md` §5).
2. As fichas são **validadas contra o contrato** antes de entrar:
   ```bash
   python tools/validate_catalog.py   # falha o build se algo não validar
   ```
3. Commit do `content/` no repo do cliente. Este é o marco auditável do acervo inicial.

### Passo 3 — Subir os assets pesados

Modelos 3D e imagens de alta resolução vão para o bucket do cliente:

```
s3://musa-assets/museu-nacional/
  ├── assets/‹asset_id›/model.glb
  ├── assets/‹asset_id›/source.usd
  └── assets/‹asset_id›/images/front.jpg
```

A `ficha.json` aponta para eles; o repo não carrega o binário.

### Passo 4 — Build e publicação

```bash
gh workflow run deploy.yml     # ou push em main
```

O workflow do cliente executa o builder da versão fixada:

1. obtém o `@musa/app@<versão fixada>` (ou a imagem de container);
2. obtém/verifica os entitlements;
3. valida as fichas contra `schemas/ficha.schema.json`;
4. **filtra por tier e por `website_status`** — o que não foi publicado nem contratado não entra no
   site;
5. emite o site estático e publica no CDN.

### Passo 5 — Domínio e go-live

Apontar o domínio, emitir TLS, rodar o checklist da seção 7.

---

## 5. Rotina de curadoria (do cliente)

O curador entra no admin e edita: publica, despublica, promove peça a *hero*, ajusta texto, sobe
nova imagem.

- As edições vão para **banco + object storage**, não para o git.
- Um rebuild (agendado ou por botão "publicar") materializa a mudança no site.
- Um *snapshot* periódico pode ser comitado no repo como export/backup — é o que sustenta a
  promessa de preservação e de portabilidade do acervo.

**Não há trabalho da equipe MUSA nesta rotina.** É o ponto central do desenho.

---

## 6. Atualizar o MUSA em um cliente

```bash
cd museum-museu-nacional
# alterar "musa" em museum.config.json
git commit -am "chore: bump MUSA to 1.5.0"
git push                        # o CI valida e publica
```

Nada de merge, nada de copiar DLL. Se a nova versão quebrar o contrato, **a validação falha antes
do deploy** e o site continua na versão anterior.

---

## 7. Checklist de go-live

- [ ] Fichas validadas contra `schemas/ficha.schema.json` (zero violações)
- [ ] **Nenhum item `draft` no payload publicado** (hoje é um defeito conhecido: o filtro é
      client-side — ver ADR 0003)
- [ ] Nenhum conteúdo de tier acima do contratado no payload
- [ ] Entitlements emitidos pelo servidor e conferidos no build
- [ ] Assets pesados no bucket, repo sem binário grande
- [ ] Backup local configurado (se contratado no tier)
- [ ] Domínio + TLS + redirecionamento
- [ ] Acessos de admin criados para o cliente; conta MUSA separada
- [ ] Termos de uso, créditos de licença de imagem e política de privacidade publicados

---

## 8. O que permanece manual (o serviço em si)

| Atividade | Por que é manual |
|---|---|
| Escaneamento 3D das peças | hardware + operador |
| Modelagem, *touch-up* e otimização | julgamento artístico/técnico |
| Autoridade dos metadados (autor, data, material) | curadoria e conferência |
| Digital twin de ala | produção complexa, por projeto |
| Revisão de respostas do assistente em acervo novo | qualidade e risco institucional |

---

## 9. Pendências do processo

- Extrair `Agua-Games/musa-museum-template` a partir de `source/` (hoje o demo e o template são a
  mesma coisa).
- Mover o gating de `website_status` e de tier do cliente (`main.js`) para o build.
- Mover `tools/validate_catalog.py` para dentro do artefato publicado do MUSA — o portão deve
  viajar com o produto.
- Definir o endpoint de entitlements e o formato do token de deploy.
