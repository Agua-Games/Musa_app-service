Para o seu projeto que exige um visual moderno, gráficos 3D com WebGL e funcionalidades avançadas como RAG, o cenário ideal não é uma única API, mas uma combinação de ferramentas especializadas.

Sobre sua pergunta direta: **o Kimi Code é uma ferramenta de agente de programação**, excelente para refatorar e gerenciar grandes bases de código . Ele pode ajudar a *construir* seu sistema, mas não é uma API de serviço para entregar as funcionalidades de IA do seu site. Para isso, você precisará de outros serviços.

Aqui está um panorama das melhores opções para atender cada parte da sua demanda:

### 🏆 Recomendação de Destaque: VULK MCP Server

Para alcançar um visual "gráfica e impactante" com o mínimo de esforço, o **VULK MCP Server** é a ferramenta mais alinhada com seus objetivos.

*   **Foco:** É um conector MCP ("Model Context Protocol") projetado especificamente para criar sites "imersivos" e com gráficos ricos a partir de descrições em linguagem natural .
*   **Conexão com 3D/WebGL:** Sua principal função é gerar projetos web com **3D/WebGL, elementos cinematográficos e ricos em vídeo**, atendendo diretamente ao seu pedido por um visual sofisticado .
*   **Integração:** Ele se conecta a assistentes de IA populares (como Claude, Codex e Cursor) e fornece ferramentas para criar, editar, listar e implantar projetos .
*   **Ponto de Atenção:** O VULK é um serviço especializado. Para a parte de backend, banco de dados e RAG, você ainda precisará integrar outras soluções.

### ⚙️ Soluções para RAG, Backend e Indexação de Código

Para a parte "inteligente" do seu site (back-end, banco de dados e RAG), você pode construir sua própria solução ou usar ferramentas específicas.

*   **DevDocs AI (Framework de Referência):** Este é um projeto de código aberto que serve como um excelente modelo para o que você deseja. Ele já implementa:
    *   **Stack:** Backend em ASP.NET Core, frontend em Next.js e banco de dados PostgreSQL com pgvector para buscas vetoriais .
    *   **RAG e Indexação:** Oferece chat com citações das fontes, busca semântica e ingestão de repositórios do GitHub, tudo com uma arquitetura de segurança multi-tenant .
    *   **Modelos de IA:** Utiliza o **Gemini para embeddings** e permite configurar o provedor de chat (ex: Ollama para modelos locais ou Gemini) .

*   **CodeScope (Ferramenta de Indexação de Código):** Se o seu objetivo é indexar e fazer perguntas sobre uma base de código existente, o CodeScope é uma ótima opção.
    *   **Funcionalidade:** Ele transforma qualquer repositório em um site navegável com busca semântica e "diffs" explicados por IA .
    *   **Embeddings:** Usa o modelo `voyage-code-3` para gerar embeddings de alta qualidade, com um gateway gratuito que valida sua chave da Anthropic .

*   **Construção do Zero (Backend + RAG):** Para um controle total, você pode construir seu próprio backend. Projetos como o "AI Website Builder" mostram como usar **FastAPI e a API da OpenAI** para gerar sites . Guias práticos demonstram como criar um backend com **FastAPI e React** para alimentar um chatbot com RAG usando PostgreSQL/pgvector e modelos como o Gemini .

### 🧠 Modelos de IA para o "Cérebro" do seu Site

Para as funções de chat, RAG e geração de conteúdo, você usará APIs de LLMs. As principais opções em 2026 são:

| Modelo | Melhor Para | Pontos Fortes | Considerações |
| :--- | :--- | :--- | :--- |
| **GPT-5.5 / GPT-5.4 (OpenAI)** | Tarefas gerais de programação e arquitetura | Líder em benchmarks, versátil e confiável para full-stack . | Pode ser mais lento que modelos menores . |
| **Claude 4.7 (Anthropic)** | Código limpo, revisões e documentação | Conhecido por gerar código de alta qualidade e legível. Possui uma janela de contexto massiva, ótima para codebases grandes . | Pode ser menos agressivo na resolução de bugs complexos . |
| **Gemini 3.1 (Google)** | Workflows multimodais e debugging visual | Entende não só código, mas também **screenshots, diagramas e logs**, ideal para depurar problemas de interface . | O estilo de código pode ser menos consistente que o de seus concorrentes . |

### 💎 Resumo e Próximos Passos

1.  **Para o Visual 3D:** Comece explorando o **VULK MCP Server**. É a ferramenta mais direta para transformar sua ideia de um site com visual impactante em realidade, integrando-a com seu assistente de IA preferido .
2.  **Para a Lógica de IA (RAG, Chat, Busca):**
    *   Se você prefere uma solução pronta e configurável, o **DevDocs AI** é um ponto de partida fantástico, pois já tem toda a arquitetura de RAG, autenticação e ingestão de dados .
    *   Se você quer construir do zero, APIs como a do **Gemini** (especialmente para embeddings) e do **OpenAI** (para geração de texto) são as mais consolidadas e com bom custo-benefício para esses casos de uso .
3.  **Para a "Mão na Massa" (Coding Agent):** O **Kimi Code** é uma excelente ferramenta para auxiliar no desenvolvimento. Use-o para escrever, refatorar e testar o código do seu frontend, backend e integrações com as APIs escolhidas .

Em resumo: **Kimi Code para programar** + **VULK para os gráficos 3D** + **Gemini/OpenAI para o cérebro (RAG/chat)** é uma combinação poderosa e alinhada com o que há de mais moderno no mercado.

Espero que este panorama ajude na sua decisão! Se quiser aprofundar em algum desses caminhos, é só me perguntar.

------------------------------------------------------------------------------------------------------------------------------------------------

Entendi perfeitamente seu objetivo agora. Você não quer apenas uma API de IA, mas o **kit completo (assistente + IDE)** mais eficiente e com melhor custo-benefício para prototipar rapidamente um website-app. E esse website tem necessidades bem específicas: um visual com seções 2D e um viewer 3D impactante, além da integração com um backend robusto para acervos de museus, como o Tainacan.

Com base no que há de melhor em 2026, aqui está o panorama para você decidir.

### 🚀 A Melhor Dupla para o Seu Projeto: VULK + Cursor

Para o que você descreveu, a recomendação mais certeira é combinar duas ferramentas que se complementam perfeitamente:

1.  **VULK (com seu MCP Server) para a Geração do Site:** Esta é a ferramenta que atende diretamente seus pedidos por um visual moderno e 3D.
    *   **Foco em 3D/WebGL:** O VULK é posicionado como um gerador de "prompt-to-immersive-site", com um pipeline especializado em criar projetos web com **3D/WebGL, elementos cinematográficos e ricos em vídeo** a partir de uma simples descrição .
    *   **Kit Completo:** Ele não gera apenas o frontend. O VULK cria um projeto full-stack com backend PostgreSQL real, autenticação e API REST, tudo pronto para ser exportado e implantado .
    *   **Integração com seu Assistente:** O VULK possui um servidor MCP (Model Context Protocol), que age como uma ponte. Você pode conectá-lo ao seu IDE/assistente favorito (como o Cursor ou o próprio Claude Desktop) e, de dentro do chat, dar comandos como *"crie um site com um viewer 3D para modelos de museu usando Three.js"* . A ferramenta gera o projeto e te retorna um link para prévia e edição.
    *   **Preço:** O plano pago do VULK começa em €19,99/mês, com um período de teste de 3 dias por €3,99 . Não há plano gratuito, mas o investimento pode valer muito pela velocidade de prototipação.

2.  **Cursor como seu IDE para dar os retoques finais:** Você mencionou a necessidade de acesso à base de código e integração com bibliotecas third-party.
    *   **Controle Total:** O VULK é excelente para a geração inicial, mas você precisará de um IDE poderoso para ajustar o código gerado, integrar o Tainacan e fazer a engenharia fina.
    *   **Contexto Profundo:** O Cursor é um fork do VS Code com uma compreensão profunda do seu código, permitindo que você faça refatorações complexas e entenda todo o projeto com ajuda da IA .
    *   **Preço e Integração MCP:** O Cursor tem um plano gratuito limitado e um plano Pro por $20/mês . Além disso, ele é um dos IDEs com melhor suporte para MCP, o que significa que você pode manter o VULK conectado a ele e usar ambos em conjunto .

### ⚖️ Comparando os Modelos de IA (DeepSeek vs. Kimi)

Você perguntou sobre o Kimi Coder e o DeepSeek Coder. Em 2026, ambos são titãs open-weight (com modelos disponíveis para uso e, em muitos casos, com pesos abertos), e a escolha entre eles se resume a detalhes finos.

| Característica | Kimi (K2.6 / K3) | DeepSeek (V4-Pro) |
| :--- | :--- | :--- |
| **Custo (por 1M tokens)** | Mais caro (~$0.60-$0.95 input / $2.80-$4.00 output). | **Mais barato** (~$0.435 input / $0.87 output off-peak). |
| **Licenciamento** | Modified MIT . | **MIT** (mais permissivo) . |
| **Multimodalidade** | **Possui visão nativa**, pode interpretar imagens e esboços . | Apenas texto . |
| **Performance em Código** | Excelente. Kimi K2.6 tem SWE-Bench de 80.2% . Kimi K3 foi elogiado por escrever código "mais limpo" em um estudo recente . | Excelente. DeepSeek V4-Pro tem SWE-Bench de 80.6% . |
| **Inteligência Geral** | Levemente superior (K2.6: 54 vs V4-Pro: 52 no Artificial Analysis Index) . | Muito próximo. |
| **Contexto** | ~1M de tokens . | ~1M de tokens . |

**Resumo da comparação:** Se o custo for o fator mais crítico para o seu protótipo, o **DeepSeek V4-Pro** é imbatível . Porém, se você acha que a capacidade de entender imagens (por exemplo, para gerar código a partir de um esboço de interface) pode agilizar seu trabalho, o **Kimi K2.6 ou K3** leva vantagem . As avaliações de usuários sobre ambos são muito positivas, com o Kimi K3 sendo apontado como um concorrente direto dos melhores modelos americanos .

### 🏛️ Sobre o Tainacan e Alternativas

*   **Tainacan:** É uma plataforma de repositório digital construída sobre o **WordPress**, desenvolvida com foco em instituições culturais brasileiras . Ele é open-source e atende bem ao propósito de gerenciar acervos, mas como você mesmo notou, sua base no WordPress pode adicionar uma camada de complexidade se seu objetivo é um website mais customizado . Ainda assim, é uma opção válida e consolidada.
*   **Alternativas Open-Source:** Se estiver aberto a explorar, ferramentas que seguem padrões como o **IIIF (International Image Interoperability Framework)** são extremamente poderosas para acervos de museus, permitindo um alto grau de interoperabilidade e visualização de imagens . Integrar seu app com uma solução IIIF pode ser mais moderno e flexível que o WordPress, dependendo do seu nível de conhecimento técnico.

### 💎 Resumo do Plano de Ação

1.  **Para Prototipação Rápida:** Comece com a dupla **VULK + Cursor**. Use o VULK para gerar a estrutura inicial do site com o viewer 3D que você precisa. Essa é a forma mais rápida de sair do zero para um protótipo funcional com visual impactante .
2.  **Para a Parte Inteligente (Backend e RAG):** Enquanto o VULK cuida da geração, o **Cursor** será seu IDE principal para integrar o backend. Você pode usar a IA do próprio Cursor (que pode ser configurada para usar DeepSeek ou Kimi) para te auxiliar a escrever o código de integração com o Tainacan ou qualquer outra API, e até mesmo para construir um sistema de RAG (Recuperação Aumentada de Geração) usando um banco de dados vetorial como o pgvector.
3.  **Para os Modelos de IA (DeepSeek vs Kimi):** Comece com o mais barato, **DeepSeek V4-Pro**, já que ele tem performance similar ao Kimi por um custo menor. Se precisar da capacidade de entender imagens, troque para o **Kimi K2.6** .

Esse fluxo de trabalho te dá o melhor dos dois mundos: a velocidade de geração do VULK e o controle total e refinamento que o Cursor e os melhores modelos de IA proporcionam.

Espero que esse roteiro detalhado ajude! Se quiser explorar mais a fundo a integração com o Tainacan ou como configurar o RAG, é só me perguntar.

-----------------------------------------------------------------------------------------------------------------------------------------------------------------

Excelente, essa é a pergunta certa. Vamos por partes: entender como esses assistentes "veem" seu código e encontrar um substituto para o Tainacan que seja mais leve e baseado em IIIF.

### 🧠 DeepSeek no Copilot e Awareness da Codebase

A extensão que você instalou usa o modelo DeepSeek dentro do chat do Copilot. **Por si só, ela não faz RAG ou vetorização da sua base de código.** Ela funciona com o contexto que você fornece manualmente (abrindo arquivos e mencionando-os no chat) ou com o contexto que o Copilot já envia (que é limitado ao arquivo atual e alguns relacionados).

No entanto, há uma maneira de ter uma "awareness" completa e barata usando a mesma API DeepSeek: **Flashlight MCP**.

*   **O que é**: Um servidor MCP (Model Context Protocol) que usa a janela de contexto massiva de 1 milhão de tokens do DeepSeek para pesquisar *todo o seu código* sem precisar de embeddings ou indexação complexa.
*   **Como funciona**: Ele carrega sua base de código inteira no contexto do DeepSeek e usa a compreensão da IA para encontrar o código relevante para sua pergunta. É uma abordagem "bruta", mas muito eficaz.
*   **Custo**: Usa o cache de prefixo do DeepSeek para ser extremamente barato (¥0,02/milhão de tokens para consultas em cache vs ¥1/milhão para consultas novas).
*   **Integração**: Você pode configurá-lo como um servidor MCP no Kimi Code, e provavelmente em outras ferramentas que suportem MCP.

Se você quer essa capacidade de busca inteligente em toda a base, vale a pena testar o Flashlight.

### 🏛️ Substituições Open-Source ao Tainacan Baseadas em IIIF

O IIIF (International Image Interoperability Framework) é exatamente o que você precisa para evitar a complexidade do WordPress e ter um sistema de acervo mais flexível e interoperável. Aqui estão duas alternativas open-source e gratuitas que se encaixam no seu projeto:

**1. Archipelago Commons**

*   **O que é**: Um Sistema de Repositório de Objetos Digitais e DAM (Digital Asset Management) open-source, construído sobre Drupal 10.
*   **Foco**: Projetado especificamente para a comunidade GLAM (Galeries, Libraries, Archives, Museums). Já foi adotado por instituições como Barnard College, Rensselaer Polytechnic Institute e University of Edinburgh.
*   **Integração IIIF**: Suporta o IIIF para entrega de imagens (com visualização de gigapixels), além de usar o Cantaloupe Image Server para processamento dinâmico de imagens. É uma solução completa, mas ainda tem a camada do Drupal, que você pode ou não considerar complexa.

**2. Canopy IIIF**

*   **O que é**: Um gerador de sites estáticos open-source.
*   **Foco**: Criar sites de coleções digitais "fast, contextualization, and customization". É uma abordagem mais leve: você não tem um backend, apenas um site estático que consome dados de uma API IIIF.
*   **Como funciona**: Usa uma única "IIIF Presentation Collection" como fonte de dados e gera um site estático com Next.js, sem duplicar conteúdo ou copiar ativos. É ideal se você quer um visual moderno e rápido, sem a complexidade de gerenciar um servidor de banco de dados.

### 💎 Resumo e Recomendação

*   **Para awareness de código**: A extensão padrão não faz RAG, mas você pode alcançar esse objetivo com o **Flashlight MCP**, que usa o DeepSeek para pesquisar em toda a sua base de código de forma barata e eficiente. O Kimi Code também possui um entendimento profundo do projeto graças ao seu contexto de 1M de tokens e ao suporte a MCP.
*   **Para substituir o Tainacan**:
    *   Se você quer uma solução mais "pronta para uso", com todas as funcionalidades de um repositório digital e não se importa com a base em Drupal, o **Archipelago Commons** é uma excelente escolha.
    *   Se você prefere uma abordagem mais leve, moderna e com foco em frontend, o **Canopy IIIF** é perfeito para você. Você pode gerar um site bonito e funcional que consome dados de uma fonte IIIF, sem precisar de um backend complexo.

Espero que essas opções ajudem a descomplicar seu projeto! Boa sorte nos testes.

-----------------------------------------------------------------------------------------------------------------------------------------------------------------

ATHOS:
Ok. Quanto a uma ferramenta/solução para a hospedagem e apresentação online de forma procedural e agnóstica de um banco de dados (que é o que busco):
- qual seria a complexidade de implementar algo assim com um assistente versus usar uma dessas soluções que você listou? Implementar: scripts que lêem e gerenciam a relação entre um banco de dados cujo principal elemento de organização são folders (para coleções, sub-coleções, etc) e cujo principal tipo de dado (padronizado) são fichas (de cada peça do acervo) em estilo json/toml. Os scripts lêem as pastas, baseados em qual pasta ou subpasta uma peça (a pasta do asset, todas suas dependencies dentro da mesma pasta. ex: um vaso grego) está, colocam numa certa página do site/frontend, preenchendo os campos (que são agnósticos, atribuídos via tags) com base diretamente nos campos da ficha em json/toml?
- seria possível usar usd para estas fichas base dos assets? Pergunto porque é possível ter num arquivo usd tanto imagens 2d estáticas quanto modelos 3d, inclusive em formatos como glb, fbx, etc? Se for um usdc ou usdz (formato zipado) seria possível lê-los no website? Assim facilitaria ter, e de uma forma que dialogue, tanto assets atomizados (ex: um vaso) quanto acervos de alas inteiras (digital twins de alas do museu) no mesmo formato. E digital twins de assistentes IA in loco (robozinhos, display fixos, etc)?

-------------------------------------------------------------------------------------------------------------------------------------------------------------------

Essas são perguntas muito boas e vão direto ao cerne do seu projeto. Vamos analisar cada uma delas separadamente.

### 1. Complexidade: Implementar do Zero vs. Usar Soluções Existentes

A curto prazo, **usar uma das soluções existentes (como o Canopy IIIF ou o CollectionBuilder) seria bem mais rápido**. Elas já resolvem a parte mais chata: ler metadados, gerar páginas e exibir imagens. Você só precisaria adaptar seus dados (as pastas e as fichas JSON/TOML) para o formato que elas esperam (geralmente um arquivo de configuração centralizado com os caminhos) .

**Implementar tudo do zero com um assistente de IA** seria uma tarefa bem mais longa e complexa. Você precisaria pedir para ele criar:

1.  **Um "scanner" de pastas**: Um script que navega pela sua estrutura de diretórios recursivamente .
2.  **Um "parser" de fichas**: Para ler e interpretar seus arquivos JSON/TOML, que funcionariam como um esquema de metadados.
3.  **Um gerador de rotas/páginas**: A lógica para, baseado na localização da pasta, decidir em qual página do frontend aquele item deve aparecer (em uma coleção, sub-coleção, etc.). Isso exigiria um sistema de roteamento dinâmico.
4.  **A interface de visualização**: Que, para ser moderna e gráfica, provavelmente usaria **Three.js** ou uma biblioteca similar.

O grande desafio é fazer o assistente gerar um código que seja robusto e mantenha a coerência entre a estrutura de pastas (a organização do acervo) e o frontend. A IA pode "pirar" e gerar loops complexos se você não for muito específico nas instruções.

**A melhor estratégia é uma abordagem híbrida:** Use o assistente de IA para te ajudar a **criar um adaptador**. Ao invés de construir todo o sistema do zero, peça para ele escrever um script que leia suas pastas e fichas e as converta para o formato de metadados de uma ferramenta como o **CollectionBuilder** (que usa um arquivo CSV)  ou que gere um **IIIF Manifest** para cada item. Feito isso, você usa as ferramentas existentes para a geração do site.

### 2. Usar USD (Universal Scene Description) para as Fichas dos Assets

A sua ideia de usar USD (usando arquivos `.usd`, `.usdc` ou `.usdz`) como um container unificado é excelente e tem tudo a ver com as tendências atuais. A resposta é: **sim, é tecnicamente viável e existem ferramentas para isso**.

*   **Visualização Web**: Você pode carregar e visualizar arquivos USD diretamente no navegador. Isso é possível graças a projetos open-source que compilaram o código do USD (escrito em C++) para WebAssembly (WASM) . Ferramentas como **USD Web View** e a biblioteca **Needle USD** permitem renderizar cenas USD complexas com Three.js .
*   **Renderização**: A biblioteca `@needle-tools/usd` é um exemplo chave. Ela é um runtime WebAssembly que permite renderizar "estágios USD reais e compostos (.usd, .usda, .usdc, .usdz) com MaterialX diretamente no navegador" . Isso significa que você pode ter texturas, iluminação e materiais complexos.
*   **Suporte a Assets Diversos**: O USD é nativamente capaz de referenciar outros arquivos. Ele pode carregar modelos 3D em formatos como `glTF/GLB` diretamente dentro de um estágio USD . Isso é perfeito para seus "assets atomizados" como vasos (em GLB) dentro de uma cena maior.
*   **Arquitetura de Código**: O que você chama de "ficha base" são os **metadados**. No USD, os metadados de um prim (objeto) podem ser armazenados como atributos personalizados (`customData`). Você poderia, teoricamente, colocar os dados da sua ficha JSON diretamente nos atributos do prim correspondente no arquivo USD.

**Quanto à sua pergunta sobre robôs e digital twins**, você está descrevendo um sistema de **"mundo virtual" ou "metaverso"**. Para isso, você precisaria não apenas de visualização, mas de um **backend de simulação** que atualizasse a posição e estado desses robôs em tempo real. O USD, por si só, é um formato de cena estático ou com animações pré-definidas. Para interações ao vivo com robôs, você precisaria de um servidor de aplicação e uma camada de rede (como WebSockets) para atualizar a cena USD em tempo real, e um renderizador que suporte essas atualizações.

### 💎 Resumo e Recomendação Final

*   **Complexidade**: **Não construa tudo do zero com IA**. É um projeto grande e propenso a problemas. Use a IA para construir um "tradutor" de dados que se conecte a ferramentas maduras como o CollectionBuilder.
*   **USD**: **Use USD como seu formato de arquivo central**. Ele é poderoso, agnóstico e perfeitamente adequado para unificar seus assets 2D e 3D. Para visualização web, ferramentas como a **Needle USD** e o **USD Web View** são o caminho.
*   **IIIF**: Continue de olho no IIIF para imagens 2D, especialmente com viewers como o **Mango** . O futuro da padronização de dados 3D, como o USD, e a sua integração com padrões como IIIF é um caminho promissor, mas ainda em desenvolvimento . Usar USD como container e exportar imagens para IIIF pode ser uma excelente arquitetura híbrida.

Esse caminho que você está traçando é muito inovador. Combinar a flexibilidade do USD com a robustez de sistemas de acervo e padrões web é o que há de mais moderno para museus e patrimônio cultural.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Ótimo! Vamos desenhar essa arquitetura de forma clara e detalhada, com todos os componentes, pipelines e como eles se conectam.

## 🏛️ Arquitetura Completa do Sistema

### Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SISTEMA DE GESTÃO DE ACERVO                         │
│                         (Arquitetura Híbrida USD + IIIF)                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐
│   CAMADA DE      │    │   CAMADA DE      │    │   CAMADA DE FRONTEND     │
│   DADOS/ACERVO   │───▶│   PROCESSAMENTO  │───▶│   (Website + Visualização)│
│                  │    │   (Pipelines)    │    │                          │
└──────────────────┘    └──────────────────┘    └──────────────────────────┘
```

---

## 📁 CAMADA 1: ESTRUTURA DE DADOS (Acervo Físico)

### Estrutura de Pastas do Acervo

```
acervo/
├── colecao_egipcia/
│   ├── metadata.toml              # Metadados da coleção
│   ├── vaso_canopo/
│   │   ├── asset.usda             # Arquivo USD com o modelo 3D
│   │   ├── asset.glb              # Modelo 3D (referenciado pelo USD)
│   │   ├── textures/              # Texturas do modelo
│   │   │   ├── base_color.png
│   │   │   └── normal_map.png
│   │   ├── images/                # Imagens 2D para visualização
│   │   │   ├── front.jpg
│   │   │   ├── side.jpg
│   │   │   └── detail.jpg
│   │   └── ficha.toml             # Ficha do item (metadados)
│   │
│   └── sarcófago/
│       ├── asset.usda
│       ├── asset.glb
│       └── ficha.toml
│
├── colecao_grega/
│   ├── metadata.toml
│   ├── anfora/
│   │   ├── asset.usda
│   │   ├── images/
│   │   └── ficha.toml
│   └── estatueta/
│       ├── asset.usda
│       └── ficha.toml
│
└── alas/                          # Digital Twins do museu
    ├── ala_egipcia/
    │   ├── layout.usda            # Layout completo da ala (com referências)
    │   ├── robos/                 # Robôs/assistentes virtuais
    │   │   ├── robo_guia.usda
    │   │   └── display_interativo.usda
    │   └── mobiliario.usda        # Vitrines, pedestais, etc.
    └── ala_grega/
        ├── layout.usda
        └── robos/
```

### Exemplo de Ficha (ficha.toml)

```toml
# Ficha do item: vaso_canopo
[identificacao]
id = "EG-001"
nome = "Vaso Canopo com Cabeça de Falcão"
data = "650 a.C."
periodo = "Período Saíta"
cultura = "Egípcia"

[classificacao]
categoria = "Vaso Canopo"
material = "Alabastro"
tecnica = "Esculpido e Polido"
dimensoes = { altura = "45cm", largura = "18cm", profundidade = "18cm" }

[localizacao]
ala = "Ala Egípcia"
vitrine = "Vitrine 12"
numero_inventario = "MUS-2024-001"

[descricao]
resumo = "Vaso canopo para vísceras mumificadas, representando o deus Qebehsenuef"
detalhes = "Detalhamento completo do objeto..."

[tags]
interesses = ["religiao", "mumificacao", "deuses_egipcios"]
estilos = ["arte_funeraria"]
cronologia = ["VII_seculo_AC"]

[apresentacao]                      # Configuração de como exibir no website
prioridade = "alta"                 # Destaque na home
rotacao_3d = true                   # Permite rotação do modelo
zoom = true                         # Permite zoom
preview_imagem = "front.jpg"        # Imagem de preview

[relacoes]
parte_de = "colecao_egipcia"
gemelo_digital = "ala_egipcia/layout.usda#vitrine_12"
```

### Exemplo de Configuração da Coleção (metadata.toml)

```toml
[colecao]
id = "colecao_egipcia"
nome = "Coleção Egípcia"
descricao = "Acervo de artefatos do Antigo Egito, período de 3000 a.C. a 30 d.C."
cor_primaria = "#D4A574"
icone = "pyramid.svg"

[configuracao]
viewer_3d_padrao = true
ordem_exibicao = "cronologica"
```

---

## 🔄 CAMADA 2: PIPELINE DE PROCESSAMENTO

### Pipeline Detalhado

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE DE PROCESSAMENTO                          │
└─────────────────────────────────────────────────────────────────────────────┘

        ┌─────────────────────┐
        │   ACERVO (PASTAS)   │
        │                     │
        │  ├── colecao_egipcia│
        │  ├── colecao_grega  │
        │  └── alas/          │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐     ┌─────────────────────┐
        │   WATCHER SERVICE   │     │   SCHEDULED SCAN    │
        │   (File Watcher)    │     │   (Cron Job)        │
        └──────────┬──────────┘     └──────────┬──────────┘
                   │                            │
                   └────────────┬───────────────┘
                                ▼
        ┌────────────────────────────────────────────────────────────┐
        │            PROCESSADOR DE METADADOS                        │
        │  (Python - Pydantic + Tomli + JSON)                       │
        │                                                           │
        │  1. Lê ficha.toml de cada pasta                           │
        │  2. Valida esquema dos metadados                          │
        │  3. Extrai tags e relações                                │
        │  4. Gera índice de busca                                  │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE MANIFESTS IIIF                      │
        │  (Python - IIIF Presentation API v3)                     │
        │                                                           │
        │  Para cada item:                                          │
        │  1. Lista imagens 2D na pasta /images                    │
        │  2. Cria Manifest (info.json) com todas as imagens       │
        │  3. Salva em /iiif/colecao/id/                          │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE CENAS USD                           │
        │  (Python - pxr.Usd / USD Web View)                       │
        │                                                           │
        │  Para cada item/ala:                                      │
        │  1. Carrega asset.usda                                   │
        │  2. Resolve referências a GLB/texturas                  │
        │  3. Adiciona metadados como customData                   │
        │  4. Gera versão otimizada para web (USDZ)               │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            INDEXADOR DE BUSCA (RAG)                       │
        │  (Python - Qdrant / LanceDB + Sentence Transformers)     │
        │                                                           │
        │  1. Concatena metadados + descrições                     │
        │  2. Gera embeddings (BAAI/bge-base)                      │
        │  3. Armazena vetores + metadados no Qdrant              │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE SITE ESTÁTICO                       │
        │  (Next.js / Astro + CollectionBuilder)                   │
        │                                                           │
        │  1. Lê índice de metadados processados                   │
        │  2. Gera páginas para cada coleção/item                  │
        │  3. Insere referências aos manifests IIIF               │
        │  4. Insere referências aos USD (via WebAssembly)        │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            SAÍDA (Site Build)                             │
        │  /dist/                                                   │
        │  ├── index.html                                           │
        │  ├── colecao_egipcia/                                    │
        │  ├── item_vaso_canopo/                                   │
        │  ├── iiif/                                              │
        │  ├── assets/   (USDZ, GLB, imagens)                     │
        │  └── data/     (JSON para busca dinâmica)               │
        └────────────────────────────────────────────────────────────┘
```

---

## 🖥️ CAMADA 3: FRONTEND (Website + Visualização 3D)

### Arquitetura do Frontend

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEBSITE (Next.js / Astro)                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYOUT (Tailwind CSS + shadcn/ui)                                        │
│  ├── Header/Navegação                                                     │
│  ├── Página Inicial (Carrossel + Destaques)                              │
│  ├── Página de Coleções                                                  │
│  ├── Página de Item (Detalhe + Viewer)                                   │
│  └── Página de Busca (RAG + Filtros)                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPONENTES DE VISUALIZAÇÃO                                              │
│                                                                           │
│  ┌─────────────────────┐    ┌─────────────────────┐                      │
│  │   IIF VIEWER        │    │   USD WEB VIEWER    │                      │
│  │   (Mango / OpenSea  │    │   (Needle USD +     │                      │
│  │   Dragon)           │    │    Three.js)        │                      │
│  │                     │    │                     │                      │
│  │  - Zoom/Pan         │    │  - 3D Rendering     │                      │
│  │  - Rotação automática│   │  - WebGL/WebGPU     │                      │
│  │  - Comparação de    │    │  - Animations       │                      │
│  │    imagens          │    │  - Interação AR/VR  │                      │
│  └─────────────────────┘    └─────────────────────┘                      │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  DIGITAL TWIN VIEWER (Three.js + USD WebAssembly)                │   │
│  │                                                                  │   │
│  │  - Renderiza alas completas do museu                            │   │
│  │  - Navegação em tempo real (WASD + Mouse)                      │   │
│  │  - Robôs/Agentes interativos (movimento via WebSockets)        │   │
│  │  - Destaque de itens selecionados (hover/click)               │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  API E SERVIÇOS                                                            │
│                                                                           │
│  ┌─────────────────────┐    ┌─────────────────────┐                      │
│  │   API DE BUSCA (RAG) │    │   API DE METADADOS   │                      │
│  │   (FastAPI + Qdrant)│    │   (FastAPI + SQLite) │                      │
│  │                     │    │                     │                      │
│  │  /search?q=...      │    │  /items/{id}        │                      │
│  │  /search/semantic   │    │  /collections       │                      │
│  └─────────────────────┘    └─────────────────────┘                      │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  WEBSOCKET SERVER (para digital twins)                           │   │
│  │                                                                  │   │
│  │  - Atualiza posição de robôs em tempo real                      │   │
│  │  - Envia eventos de interação (clique em item)                 │   │
│  │  - Sincroniza estado entre múltiplos usuários                   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Exemplo de Página de Item no Frontend

```tsx
// pages/item/[id].tsx (Next.js)
export default function ItemPage({ item, manifestUrl, usdUrl }) {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-8">
        {/* Breadcrumbs */}
        <Breadcrumb items={[item.collection, item.category, item.name]} />
        
        {/* Título e Metadados */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <h1 className="text-4xl font-serif mb-4">{item.name}</h1>
            
            {/* Viewer Tabs */}
            <Tabs>
              <Tab label="3D">
                <USDViewer url={usdUrl} />
              </Tab>
              <Tab label="Imagens">
                <IIIFViewer manifest={manifestUrl} />
              </Tab>
              <Tab label="Digital Twin">
                <DigitalTwinViewer alaId={item.ala} position={item.position} />
              </Tab>
            </Tabs>
          </div>
          
          {/* Sidebar com Ficha */}
          <div className="bg-white shadow-lg rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">Ficha Técnica</h2>
            
            <MetadataDisplay data={item.metadata} />
            
            {/* Tags interativas */}
            <div className="flex flex-wrap gap-2 mt-4">
              {item.tags.map(tag => (
                <Link key={tag} href={`/search?tag=${tag}`}>
                  <span className="px-3 py-1 bg-primary-100 rounded-full text-sm">
                    #{tag}
                  </span>
                </Link>
              ))}
            </div>
            
            {/* Busca Semântica Integrada */}
            <div className="mt-6 border-t pt-4">
              <h3 className="font-medium">Pergunte sobre este item</h3>
              <SemanticSearch context={{ itemId: item.id }} />
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  )
}
```

---

## ⚙️ CAMADA 4: BACKEND E SERVIÇOS

### Arquitetura de Backend

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ENDPOINTS                                                                  │
│                                                                             │
│  GET /api/collections          # Lista todas as coleções                   │
│  GET /api/collections/{id}     # Detalhes de uma coleção                   │
│  GET /api/items/{id}           # Detalhes de um item                      │
│  GET /api/items/{id}/manifest  # IIIF Manifest                            │
│  GET /api/items/{id}/usd       # USDZ otimizado para web                 │
│  GET /api/search               # Busca textual                            │
│  POST /api/search/semantic     # Busca semântica (RAG)                   │
│  GET /api/twin/{alaId}         # Dados do digital twin                   │
│  WS /api/twin/stream           # WebSocket para atualizações em tempo real│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  CAMADA DE SERVIÇOS                                                         │
│                                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐                      │
│  │  Metadata Service   │    │  USD Service        │                      │
│  │  (SQLite/PostgreSQL)│    │  (Processing +      │                      │
│  │                     │    │   Optimization)     │                      │
│  └─────────────────────┘    └─────────────────────┘                      │
│                                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐                      │
│  │  Search Service     │    │  Twin Service       │                      │
│  │  (Qdrant Vector DB) │    │  (WebSocket + State)│                      │
│  └─────────────────────┘    └─────────────────────┘                      │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  RAG Service (DeepSeek + Qdrant)                                  │   │
│  │                                                                  │   │
│  │  1. Recebe pergunta do usuário                                   │   │
│  │  2. Gera embedding da pergunta (BGE)                            │   │
│  │  3. Busca itens relevantes no Qdrant                            │   │
│  │  4. Constrói prompt com contexto dos itens                      │   │
│  │  5. Envia para DeepSeek API (pay-per-use)                      │   │
│  │  6. Retorna resposta com citações                                │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Exemplo de Busca RAG

```python
# services/rag_service.py
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from openai import OpenAI  # ou DeepSeek API

class RAGService:
    def __init__(self):
        self.embedder = SentenceTransformer('BAAI/bge-base-en-v1.5')
        self.vector_db = QdrantClient(host="localhost", port=6333)
        self.llm = OpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key="sk-...",
            model="deepseek-v4-flash"
        )
    
    def search_and_answer(self, query: str, context_filter: dict = None):
        # 1. Embedding da pergunta
        query_embedding = self.embedder.encode(query)
        
        # 2. Busca vetorial
        search_result = self.vector_db.search(
            collection_name="acervo",
            query_vector=query_embedding,
            limit=5,
            filter=context_filter
        )
        
        # 3. Monta contexto
        context = []
        for hit in search_result:
            item = hit.payload
            context.append(f"""
            Item: {item['nome']}
            Descrição: {item['descricao_resumo']}
            Tags: {', '.join(item['tags'])}
            """)
        
        # 4. Gera resposta com DeepSeek
        prompt = f"""
        Com base no acervo do museu, responda à pergunta:
        Pergunta: {query}
        
        Contexto relevante:
        {'---'.join(context)}
        
        Cite os itens específicos mencionados.
        """
        
        response = self.llm.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        return {
            "answer": response.choices[0].message.content,
            "sources": [hit.payload['id'] for hit in search_result],
            "confidence": hit.score
        }
```

---

## 🔧 CAMADA 5: FERRAMENTAS E RECOMENDAÇÕES TÉCNICAS

### Stack Tecnológico Recomendado

| Camada | Tecnologia | Justificativa |
|--------|------------|---------------|
| **Processamento** | Python 3.11+ | Melhor suporte para IA, USD, IIIF |
| **Framework Backend** | FastAPI | Rápido, moderno, documentação automática |
| **Banco de Dados** | SQLite (desenvolvimento) / PostgreSQL (produção) | Leve, com suporte a JSON e busca vetorial (pgvector) |
| **Vector DB** | Qdrant (self-hosted) | Open-source, performático, fácil integração |
| **Frontend** | Next.js 14+ | SSR, otimização de imagens, API routes |
| **UI Components** | shadcn/ui + Tailwind CSS | Moderno, acessível, customizável |
| **Viewer 2D (IIIF)** | Mango (ou OpenSeadragon) | Suporte a IIIF, zoom/pan, open-source |
| **Viewer 3D (USD)** | Needle USD (WASM) | Renderiza USD no browser via WebAssembly |
| **Viewer 3D (Alternativa)** | Three.js + USD Web View | Mais controle, comunidade maior |
| **Digital Twin** | Three.js + WebSockets | Renderização em tempo real, interatividade |
| **Busca/IA** | DeepSeek API (pay-per-use) | Custo-benefício, eficiente |
| **Deploy** | Vercel (frontend) + Railway/Render (backend) | Simples, escalável, integração Git |

### Exemplo de Configuração do USD Web Viewer

```typescript
// components/USDViewer.tsx
import { useEffect, useRef } from 'react';
import { USDZViewer } from '@needle-tools/usd';

export function USDViewer({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    const viewer = new USDZViewer(containerRef.current, {
      antialias: true,
      shadows: true,
      background: '#1a1a2e',
      camera: {
        position: [0, 1, 5],
        target: [0, 0, 0]
      }
    });
    
    viewer.load(url).then(() => {
      // Adiciona controles
      viewer.enableControls({
        rotate: true,
        zoom: true,
        pan: false
      });
      
      // Auto-rotation (se configurado)
      if (viewer.autoRotate) {
        viewer.autoRotate = true;
        viewer.autoRotateSpeed = 0.02;
      }
    });
    
    return () => viewer.destroy();
  }, [url]);
  
  return <div ref={containerRef} className="w-full h-[600px] rounded-lg" />;
}
```

### Exemplo de Digital Twin (Museu Virtual)

```typescript
// components/DigitalTwinViewer.tsx
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { USDZLoader } from 'three/addons/loaders/USDZLoader.js';

export function DigitalTwinViewer({ alaId }: { alaId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    // Setup Three.js
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, 800/600, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    
    // Carrega layout da ala (USD)
    const loader = new USDZLoader();
    loader.load(`/assets/alas/${alaId}.usdz`, (usdScene) => {
      scene.add(usdScene);
    });
    
    // WebSocket para robôs em tempo real
    wsRef.current = new WebSocket(`wss://api.museu.com/twin/${alaId}`);
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Atualiza posição dos robôs
      if (data.type === 'robo_update') {
        const robo = scene.getObjectByName(data.id);
        if (robo) {
          robo.position.set(data.x, data.y, data.z);
          robo.rotation.y = data.rotation;
        }
      }
    };
    
    // Loop de renderização
    function animate() {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();
    
    return () => {
      wsRef.current?.close();
      renderer.dispose();
    };
  }, [alaId]);
  
  return <div ref={containerRef} className="w-full h-[600px]" />;
}
```

---

## 🚀 PIPELINE DE DEPLOYMENT

### Fluxo de Deploy Contínuo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD PIPELINE                                      │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │   DEVELOPER  │
  │  (Git Push)  │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  GITHUB ACTIONS / GITLAB CI                                     │
  │                                                                 │
  │  1. Lint e Testes Unitários                                     │
  │  2. Build do Frontend (Next.js)                                │
  │  3. Build do Backend (Python)                                  │
  │  4. Processa acervo (scripts de metadados)                    │
  │  5. Gera assets otimizados (USDZ, imagens WebP)               │
  │  6. Deploy para produção                                        │
  └──────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  PRODUÇÃO                                                       │
  │                                                                 │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
  │  │   VERCEL     │  │   RAILWAY    │  │   S3/CDN     │       │
  │  │ (Frontend)   │  │ (Backend)    │  │ (Assets)     │       │
  │  └──────────────┘  └──────────────┘  └──────────────┘       │
  │                                                                 │
  │  - Frontend: Next.js (SSR/SSG)                                │
  │  - Backend: FastAPI + Qdrant + SQLite                         │
  │  - Assets: Cloudflare R2 / AWS S3 (CDN)                      │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 📊 RESULTADO FINAL: O QUE O USUÁRIO VÊ

### Visão do Website

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🏛️ MUSEU VIRTUAL - ACERVO DIGITAL                                       │
│  ───────────────────────────────────────────────────────────────────────── │
│  [Home] [Coleções] [Digital Twin] [Busca IA] [Sobre]                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  DESTAQUES DO ACERVO (Carrossel 3D)                                      │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  [Vaso Canopo]  [Sarcófago]  [Anfora Grega]  [Estátua]          │    │
│  │  (3D interativo com rotação automática)                          │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  COLEÇÕES                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │  Coleção     │  │  Coleção     │  │  Coleção     │                    │
│  │  Egípcia     │  │  Grega       │  │  Romana      │                    │
│  │  (12 itens)  │  │  (8 itens)   │  │  (5 itens)   │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  EXPERIÊNCIA IMERSIVA (Digital Twin da Ala)                               │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  [Renderização 3D da Ala com robôs interativos]                 │    │
│  │                                                                   │    │
│  │  ● Clique em um item para ver detalhes                          │    │
│  │  ● Robô-guia percorre a ala (movimento em tempo real)           │    │
│  │  ● Exibe informações contextuais (hover)                       │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  BUSCA INTELIGENTE (RAG)                                                  │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  [🔍 Pergunte sobre o acervo: "Quais vasos canopos existem?"]   │    │
│  │                                                                   │    │
│  │  Resposta: "Existem 3 vasos canopos: ..."                        │    │
│  │                                                                   │    │
│  │  Fontes:                                                          │    │
│  │  • Vaso Canopo com Cabeça de Falcão (EG-001)                     │    │
│  │  • Vaso Canopo com Cabeça de Chacal (EG-002)                    │    │
│  │  • Vaso Canopo com Cabeça de Babuíno (EG-003)                   │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 💎 RESUMO DA ARQUITETURA

### Pontos-Chave

1. **Pipeline Modular**: Cada etapa (metadados, IIIF, USD, indexação) é independente
2. **Sem WordPress**: Usa gerador de site estático + APIs dedicadas
3. **USD como Container Universal**: Unifica assets 2D, 3D e metadados
4. **IIIF para Imagens**: Padroniza visualização de imagens 2D
5. **RAG com DeepSeek**: Busca semântica integrada (pay-per-use)
6. **Digital Twins**: Renderização 3D em tempo real com WebSockets
7. **Escalável**: Cada camada pode ser escalada independentemente

### Próximos Passos para Implementação

1. **Setup Inicial**:
   - Instalar Python 3.11+ e Node.js 18+
   - Configurar ambiente virtual (Python)
   - Inicializar projeto Next.js

2. **Processamento do Acervo**:
   - Criar scripts de leitura de TOML
   - Implementar validação de esquema
   - Gerar primeiros manifests IIIF

3. **Frontend Base**:
   - Criar layout com Tailwind/shadcn
   - Implementar USD Viewer com Needle
   - Implementar IIIF Viewer com Mango

4. **Busca IA**:
   - Configurar Qdrant
   - Implementar embedding dos metadados
   - Integrar com DeepSeek API

5. **Digital Twins**:
   - Setup Three.js para renderização 3D
   - Implementar WebSocket server
   - Criar lógica de movimento de robôs

6. **Deploy**:
   - Configurar Vercel para frontend
   - Configurar Railway/Render para backend
   - Configurar S3/CDN para assets

Precisa que eu detalhe alguma parte específica ou ajude a começar a implementação de algum componente?

-------------------------------------------------------------------------------------------------------------------

A sua ideia de unificar tudo no arquivo USD é um excelente pensamento para simplificar a arquitetura, e a resposta é: **sim, é totalmente viável e traz ganhos significativos**. Você pode, e provavelmente deve, incorporar os metadados da ficha diretamente no arquivo USDA.

Vou explicar os motivos e como isso funcionaria na prática, com base nas informações disponíveis.

### Por que usar o USDA como fonte única?

A grande vantagem de usar o USDA é a **centralização e a integridade dos dados**.

1.  **Encapsulamento Total**: O arquivo USD se torna a "fonte da verdade" para aquele item. Ele contém não apenas o modelo 3D (ou a referência a ele), mas também as imagens e todos os metadados descritivos. Isso elimina a necessidade de manter arquivos `.toml` ou `.json` separados e sincronizados.
2.  **Acesso Universal**: Você pode acessar esses metadados tanto por trás, com scripts Python para processamento, quanto no frontend, diretamente no navegador.
    *   **Python (Backend/Processamento)**: A biblioteca oficial do USD (`pxr.Usd`) tem funções nativas para ler e escrever metadados em `customData`. Você pode usar `prim.GetCustomDataByKey()` para recuperar um dicionário inteiro com os dados da sua ficha ou `prim.SetCustomDataByKey()` para escrevê-los.
    *   **JavaScript (Frontend/Website)**: Sim, scripts JavaScript podem ler arquivos USDA. Bibliotecas como o `@loaders.gl/scene` e o `@dotdotdash/stunner-usd` permitem carregar e parsear arquivos USD (incluindo USDA/USDC/USDZ) no navegador, dando acesso à estrutura da cena e, consequentemente, aos metadados.

### Como integrar as "fichas" no USDA

A maneira padrão e recomendada para fazer isso é usando o dicionário `customData` de um `Usd.Prim` (o nó que representa seu objeto, como o "Vaso Canopo").

Seu arquivo `asset.usda` poderia ser estruturado assim:

```usda
#usda 1.0

def Xform "Vaso_Canopo" (
    customData = {
        dictionary museu = {
            string id = "EG-001"
            string nome = "Vaso Canopo com Cabeça de Falcão"
            string data = "650 a.C."
            string cultura = "Egípcia"
            dictionary dimensoes = {
                float altura = 45
                float largura = 18
            }
            string[] tags = ["religiao", "mumificacao"]
            string preview_imagem = "images/front.jpg"
        }
    }
)
{
    # Referência ao arquivo GLB com o modelo 3D
    def "Modelo" (references = </path/to/vaso.glb>) {
    }
}
```

Com essa abordagem, você mantém todos os dados do acervo dentro do próprio arquivo de cena.

### Vantagens Práticas dessa Unificação

Essa estratégia se alinha perfeitamente com a sua visão de simplificar e integrar:

*   **Pipeline Simplificado**: Seus scripts de processamento não precisam mais navegar por pastas para ler arquivos TOML separados. Eles apenas abrem o arquivo `.usda` e extraem tudo o que precisam. Um único pipeline pode processar tanto a geometria/aparência quanto os metadados.
*   **Maior Integridade dos Dados**: A ficha técnica e o modelo 3D nunca ficam dessincronizados, pois vivem no mesmo arquivo. Você não corre o risco de atualizar um e esquecer o outro.
*   **Mais Poder no USD**: Ao ter os metadados como `customData`, você pode usar funcionalidades avançadas do USD, como os **`variants`**. Por exemplo, você poderia usar `variants` para criar diferentes "exploded views" do vaso ou para alternar entre suas texturas, tudo controlado pelos dados que você mesmo inseriu na ficha.

### Considerações Finais

*   **Suporte em JavaScript**: É uma área que está amadurecendo rapidamente. Ferramentas como `tinyusdz` já possuem bindings para WebAssembly (WASM), e `loaders.gl` já oferece um `USDLoader` funcional para USDA, o que torna a leitura desses metadados no frontend perfeitamente possível.
*   **Ferramentas Externas**: Embora ferramentas como o **CollectionBuilder** ou **Canopy IIIF** esperem arquivos CSV ou JSON, você pode usar um script para extrair os metadados do USDA e gerar esses formatos, mantendo a fonte única e consistente.

**Conclusão:** Incorporar os metadados diretamente no USDA não só é possível como é uma prática mais moderna e alinhada com a filosofia de dados unificados do USD. É uma escolha que traz mais simplicidade, integridade e poder para seu sistema.

Se você quiser explorar como fazer a leitura desses metadados no frontend com JavaScript ou no backend com Python, posso detalhar mais esses passos.

----------------------------------------------------------------------------------------------------------------------------------------------------------

