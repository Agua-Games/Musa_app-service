# ADR 0010 — Entitlements: arquivo assinado offline (Ed25519), endpoint online depois

- **Status:** proposta — aguardando aprovação do dono
- **Data:** 2026-09-24
- **Relacionada:** ADR 0003 (onboarding, item 4), ADR 0008 (backend M1)

## Contexto

A ADR 0003 fixou que tier e módulos vêm de **entitlements emitidos pela
plataforma** — nunca digitados pelo cliente — e que o gating acontece no build. O
que ficou em aberto era o mecanismo: como o entitlement chega ao repo do cliente
de forma que (a) o cliente não consiga se auto-promover de tier e (b) funcione
sem infraestrutura online no M1.

O que pesa:

1. **O gating roda no build, que roda na nossa imagem** (ADR 0006). O ponto de
   enforce existe; falta garantir a integridade do dado de entrada.
2. **Não há backend ainda no início do M1** — um endpoint de entitlements só faz
   sentido junto com a API (ADR 0008). O mecanismo precisa funcionar offline
   desde já.
3. **Assinatura assimétrica resolve os dois**: a plataforma assina com a chave
   privada; o builder verifica com a chave pública embarcada na imagem. O cliente
   pode ler o arquivo, mas qualquer adulteração invalida a assinatura.
4. **Ed25519** é o padrão moderno para isso: chaves curtas, verificação rápida,
   implementação madura em Python (`cryptography`/`PyNaCl`) — sem PKI, sem
   certificado, sem dependência de rede.

## Decisão proposta

1. **Entitlement = bloco `entitlements` assinado dentro do `museum.config.json`**
   do repo do cliente:
   - payload: `{museum_id, tier, modules, issued, expires}` serializado em JSON
     canônico (chaves ordenadas, sem espaços);
   - campo `signature`: assinatura Ed25519 do payload, em base64.
2. **Chave privada da plataforma** fica fora do repo (secret do dono);
   `tools/sign_entitlements.py` (na plataforma) é o único emissor — rodado por nós
   a cada onboarding ou mudança de tier.
3. **Chave pública embarcada** em `musa_build/data/` dentro da imagem — o cliente
   não a controla porque não controla a imagem (ADR 0006).
4. **O builder falha o build** se a assinatura estiver ausente, inválida ou
   expirada. Exceção: `musa: "0.0.0-unreleased"` (modo dev local), que avisa em
   vez de falhar.
5. **Endpoint online é a fase 2** (com a API do M1.2): mesmo formato de payload e
   mesma verificação, apenas muda o canal de entrega (arquivo no repo → resposta
   da API). O código de verificação é um só, com dois modos de entrega — como
   previsto na ADR 0003 item 4.
6. **Verificação falsificável**: adulterar o `tier` no `museum.config.json` do
   DemoMuseum deve quebrar o build — este é o teste de aceite do M1.2.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Endpoint online desde o início** | Exige backend, auth e deploy antes da API existir; o M1.2 ficaria bloqueado na M1.1 inteira |
| **JWT assinado (RS256)** | Funciona, mas carrega ecossistema de JWT (header, claims, libs) para um payload de 5 campos; Ed25519 sobre JSON canônico é mais simples e auditável |
| **Hash/HMAC com segredo compartilhado** | O segredo teria que estar na imagem do builder — e quem tem o segredo verifica **e** forja; chave assimétrica separa emissor de verificador |
| **Entitlements digitados pelo cliente com checksum** | Cliente controla o arquivo inteiro — checksum sem chave não impede auto-promoção |

## Consequências

- O cliente pode ler seus entitlements (transparência), mas não pode alterá-los —
  auto-promoção de tier quebra o build, de forma verificável.
- Onboarding de cliente novo = rodar um script e commitar o config assinado; sem
  infraestrutura online.
- Rotação de chave é possível (nova chave pública na próxima release da imagem),
  mas exige re-assinar os configs dos clientes — operação rara e manual.
- Quando o endpoint online chegar, nenhum repo de cliente muda de formato — só
  ganha a opção de buscar entitlements atualizados em vez de esperar commit.
- Risco aceito: perda da chave privada = re-emissão de todos os entitlements;
  mitigado por ela viver como secret do dono (mesmo padrão do `GHCR_PULL_TOKEN`).
