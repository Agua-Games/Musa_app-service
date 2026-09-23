# ADR 0006 — Formato do artefato: imagem de contêiner no ghcr.io + GitHub Releases

- **Status:** aceita
- **Data:** 2026-09-23
- **Relacionada:** ADR 0003 (onboarding de clientes), ADR 0005 (publicação do frontend)

## Contexto

O M0 exige transformar `source/` em um artefato que um repositório de cliente possa
consumir (entregável M0.4). O requisito central, decidido na ADR 0003, é: **cada cliente
tem um repositório independente com apenas os seus ativos; o código do aplicativo e a
lógica de controle de funcionalidades são gerenciados de forma centralizada e não podem
ser modificados pelo cliente** — "construir uma vez, distribuir para muitos".

As opções eram: pacote `@musa/app` no GitHub Packages (npm), imagem de contêiner, ou
GitHub Release com tarball.

## Decisão

**Imagem de contêiner publicada no GitHub Container Registry (`ghcr.io/agua-games/musa-app`),
com GitHub Releases como registro canônico de versões.** Decidido pelo dono do produto em
2026-09-23. Os motivos:

1. **Isolamento de ambiente.** A imagem encapsula o runtime completo (Python, builder,
   frontend genérico, contrato congelado, three.js vendorizado): cada cliente executa
   exatamente a mesma versão, sem variação de ambiente.
2. **Imutabilidade.** A imagem é read-only — o cliente executa, não modifica. O portão do
   contrato e o gating de tier viajam dentro do artefato (invariantes §5.1–§5.2), e não
   há como um cliente rodar "a sua versão" do portão.
3. **Entrega de versão.** Push de uma tag `vX.Y.Z` dispara o workflow de release, que
   publica a imagem com a tag correspondente. Atualizar um cliente é mudar **uma linha**
   em `museum.config.json` (`"musa": "0.2.0"`) e dar push.
4. **Integração natural.** O CI do cliente faz `docker run` da imagem com o repositório
   montado; a Azure App Service (hospedagem futura) aceita implantação direta de imagem.
5. **Custo.** O armazenamento de imagens no ghcr.io é atualmente gratuito; pacotes npm
   privados têm cota apertada no plano Free (500 MB + 1 GB/mês de tráfego).

O **GitHub Release** acompanha cada tag: notas de versão e changelog, para que o cliente
saiba o que mudou antes de subir o pin.

## Consequências

- O `Dockerfile` vive na raiz do repositório da plataforma; `.github/workflows/release.yml`
  publica `ghcr.io/agua-games/musa-app:<versão>` a cada tag `v*`. A tag da imagem **não**
  leva o prefixo `v` (`0.1.0`), para casar com o valor de `musa` em `museum.config.json`.
- A versão da tag, o `__version__` do builder e o `version` do `pyproject.toml` devem
  concordar — o workflow de release **falha** se divergirem.
- O pacote no ghcr.io é **privado**: o CI de cada cliente autentica com um token
  `read:packages` guardado como secret do repositório do cliente (ver
  `templates/client-deploy.yml`).
- npm/GitHub Packages e tarball em Release ficam descartados: não encapsulam o runtime
  (npm) ou não são executáveis sem montagem de ambiente (tarball).
