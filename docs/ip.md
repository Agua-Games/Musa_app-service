# Documento de IP — o que é de quem no MUSA

> **Documento interno e sensível (2026-10-17).** Base do §4 da minuta de
> contrato (`docs/contrato-servico.md`) e do data room de uma futura rodada
> de investimento. Manter privado junto com este repositório.
> Não substitui revisão de assessoria jurídica — pontos abertos no checklist
> final.

## 1. Princípio arquitetônico (e comercial)

**O motor é nosso; o acervo é do museu; o formato é aberto.**

A separação não é só ética — é a tese de defesa do negócio: a Plataforma
detém o software (difícil de replicar: gate de contrato, entitlements
assinados, pipeline, bateria de testes), o cliente detém o conteúdo
(inalienável, é o patrimônio dele), e o esquema de card é público de
propósito (portabilidade vira argumento de venda, não risco — o cliente
fica porque o serviço é bom, não porque está trancado).

## 2. Da PLATAFORMA (Agua-Games / empresa MUSA a constituir)

| Ativo | Natureza | Observações |
|---|---|---|
| Código-fonte: `builder/`, `pipeline/`, `mcp_server/`, `beta/`, `tools/`, workflows de CI | Direito autoral de software | Todo o histórico de commits é do dono do estúdio (ver §5 sobre assistência de IA) |
| Frontend: `source/` (layout, CSS, JS, design da landing, viewers 3D integrados) | Direito autoral + design | Usa three.js MIT vendored (§4) |
| Documentação técnica, ADRs, runbooks, planos de milestone | Direito autoral | Vivos no repo |
| Nome e marca "MUSA", identidade visual | Marca | **Não registrada — [A DEFINIR: INPI]** |
| Mecanismo de entitlements Ed25519 + política de tiers/módulos | Know-how / segredo de negócio | A chave privada da plataforma é o ativo crítico (ver §6) |
| Tabela de preços e estratégia comercial (`plans.json`, `M4_custos.md`) | Segredo de negócio | Sensível: nunca em repo de cliente |
| Melhorias genéricas da aplicação decorrentes de demandas de clientes | Plataforma | Cláusula correspondente no contrato de serviço §4 |

## 3. Do CLIENTE (cada museu)

| Ativo | Natureza | Observações |
|---|---|---|
| Acervo Digital (fichas, fotos, modelos 3D, textos, traduções) | Direito autoral / patrimônio institucional do museu | Repositório Git titulado pelo cliente; formato aberto `schemas/card/v1` |
| Marca, nome e identidade visual do museu | Marca do cliente | Skin e logo entram via `museum.config.json` |
| Adaptações de conteúdo feitas pela Plataforma a pedido | [A DEFINIR: cessão integral ao cliente vs. licença] | Pendente na minuta de contrato §4 |
| Direitos sobre as obras retratadas | Museu ou terceiros | Cliente declara titularidade ao cadastrar; campos `licenca`/`fonte` (contrato 1.2.0) exibem a proveniência publicamente |

## 4. De TERCEIROS (componentes incorporados — inventário de licenças)

| Componente | Onde | Licença | Compatível? |
|---|---|---|---|
| three.js (vendored em `source/assets/vendor/three/`) | viewers 3D | MIT | Sim — manter o cabeçalho de licença no bundle |
| Fontes Cormorant Garamond + Inter (Google Fonts) | landing | SIL OFL | Sim — uso web livre, sem atribuição obrigatória |
| Modelos demo: `lantern.glb`, `samurai-helmet.glb`, `antique-corset.glb` | `source/assets/models/` | Khronos glTF-Sample-Assets — **verificar licença por modelo** (alguns são CC-BY: exigem crédito) | [A DEFINIR: confirmar e registrar créditos] |
| `venus-de-milo.glb` | idem | CC0 (scan, National Gallery of Denmark, via Sketchfab) | Sim — **mas a URL de origem não está registrada**; pendência aberta no HANDOFF §riscos (o arquivo existe só localmente) |
| Pinturas demo (DemoMuseum) | R2 | Domínio público / Wikimedia Commons | Sim — 455 cards com `licenca`+`fonte` preenchidos (M4.6) |
| Met Open Access (450 fichas sintéticas) | corpus de teste | CC0 | Sim |
| DeepSeek (API de IA) | assistente + pipeline M2 | Termos do provedor; processamento remoto on-demand | Não gera IP nosso; registrar DPA/termos (pendente em `lgpd.md`) |
| Dependências Python do build (`builder/pyproject.toml`) | artefato | verificar na 1ª auditoria de licenças | [A DEFINIR: rodar `pip-licenses` e arquivar] |

## 5. Contribuições e autoria

5.1. **Autoria dos commits:** todo o histórico git é de autoria do dono do
estúdio (commits assinados por ele). O desenvolvimento usou **assistentes
de IA** (Kimi, DeepSeek) sob direção, revisão e integração humana —
equiparável a ferramenta de autoria; a jurisprudência sobre código gerado
por IA ainda é instável, então a documentação desta cadeia (prompts,
revisões, commits humanos) é a evidência de titularidade. [A DEFINIR com
assessoria: termo interno formalizando essa política.]

5.2. **Novos membros da equipe (a partir de agora):** todo colaborador —
CLT, PJ ou freelancer — assina **termo de cessão de IP e confidencialidade
antes do primeiro commit**. Sem exceção: é o que sustenta a coluna
"Plataforma" do §2 numa due diligence. [A DEFINIR: minuta do termo.]

5.3. **Código de cliente:** clientes não contribuem código para a
plataforma; contribuições de conteúdo seguem o §3.

## 6. Segredos de negócio e custódia

| Segredo | Onde vive | Risco se vazar | Mitigação |
|---|---|---|---|
| Chave privada Ed25519 da plataforma | `H:\Musa_app-service\secrets\` (fora de qualquer repo) | Forjar upgrades de tier de graça | Backup offline criptografado; rotação documentada; [A DEFINIR: HSM/KMS na produção] |
| Tabela de custos e margens (`M4_custos.md`) | este repo (privado) | Barganha comercial enfraquecida | Repo privado; acesso mínimo |
| Credenciais R2/tokens | secrets do GitHub + local criptografado | Uso indevido do bucket | Rotacionar o secret R2 exposto no chat em 2026-10-07 — **pendente do dono** |

## 7. Decisões de abertura (o que é público de propósito)

- **Esquema do card** (`schemas/card/v1` + `COMPATIBILITY.md`): público,
  viaja nos repos dos clientes. É a garantia de portabilidade do §7 do
  contrato — abrir o formato fortalece a venda e não entrega o motor.
- **API reference** (`docs/api-reference.md`): pública, necessária para
  integrações de clientes.
- **O que NUNCA abrir:** builder/serve/pipeline (o motor), preços,
  documentos comerciais, este documento.

---

### Checklist de pendências

- [ ] Registrar a marca "MUSA" (INPI) — §2.
- [ ] Confirmar licença por modelo dos 3 GLBs Khronos e registrar créditos
      se CC-BY — §4.
- [ ] Registrar a URL de origem do `venus-de-milo.glb` em
      `tools/fetch_models.py` (pendência já listada no HANDOFF §riscos) — §4.
- [ ] Rodar `pip-licenses` no builder e arquivar o inventário — §4.
- [ ] Minuta de termo de cessão de IP + confidencialidade para novos
      membros — §5.2.
- [ ] Termo interno sobre uso de assistentes de IA — §5.1.
- [ ] Confirmar DPAs/termos dos suboperadores (espelha `lgpd.md`) — §4.
- [ ] Definir cessão vs. licença das adaptações a pedido do cliente — §3
      (resolve o [A DEFINIR] correspondente no contrato de serviço).
