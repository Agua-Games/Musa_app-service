# 🏛️ Museu Digital 3D - Documento Técnico (Design Document)

## Sumário Executivo

Este documento descreve a arquitetura técnica completa do serviço **Museu Digital 3D**, uma plataforma modular para digitalização, catalogação, preservação e exibição interativa de acervos museológicos. O sistema é **contract-first**: a camada de acervo é definida por um contrato de ficha versionado (JSON Schema) e implementada de forma **backend-agnóstica**, sem dependência de WordPress (ver §2.1). A modelagem 3D usa **OpenUSD** como formato-fonte e **glTF/GLB** como formato de entrega web, com visualização imersiva via **Three.js** ou **Omniverse Kit App Streaming**. A plataforma inclui assistentes de IA conversacionais integrados, capazes de responder perguntas sobre o acervo tanto no frontend web quanto em quiosques físicos com reconhecimento de fala.

---

## 1. Visão Geral da Arquitetura

### 1.1 Diagrama de Arquitetura de Alto Nível

```mermaid
flowchart TB
    subgraph Clients["Camada de Clientes"]
        Web["Website/Frontend<br/>(HTML + JS + Three.js)"]
        Kiosk["Quiosques Físicos<br/>(Displays Interativos + STT/TTS)"]
        Mobile["App Mobile<br/>(Opcional)"]
    end

    subgraph CDN["Camada de Distribuição"]
        CloudFront["CloudFront / CDN<br/>(Cache de Assets 3D)"]
    end

    subgraph Backend["Backend Principal (contract-first)"]
        Catalog["Acervo API (serviço separado)<br/>- Fichas por contrato (JSON Schema)<br/>- Coleções / Subcoleções<br/>- Asset refs agnósticos de formato<br/>- Ingestão CSV / JSON / TOML"]
        Admin["Painel de Controle<br/>(Módulos, Faturamento)"]
        Queue["Fila de Demandas<br/>(Agentes Automáticos)"]
    end

    subgraph Storage["Camada de Armazenamento"]
        S3["AWS S3 / Azure Blob<br/>- Fotos (JPG/PNG)<br/>- Modelos 3D (GLB/USD)<br/>- Digital Twins"]
        DB["Banco de Dados<br/>(MySQL/PostgreSQL)"]
        VectorDB["Banco Vetorial<br/>(FAISS / Pinecone)<br/>- Embeddings do Acervo"]
    end

    subgraph Processing["Camada de Processamento"]
        OCR["Pipeline de OCR + IA<br/>(Folio-OCR, docling)"]
        USD["Pipeline USD<br/>(OpenUSD Exchange SDK)"]
        Streaming["Omniverse Kit App Streaming<br/>(para Digital Twins)"]
        RAG["Pipeline RAG<br/>(Recuperação + Geração)"]
    end

    subgraph AI["Camada de IA"]
        LLM["Modelo de Linguagem<br/>(GPT-4 / LLaMA)"]
        STT["Speech-to-Text<br/>(Whisper / ASR)"]
        TTS["Text-to-Speech<br/>(Edge TTS / Coqui)"]
        Embeddings["Gerador de Embeddings<br/>(CLIP / Sentence-BERT)"]
    end

    subgraph External["Integrações Externas"]
        Scanner["Serviços de Escaneamento 3D"]
    end

    Web --> CloudFront
    Kiosk --> CloudFront
    Kiosk --> STT
    Kiosk --> TTS
    Mobile --> CloudFront
    CloudFront --> Catalog
    CloudFront --> S3
    Admin --> Backend
    Queue --> Processing
    Catalog --> S3
    Catalog --> DB
    OCR --> LLM
    USD --> S3
    USD --> Streaming
    Scanner --> USD
    
    RAG --> VectorDB
    RAG --> LLM
    RAG --> Catalog
    Web --> RAG
    Kiosk --> RAG
    STT --> RAG
    RAG --> TTS
```

---

## 2. Componentes Técnicos

### 2.1 Camada de Acervo (contract-first, backend-agnóstica)

A camada de acervo **não depende de WordPress**. Ela é definida por um **contrato de
ficha** versionado (`schemas/ficha.schema.json`, ver §3.2) e por uma **API de acervo**
estável (§6.1). A implementação que materializa esse contrato é trocável sem migração de
dados, porque a fonte de verdade é o diretório `acervo/` em disco (pastas = coleções e
subcoleções; arquivos = fichas + assets), versionado em Git.

#### 2.1.1 Princípio: contrato único, implementações múltiplas

| Aspecto | Definição |
|---------|-----------|
| **Contrato** | `ficha.json` validado por JSON Schema, com campos de asset agnósticos de formato (§3.2) |
| **Fontes de verdade** | `acervo/` (estrutura de pastas + fichas) e os assets 3D (USD como arquivo-fonte) |
| **API** | Recursos `/collections`, `/collections/{id}/items`, `/items/{id}`, `/schema`, `/search` (§6.1) |
| **Implementação** | Detalhe substituível — não vaza para o contrato nem para o frontend |

#### 2.1.2 Implementações por estágio

| Estágio | Implementação | Dependências | Quando usar |
|---------|---------------|--------------|-------------|
| **MVP** | índice gerado em build-time (`catalog.json` + SQLite) sobre `acervo/`; site estático | nenhuma (sem PHP, sem MySQL, sem WordPress) | prototipação rápida do frontend (WebGL/WebAssembly) e validação do contrato antes de investir em infraestrutura |
| **Escala** | **Payload** (TypeScript + Next.js, PostgreSQL ou MongoDB) expondo REST/GraphQL sobre os mesmos campos | Node.js + PostgreSQL (+ `pgvector` para RAG) | quando houver edição concorrente, papéis/permissões e múltiplos museus |
| **Padrões** | Omeka S (LAMP, GPL-3.0) ou CollectiveAccess 2.0 (PHP 8.2+, MySQL, API GraphQL) | PHP + MySQL | quando o cliente exigir padrões museológicos (OAI-PMH, controle de autoridade, exportação BagIT) |

A passagem entre estágios usa sempre o mesmo caminho: **CSV/JSON gerado a partir das
fichas** (§6.2), o que mantém baixo o custo de troca de backend.

> ⚠️ **Nota de licenciamento.** Omeka S e CollectiveAccess são GPL-3.0: o copyleft só é
> acionado ao **distribuir** o software, não pela hospedagem como serviço. Backends
> "source-available" com limite de receita (ex.: Directus/MSCL) foram descartados por
> risco comercial para um serviço vendido em tiers.

#### 2.1.3 Estrutura de Dados

| Entidade | Descrição | Exemplo de Uso |
|----------|-----------|----------------|
| **Coleção** | Agrupamento lógico de itens (uma pasta de primeiro nível em `acervo/`) | "Coleção de Esculturas Gregas" |
| **Subcoleção** | Agrupamento dentro de uma coleção (mesma navegação do acervo) | "Cerâmica Ática" |
| **Item** | Uma peça do acervo | "Vaso Grego - Séc. V a.C." |
| **Metadado** | Campo de informação customizável | "Autor", "Data", "Material", "Dimensões" |
| **Taxonomia** | Hierarquia de termos para categorização | "Período: Arcaico → Clássico → Helenístico" |

#### 2.1.4 Extensibilidade

- **Campos novos sem migração estrutural:** a "ficha universal" agrega metadados e a UI
  consulta apenas os campos que cada coleção declara usar.
- **Coleções e campos em Payload:** os `collections` e `fields` espelham o JSON Schema,
  mantendo o contrato como fonte das definições.
- **Endpoints customizados:** o Payload permite endpoints próprios para ingestão em lote
  e para as etapas do pipeline de catalogação.
- **Modo padrões:** exportadores (CSV/XML/OAI-PMH) rodam como etapa de build, sem acoplar
  o frontend ao catálogo museológico.

---

### 2.2 Camada de Modelagem 3D: OpenUSD e glTF/GLB

> Implementação detalhada — estrutura do `asset.usda`, scripts de extração, viewer e digital
> twin em tempo real: `docs/Musa_design implementacao-usd.md`.

#### 2.2.1 OpenUSD (Universal Scene Description)

**Por que USD?**
- Padrão da indústria (Pixar, NVIDIA, Apple, Adobe, Autodesk)
- Suporte nativo a metadados customizados (Custom Attributes, Custom Schemas)
- Referenciamento e Payloads para cenas complexas
- Animações e variações ("Exploded View")

**Ferramentas para Desenvolvimento:**

1. **OpenUSD Exchange SDK (Python):**
   - Disponível como pacote PyPI: `pip install usd-exchange`.
   - Fornece APIs de alto nível para criação e manipulação de stages USD.

2. **Módulos do SDK:**
   - `usdex.core`: Funções de alto nível para criar/editar stages USD.
   - `usdex.rtx`: Utilitários para materiais MDL e shaders para RTX Renderer.
   - `usdex.test`: Ferramentas de teste para validação de dados USD.

3. **Assistentes IA para USD:**
   - O ecossistema Omniverse Kit oferece **Chat USD**, um assistente IA integrado que permite interação em linguagem natural com cenas USD, incluindo geração de código USD, busca de assets, análise de cena e edição em tempo real através de conversação .
   - A ferramenta **openusd-mcp** (Model Context Protocol) permite que assistentes como Claude, ChatGPT ou Cursor leiam, inspecionem e manipulem cenas USD diretamente, com ferramentas como `usd_inspect`, `usd_get_prim`, `usd_list_variants` e `usd_set_variant` .

#### 2.2.2 glTF/GLB para Visualização Web

**Vantagens para Web:**
- Formato leve, otimizado para entrega via CDN.
- Suporte nativo em Three.js, Babylon.js, etc.
- Compressão Draco/Meshopt disponível.

**Estimativas de Tamanho:**

| Tipo de Asset | Tamanho GLB (otimizado) | Tamanho USD (usda) | Fator de Aumento |
|---------------|------------------------|---------------------|------------------|
| Objeto simples (ex: vaso) | 2-5 MB | 20-50 MB | 10× |
| Escultura detalhada | 10-30 MB | 100-300 MB | 10× |
| Cena com múltiplos objetos | 50-150 MB | 500 MB - 1 GB | 10× |

**Estratégia Híbrida:**
- **Arquivo `.usd`:** Fonte de verdade, com metadados, animações e payloads. Armazenado para edição e arquivamento.
- **Arquivo `.glb`:** Versão otimizada para entrega web, gerada via pipeline de conversão (`usd2gltf`).
- **Payloads USD:** Referenciam `.glb` dentro de uma cena USD.

---

### 2.3 Pipeline de Catalogação Automatizada

#### 2.3.1 Fluxo de Trabalho

```mermaid
flowchart LR
    subgraph Input["Entrada"]
        Fichas["Fichas Físicas<br/>(Scans/Photos)"]
    end
    
    subgraph OCR["Etapa 1: OCR"]
        Folio["Folio-OCR<br/>(Layout + Texto)"]
        OutputOCR["Texto Bruto +<br/>Estrutura da Página"]
    end
    
    subgraph IA["Etapa 2: IA"]
        LLM["Modelo de Linguagem<br/>(GPT-4 / Qwen)"]
        Prompt["Prompt Template<br/>+ Esquema de Metadados"]
    end
    
    subgraph Output["Saída"]
        CSV["CSV/JSON<br/>Estruturado"]
        Embeddings["Embeddings<br/>para RAG"]
    end
    
    subgraph Import["Etapa 3: Ingestão"]
        Catalog["Acervo API<br/>Valida + Indexa Lote"]
        VectorDB["Banco Vetorial"]
    end
    
    Fichas --> Folio
    Folio --> OutputOCR
    OutputOCR --> LLM
    Prompt --> LLM
    LLM --> CSV
    LLM --> Embeddings
    CSV --> Catalog
    Embeddings --> VectorDB
```

#### 2.3.2 Ferramentas de OCR Recomendadas

| Ferramenta | Modo Headless | Batch | Diferencial |
|------------|---------------|-------|-------------|
| **Folio-OCR** | ✅ (Docker/CLI) | ✅ | Análise de layout com GLM-OCR e PP-DocLayoutV3 |
| **docling-OCR-OnnxTR** | ✅ (pip com flags headless) | ✅ | Otimizado para CPU/GPU/OpenVINO |
| **vlm4ocr** | ✅ (CLI Python) | ✅ | Usa VLMs (Qwen, LLaVa) para OCR |

**Exemplo de Uso (Folio-OCR via Docker):**
```bash
docker run -v /path/to/scans:/input -v /path/to/output:/output \
  folio-ocr --batch /input --output /output
```

#### 2.3.3 Agente IA para Correção e Estruturação

**Prompt Template:**
```
"Receba o seguinte texto OCR, que pode conter erros de reconhecimento:
[texto_ocr]

Extraia as informações e formate-as de acordo com o seguinte esquema de metadados (ficha universal):

Campos obrigatórios:
- titulo: string
- autor: string
- data: string (AAAA ou AAAA-MM-DD)
- material: string
- dimensoes: string
- descricao: text
- colecao: string
- tags: array de strings

Regras:
1. Corrija erros óbvios de ortografia
2. Inferia datas incompletas com base no contexto histórico
3. Saída em formato JSON
4. Gere também um embedding semântico do conteúdo para indexação vetorial

Saída esperada:
{ "titulo": "...", "autor": "...", "embedding": [...], ... }
```

---

### 2.4 Sistema de Assistente IA para Perguntas sobre o Acervo

#### 2.4.1 Visão Geral

Nosso serviço inclui um **assistente IA conversacional integrado**, capaz de responder perguntas sobre o acervo em linguagem natural, tanto no frontend web quanto em quiosques físicos. Este sistema utiliza **Retrieval-Augmented Generation (RAG)** combinado com Large Language Models para fornecer respostas precisas e contextualmente relevantes.

#### 2.4.2 Arquitetura RAG

```mermaid
flowchart TB
    subgraph Query["Consulta do Usuário"]
        Text["Pergunta em Texto"]
        Voice["Pergunta por Voz"]
    end
    
    subgraph Input["Processamento da Consulta"]
        STT["Speech-to-Text<br/>(Whisper / ASR)"]
        EmbedQuery["Gerador de Embedding<br/>(Sentence-BERT)"]
    end
    
    subgraph Retrieval["Recuperação de Contexto"]
        VectorDB["Banco Vetorial<br/>(FAISS / Pinecone)"]
        Search["Busca por Similaridade"]
        Context["Contexto Relevante<br/>(Fichas + Metadados)"]
    end
    
    subgraph Generation["Geração da Resposta"]
        Prompt["Prompt Template<br/>+ Contexto"]
        LLM["LLM<br/>(GPT-4 / LLaMA)"]
        Response["Resposta em Texto"]
    end
    
    subgraph Output["Saída"]
        TTS["Text-to-Speech<br/>(Coqui / Edge TTS)"]
        Display["Exibição na Tela"]
    end
    
    Voice --> STT
    Text --> EmbedQuery
    STT --> EmbedQuery
    EmbedQuery --> VectorDB
    VectorDB --> Search
    Search --> Context
    Context --> Prompt
    Prompt --> LLM
    LLM --> Response
    Response --> Display
    Response --> TTS
    TTS --> Kiosk["Áudio no Quiosque"]
```

#### 2.4.3 Componentes do Sistema

**1. Speech-to-Text (Reconhecimento de Fala)**

Para quiosques físicos, o sistema utiliza modelos de reconhecimento de fala para capturar perguntas de visitantes, incluindo crianças.

- **Tecnologias:** Whisper (OpenAI), modelos ASR especializados
- **Otimizações:** Em ambientes ruidosos como museus, sistemas de reconhecimento de fala para quiosques podem alcançar melhorias significativas de precisão com técnicas de correção de palavras-chave baseadas em RAG, elevando a acurácia de 45,71% para 91,43% 
- **Filtros de Ruído:** Microfones ultra-direcionais, filtros bandpass e funções de remoção de ruído em tempo real mantêm altas taxas de reconhecimento mesmo em ambientes com múltiplas conversas simultâneas e música de fundo 

**2. Recuperação de Contexto (RAG)**

O sistema consulta um banco vetorial contendo embeddings de todas as fichas do acervo, metadados e descrições.

- **Tecnologias:** FAISS, Pinecone, CLIP (para consultas multimodais)
- **Indexação:** Cada item do acervo é convertido em embedding semântico durante a catalogação
- **Busca:** Similaridade por cosseno para encontrar os documentos mais relevantes

**3. Geração de Respostas (LLM)**

O modelo de linguagem recebe o contexto recuperado e a pergunta do usuário, gerando uma resposta natural e informativa.

- **Tecnologias:** GPT-4, LLaMA 3, modelos open-source
- **Personalização:** Sistemas RAG multimodais podem integrar rastreamento ocular, imagens das obras e consultas de voz para gerar explicações personalizadas e adaptadas ao interesse do visitante 

**4. Text-to-Speech (Síntese de Voz)**

Para quiosques físicos, a resposta gerada é convertida em áudio.

- **Tecnologias:** Coqui TTS, Edge TTS, modelos open-source
- **Customização:** Possibilidade de múltiplas vozes (adulto, criança, diferentes idiomas)

#### 2.4.4 Exemplos de Uso

**Cenário Web:**
```
Visitante: "Quais vasos gregos do século V a.C. estão no acervo?"
Sistema: [Busca no banco vetorial] → [Gera resposta com LLM]
Resposta: "Temos 3 vasos gregos do século V a.C.: um ânfora de figuras vermelhas atribuída a Eufrônio, uma cratera de figuras negras e um lecito de fundo branco. Posso mostrar detalhes de cada um."
```

**Cenário Quiosque Físico (com voz):**
```
Criança: [Fala ao quiosque] "O que é esse vaso?"
Sistema: [STT → RAG → LLM → TTS]
Resposta (áudio + texto): "Este é um vaso grego chamado ânfora. Ele era usado para carregar vinho ou azeite. Veja as figuras pintadas - elas contam a história de um herói chamado Aquiles!"
```

#### 2.4.5 Integração com o Ecossistema USD

Para museus com digital twins em 3D, o assistente IA pode ser estendido para interagir diretamente com cenas USD:

- O **Chat USD** (Omniverse Kit) permite que assistentes IA executem comandos em linguagem natural para manipular cenas USD, como "mostre a vista explodida desta peça" ou "destaque todas as peças de cerâmica na sala" 
- Ferramentas como **openusd-mcp** podem ser integradas para que o assistente leia metadados diretamente dos arquivos USD, respondendo perguntas como "Qual o material desta peça?" ou "Que variantes estão disponíveis?" 

#### 2.4.6 Benefícios do Assistente IA

| Benefício | Descrição |
|-----------|-----------|
| **Acessibilidade** | Visitantes com deficiência visual podem ouvir descrições detalhadas |
| **Engajamento Infantil** | Respostas adaptadas para crianças, com linguagem simples e interativa |
| **Redução de Custos** | Quiosques IA reduzem a necessidade de guias humanos em horários de pico |
| **Experiência Personalizada** | O sistema pode adaptar respostas com base no perfil do visitante (criança, adulto, pesquisador)  |
| **Disponibilidade 24/7** | O assistente está sempre disponível, mesmo fora do horário de funcionamento do museu |
| **Multilíngue** | Suporte a múltiplos idiomas para turistas internacionais |

---

### 2.5 Camada de Streaming: Omniverse Kit App Streaming

#### 2.5.1 Visão Geral

O **Omniverse Kit App Streaming** é uma solução para transmissão de aplicações 3D de alta performance via navegador.

**Arquitetura:**
- **Kubernetes:** Cluster com nós GPU para escalabilidade.
- **Microserviços:** Gerenciam registro, configuração e lifecycle de apps Kit.
- **API Gateway:** Gerencia acesso seguro e load balancing.

#### 2.5.2 Recursos da Versão 108.0+

- **Multi-Stream:** Suporte a múltiplos streams (entrada e saída) do mesmo processo.
- **Performance:** Streaming 4K@60fps.
- **Observabilidade:** Métricas QoS e status do streaming (initializing, ready, connected).
- **Casos de Uso:** Direct Connections, Kit App Streaming, NVCF/OVC 2.0, Cloud Hosted, Self Hosted.

#### 2.5.3 Integração com Frontend

```javascript
// Exemplo de integração com o player de streaming
const streamUrl = `https://streaming.omniverse.com/session/${sessionId}`;
const player = new OmniverseStreamPlayer({
    url: streamUrl,
    container: document.getElementById('player-container'),
    onReady: () => console.log('Stream ready'),
    onError: (err) => console.error('Stream error', err)
});
```

---

### 2.6 Frontend: Website e Visualização 3D

#### 2.6.1 Tecnologias Recomendadas

| Camada | Tecnologia | Função |
|--------|------------|--------|
| **Framework** | React / Vue.js / HTML Puro | Interface do usuário |
| **Visualização 3D** | Three.js + WebGL | Carregamento e renderização de GLB |
| **Streaming** | Omniverse Kit App Streaming | Digital Twins complexos |
| **CDN** | CloudFront / Azure CDN | Cache de assets 3D |
| **Chat IA** | API REST + WebSockets | Interface do assistente conversacional |

#### 2.6.2 Otimização de Performance (Three.js)

**Recursos para Modelos Leves:**
- **InstancedMesh:** Para objetos repetidos (ex: estantes, colunas).
- **LOD (Level of Detail):** Alterna entre versões de alta/baixa resolução baseado na distância da câmera.
- **Merge Geometry:** Combina múltiplas geometrias para reduzir draw calls.
- **Frustum Culling:** Habilita recorte de objetos fora do campo de visão.

**Exemplo de LOD:**
```javascript
const lod = new THREE.LOD();
const highRes = new THREE.Mesh(highResGeometry, material);
const lowRes = new THREE.Mesh(lowResGeometry, material);
lod.addLevel(highRes, 0);   // Até 0 unidades: alta resolução
lod.addLevel(lowRes, 50);   // De 50 unidades: baixa resolução
scene.add(lod);
```

#### 2.6.3 Integração com a API do Acervo

**Exemplo de Consulta à API:**
```javascript
// Buscar itens de uma coleção
const response = await fetch(`${ACERVO_API}/collections/${collectionId}/items`);
const data = await response.json();

// Para cada item, resolver o asset 3D de forma agnóstica de formato
const asset = item.model_primary;        // ex.: "vaso_grego_vc.glb"
if (asset) {
    loadModel(asset, item.model_viewer); // three_js | usd_wasm | kit_stream
}
```

#### 2.6.4 Interface do Assistente IA

```html
<!-- Exemplo de componente de chat IA no frontend -->
<div class="ai-assistant">
    <div class="chat-window" id="chatMessages">
        <!-- Mensagens aparecem aqui -->
    </div>
    <div class="input-area">
        <input type="text" id="userQuestion" placeholder="Pergunte sobre o acervo...">
        <button onclick="askAssistant()">Enviar</button>
        <button onclick="startVoice()">🎤 Perguntar por Voz</button>
    </div>
</div>
```

```javascript
// Função para enviar pergunta ao assistente
async function askAssistant() {
    const question = document.getElementById('userQuestion').value;
    const response = await fetch('/api/assistant/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, context: { museumId, collectionId } })
    });
    const data = await response.json();
    displayResponse(data.answer, data.suggested_artifacts);
}
```

---

## 3. Modelo de Dados

### 3.1 Estrutura do "Asset Watertight" (GLB no MVP; USD para arquivamento e edição)

> Exemplo completo de `asset.usda` — metadados no default prim, variantes, payloads e
> anotações: `docs/Musa_design implementacao-usd.md` §3.

```yaml
Asset:
  - Nome: "vaso_grego_vc"
  - Formato: USD (usda/usdc) + GLB (cópia otimizada)
  - Estrutura USD:
    - /DefaultPrim
      - metadados: {
          "asset_id": "VASO-001",
          "titulo": "Vaso Grego - Séc. V a.C.",
          "autor": "Desconhecido",
          "data": "-500",
          "material": "Cerâmica",
          "dimensoes": "30cm x 20cm"
        }
      - geometry:
        - mesh.usd (geometria principal)
        - textures.usd (texturas difusas, normais)
        - variants: {
            "exploded_view": "/ExplodedView",
            "normal": "/NormalView"
          }
      - payloads: (opcional, para peças compostas)
        - "/Fragmentos/Fragmento01.usd"
  - Export:
    - glb_otimizado: "vaso_grego_vc.glb"  # Entrega web (obrigatório no MVP)
    - usd_arquivo: "vaso_grego_vc.usda"   # Arquivamento/edição (opcional; premium)
    - ficha_normalizada: "ficha.json"     # Extraída do USD; validada pelo JSON Schema
    - embedding: [0.123, 0.456, ...]      # Para busca semântica
```

### 3.2 Campos da Ficha (agnósticos de backend)

> O contrato é único e versionado em `schemas/ficha.schema.json`. A implementação que o
> armazena é trocável (§2.1.2): índice build-time (MVP), Payload (escala) ou catálogo
> museológico (padrões). Os nomes de campo abaixo são estáveis.

| Campo | Tipo | Origem | Descrição |
|-------|------|--------|-----------|
| `asset_id` | Texto | ficha | Identificador único do asset |
| `titulo` | Texto | ficha | Nome da peça |
| `autor` | Texto | ficha | Autor/Criador |
| `data` | Data | ficha | Data de criação/período |
| `material` | Texto | ficha | Material predominante |
| `dimensoes` | Texto | ficha | Dimensões físicas |
| `descricao` | Texto Longo | ficha | Descrição detalhada |
| `colecao` | Taxonomia | ficha | Coleção a que pertence |
| `tags` | Taxonomia | ficha | Palavras-chave |
| `model_primary` | URL | Pipeline | Asset que o frontend carrega hoje (ex.: `.glb`) |
| `model_source` | URL | Pipeline | Asset-fonte para edição/arquivamento (ex.: `.usda`), opcional |
| `model_formats` | Array | Pipeline | Formatos disponíveis: `["glb"]`, `["glb","usd"]`, `["glb","usd","usdz"]` |
| `model_viewer` | Seleção | Pipeline | `three_js` \| `usd_wasm` \| `kit_stream` |
| `digital_twin_sala` | URL | Pipeline | Link para digital twin da sala |
| `model_status` | Seleção | Automático | `available`, `processing`, `unavailable` |
| `embedding` | Array | Pipeline | Embedding semântico para RAG |

---

## 4. Infraestrutura e Custos

### 4.1 Provedores de Nuvem Recomendados

| Provedor | Armazenamento (por GB) | Egress (por GB) | Diferencial |
|----------|------------------------|-----------------|-------------|
| **AWS S3 (us-east-1)** | $0.023 (Standard) | $0.09 (primeiros 10 TB) | CDN integrado (CloudFront), ampla adoção |
| **Azure Blob (China)** | ¥0.1484 (~$0.021) (Hot) | Consultar tabela de preços | Melhor para clientes na China |

### 4.2 Estimativa de Custos Mensais

> ⚠️ **Nota:** Os valores abaixo são estimativas iniciais baseadas em preços de provedores de nuvem (us-east-1, Julho 2026) e estão sujeitos a modificação após análise detalhada de requisitos específicos do cliente e variações regionais de preço.

#### Cenário: Museu Médio (5.000 peças, 10% em 3D)

| Item | Capacidade | Custo Mensal |
|------|------------|--------------|
| **Armazenamento S3** | 500 GB (dados + modelos) | ~$11.50 ($0.023/GB) |
| **Armazenamento Glacier (backup)** | 1 TB (arquivamento) | ~$0.99 ($0.00099/GB) |
| **Egress (tráfego)** | 500 GB/mês | ~$36.00 ($0.09/GB, primeiros 100 GB free) |
| **Solicitações GET** | 5M/mês | ~$2.00 ($0.0004/1000) |
| **Banco Vetorial (FAISS + instância)** | 1 GB | ~$50/mês (estimado) |
| **API de LLM (RAG)** | 10.000 consultas/mês | ~$50/mês (GPT-4) |
| **Total Estimado** | | **~$150.49/mês** |

#### Cenário: Grande Museu (50.000 peças, 20% em 3D)

| Item | Capacidade | Custo Mensal |
|------|------------|--------------|
| **Armazenamento S3** | 2 TB (dados + modelos) | ~$46.00 |
| **Armazenamento Glacier (backup)** | 5 TB (arquivamento) | ~$4.95 |
| **Egress (tráfego)** | 2 TB/mês | ~$171.00 (primeiros 10 TB) |
| **Solicitações GET** | 20M/mês | ~$8.00 |
| **Banco Vetorial** | 5 GB | ~$150/mês (estimado) |
| **API de LLM (RAG)** | 100.000 consultas/mês | ~$500/mês (GPT-4) |
| **Total Estimado** | | **~$879.95/mês** |

### 4.3 Custo de Digitalização (One-Time)

> ⚠️ **Nota:** Valores estimados com base em referências de mercado para serviços de escaneamento 3D. Custos finais dependem da complexidade, tamanho das peças e localização geográfica.

| Serviço | Custo por Peça | Inclui |
|---------|----------------|--------|
| **Scan 3D (on-site)** | A partir de $85 (~R$ 470) | Escaneamento, modelagem base, otimização web |
| **Touch-up 3D + Upload** | ~$18 (~R$ 100) | Ajustes de textura, otimização GLB, upload |

---

## 5. Pipeline de Desenvolvimento e Implantação

### 5.1 Fluxo de Trabalho de Desenvolvimento

```mermaid
flowchart LR
    Dev["Desenvolvedor"] --> Git["GitHub/GitLab"]
    Git --> CI["CI/CD Pipeline<br/>(GitHub Actions)"]
    CI --> Test["Testes Automatizados"]
    Test --> Build["Build & Package"]
    Build --> Registry["Container Registry<br/>(Docker Hub/ECR)"]
    Registry --> K8s["Kubernetes Cluster"]
    K8s --> Staging["Staging"]
    K8s --> Prod["Produção"]
```

### 5.2 Implantação da Camada de Acervo

**MVP (sem banco de dados):** a camada de acervo é o próprio repositório de documentos —
pastas `acervo/<colecao>/<peca>/` com `ficha.json` + `model.glb`. O build valida as fichas
contra o contrato, gera `catalog.json` e o índice vetorial, e publica o site estático.

**Escala (Payload sobre PostgreSQL + pgvector):**

```yaml
# docker-compose.yml (exemplo)
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: musa
      POSTGRES_PASSWORD: secret
    volumes:
      - db_data:/var/lib/postgresql/data
  acervo:
    build: ./services/acervo
    environment:
      DATABASE_URI: postgres://postgres:secret@postgres:5432/musa
      PAYLOAD_SECRET: change-me
    ports:
      - "3000:3000"
    depends_on:
      - postgres
volumes:
  db_data:
```

### 5.3 Armazenamento de Assets 3D (AWS S3)

**Estrutura de Pastas:**
```
s3://museu-digital/{cliente_id}/
  ├── assets/
  │   ├── {asset_id}/
  │   │   ├── original.usd
  │   │   ├── optimized.glb
  │   │   ├── textures/
  │   │   │   ├── diffuse.jpg
  │   │   │   └── normal.png
  │   │   ├── metadata.json
  │   │   └── embedding.json
  ├── digital_twins/
  │   ├── sala_principal.glb
  │   └── sala_principal.usd
  ├── embeddings/
  │   └── faiss_index.bin
  └── exports/
      └── catalog_2026-07-01.csv
```

---

## 6. Integrações e APIs

### 6.1 API do Acervo (contrato do MUSA)

O contrato é estável independentemente da implementação (§2.1.2). No MVP ele é
materializado como arquivos estáticos (`catalog.json`, `items/{id}.json`); no estágio de
escala, o Payload expõe os mesmos recursos via REST/GraphQL.

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/collections` | GET | Listar coleções e subcoleções |
| `/collections/{id}/items` | GET | Listar itens com filtros |
| `/items/{id}` | GET | Obter a ficha completa de uma peça |
| `/schema` | GET | Publicar o JSON Schema da ficha universal |
| `/search?q=` | GET | Busca semântica (RAG) |
| `/items` | POST | Criar ou atualizar item (requer backend de escala) |

### 6.2 Pipeline de Ingestão e Indexação

Cada ficha é validada contra o contrato antes de entrar no índice. Ficha fora do
contrato **falha o build** — é isso que mantém o "asset watertight" verificável.

```python
# Exemplo: valida as fichas contra o contrato e gera o índice do acervo
import json
import sqlite3
from pathlib import Path

from jsonschema import validate

SCHEMA = json.loads(Path("schemas/ficha.schema.json").read_text(encoding="utf-8"))


def build_index(acervo_root: Path, out_dir: Path) -> None:
    conn = sqlite3.connect(out_dir / "catalog.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, colecao TEXT, ficha JSON)"
    )

    for ficha_path in sorted(acervo_root.glob("*/*/ficha.json")):
        ficha = json.loads(ficha_path.read_text(encoding="utf-8"))
        validate(instance=ficha, schema=SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO items (id, colecao, ficha) VALUES (?, ?, ?)",
            (ficha["asset_id"], ficha["colecao"], json.dumps(ficha, ensure_ascii=False)),
        )

    conn.commit()
    conn.close()
```

### 6.3 Conversão USD → GLB

```bash
# Usando o usd2gltf (exemplo)
usd2gltf --input modelo.usd --output modelo.glb --optimize --compress
```

### 6.4 API do Assistente IA

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/assistant/ask` | POST | Fazer pergunta sobre o acervo |
| `/assistant/voice` | POST | Enviar áudio com pergunta |
| `/assistant/suggest` | GET | Sugerir perguntas frequentes |
| `/assistant/feedback` | POST | Avaliar utilidade da resposta |

```javascript
// Exemplo de chamada à API do assistente
const response = await fetch('/assistant/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        question: "Quais artistas do movimento modernista estão no acervo?",
        context: {
            collectionIds: ['123', '456'],
            ageGroup: 'adult' // ou 'child' para respostas infantis
        }
    })
});
const data = await response.json();
// data.answer: "O acervo contém obras de Tarsila do Amaral..."
// data.suggestedArtifacts: [ { id: '789', title: 'Abaporu' } ]
```

---

## 7. Segurança e Backup

### 7.1 Segurança

- **Autenticação:** nativa do backend de escala (Payload) com 2FA no provedor de identidade; o MVP não expõe escrita pública
- **API:** Tokens JWT para autenticação de aplicações externas
- **HTTPS:** Obrigatório para todos os endpoints
- **IAM:** Políticas de acesso granular para S3
- **CORS:** Configuração restrita para domínios autorizados
- **Privacidade de Dados:** Conformidade com LGPD para dados de visitantes (perguntas, áudios)

### 7.2 Backup

| Tipo | Frequência | Retenção | Localização |
|------|------------|----------|-------------|
| **Banco de Dados** | Diário | 30 dias | S3 (Glacier) |
| **Assets 3D** | Contínuo (S3 versioning) | Ilimitado | S3 + Glacier |
| **Aplicação + índice do acervo** | Semanal | 3 versões | S3 + Export local |
| **Embeddings** | Semanal | 30 dias | S3 + Backup local |

---

## 8. Monitoramento e Observabilidade

### 8.1 Métricas-Chave

> 📋 **Seção incompleta na origem.** No documento original ela foi interrompida no cabeçalho da
> tabela. A tabela abaixo é um ponto de partida técnico proposto em 2026-09-16 e **precisa de
> revisão** antes de virar SLO contratual.

| Métrica | Camada | O que indica | Alvo inicial |
|---------|--------|--------------|--------------|
| Tempo de build do acervo | Pipeline | custo de ingestão por lote | < 10 min para 1.000 peças |
| Fichas rejeitadas na validação | Pipeline | qualidade dos metadados de entrada | 0 em produção |
| Tempo de carga do GLB (p75) | Entrega | se o tier 3D é usável em 4G | < 3 s por peça |
| Cache hit do CDN | Entrega | custo de egress | > 90% |
| Latência p95 de `/items/{id}` | API | fluidez da navegação | < 300 ms |
| Custo por consulta do assistente | IA | sustentabilidade do RAG | dentro do previsto por tier |
| Custo de armazenamento | Infra | base do preço mensal | acompanhar GB/mês |
| Qualidade da recuperação (RAG) | IA | utilidade do assistente | reavaliar a cada 6 meses |

### 8.2 Alertas

> 📋 **Pendente:** definir os gatilhos (build quebrado, ficha rejeitada, egress acima da faixa
> contratada) e o canal de notificação.
