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

| Métrica

---------------------------------------------------------------------------------------------------------------------------------------------

> ⚠️ **REGISTRO HISTÓRICO EMBUTIDO.** Todo o conteúdo abaixo, até o fim deste arquivo,
> é a transcrição de uma sessão de design sobre a arquitetura "USD-first", anexada a
> este documento. Ele **não** faz parte da especificação numerada (§1–§8) acima. A
> decisão vigente sobre a camada de acervo está em `docs/adr/0001-camada-de-acervo.md`.

Excelente! Vamos reescrever a arquitetura completa com o USDA como fonte única de verdade, eliminando arquivos TOML/JSON separados e simplificando todo o pipeline.

---

# 🏛️ ARQUITETURA UNIFICADA COM USD (USDA como Fonte Única)

## Visão Geral da Arquitetura Simplificada

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   SISTEMA DE GESTÃO DE ACERVO (USD-FIRST)                   │
│                      Todas as informações centralizadas no USDA              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐
│   CAMADA DE      │    │   CAMADA DE      │    │   CAMADA DE FRONTEND     │
│   DADOS/ACERVO   │───▶│   PROCESSAMENTO  │───▶│   (Website + Visualização)│
│   (USDA +       │    │   (Pipelines     │    │                          │
│    Assets)      │    │   Minimalistas)  │    │                          │
└──────────────────┘    └──────────────────┘    └──────────────────────────┘
```

---

## 📁 CAMADA 1: ESTRUTURA DE DADOS (Acervo em USDA)

### Estrutura de Pastas Simplificada

```
acervo/
├── colecao_egipcia/
│   ├── metadata.usda              # Metadados da coleção (USDA)
│   ├── vaso_canopo/
│   │   ├── asset.usda             # UNICO ARQUIVO: modelo + ficha + referências
│   │   ├── modelo.glb             # Modelo 3D (referenciado pelo USDA)
│   │   ├── textures/              # Texturas
│   │   │   ├── base_color.png
│   │   │   └── normal_map.png
│   │   └── images/                # Imagens 2D (referenciadas no USDA)
│   │       ├── front.jpg
│   │       └── side.jpg
│   │
│   └── sarcófago/
│       ├── asset.usda             # Único arquivo com todos os dados
│       ├── modelo.glb
│       └── images/
│
├── colecao_grega/
│   ├── metadata.usda
│   └── anfora/
│       ├── asset.usda
│       └── ...
│
└── alas/                          # Digital Twins do museu
    ├── ala_egipcia.usda           # Layout completo da ala (com referências)
    ├── robo_guia.usda             # Robô assistente
    └── display_interativo.usda    # Display fixo interativo
```

### Exemplo de arquivo USDA unificado (asset.usda)

```usda
#usda 1.0
# Fonte única de verdade para o item "Vaso Canopo"

def Xform "vaso_canopo" (
    # ============================================
    # METADADOS DA FICHA (antigo TOML/JSON)
    # ============================================
    customData = {
        dictionary museu = {
            # Identificação
            string id = "EG-001"
            string nome = "Vaso Canopo com Cabeça de Falcão"
            string data = "650 a.C."
            string periodo = "Período Saíta"
            string cultura = "Egípcia"
            
            # Classificação
            dictionary classificacao = {
                string categoria = "Vaso Canopo"
                string material = "Alabastro"
                string tecnica = "Esculpido e Polido"
                dictionary dimensoes = {
                    float altura = 45
                    float largura = 18
                    float profundidade = 18
                }
            }
            
            # Localização
            dictionary localizacao = {
                string ala = "Ala Egípcia"
                string vitrine = "Vitrine 12"
                string numero_inventario = "MUS-2024-001"
            }
            
            # Descrição
            string resumo = "Vaso canopo para vísceras mumificadas, representando o deus Qebehsenuef"
            string detalhes = "Detalhamento completo do objeto..."
            
            # Tags para busca
            string[] tags = ["religiao", "mumificacao", "deuses_egipcios", "VII_seculo_AC"]
            
            # Configuração de apresentação
            dictionary apresentacao = {
                string prioridade = "alta"
                bool rotacao_3d = true
                bool zoom = true
                string preview_imagem = "images/front.jpg"
            }
            
            # Relações com outros assets
            dictionary relacoes = {
                string parte_de = "colecao_egipcia"
                string gemelo_digital = "../alas/ala_egipcia.usda#vitrine_12"
            }
        }
    }
)
{
    # ============================================
    # MODELO 3D (referência ao GLB)
    # ============================================
    def "Modelo" (
        references = </path/to/modelo.glb>
    ) {
        # Metadados adicionais sobre o modelo
        customData = {
            dictionary modelo_info = {
                string formato = "glb"
                string arquivo = "modelo.glb"
                int vertices = 24500
                int faces = 12300
            }
        }
    }
    
    # ============================================
    # VARIANTES PARA VISUALIZAÇÃO (Exploded View, etc)
    # ============================================
    variants "vis" (
        variants = {
            "default" = {
                def Xform "Default" {
                    # Configuração padrão
                }
            }
            "exploded" = {
                def Xform "Exploded" {
                    # Configuração para exploded view
                    double3 xformOp:translate = (0, 0.5, 0)
                    uniform token[] xformOpOrder = ["xformOp:translate"]
                }
            }
            "sectioned" = {
                def Xform "Sectioned" {
                    # Configuração para corte transversal
                    double3 xformOp:translate = (0, 0, 0)
                    uniform token[] xformOpOrder = ["xformOp:translate"]
                }
            }
        }
    )
    
    # ============================================
    # IMAGENS 2D (referenciadas)
    # ============================================
    def "Imagens" {
        customData = {
            dictionary imagens = {
                string front = "images/front.jpg"
                string side = "images/side.jpg"
                string back = "images/back.jpg"
                string detail = "images/detail.jpg"
                string top = "images/top.jpg"
            }
        }
    }
    
    # ============================================
    # ANIMAÇÕES OU COMPORTAMENTOS
    # ============================================
    def Scope "Animations" {
        def Xform "Rotacao" {
            # Animação de rotação automática
            double3 xformOp:translate = (0, 0, 0)
            double3 xformOp:rotateXYZ = (0, 0, 0)
            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]
            
            customData = {
                dictionary animacao = {
                    bool ativo = true
                    float velocidade = 0.02
                    string eixo = "y"
                    bool loop = true
                }
            }
        }
    }
    
    # ============================================
    # LABELS E ANOTAÇÕES (para UI)
    # ============================================
    def Scope "Labels" {
        def Xform "Label_Parte1" {
            double3 xformOp:translate = (0.5, 1.2, 0)
            customData = {
                string label = "Boca do vaso"
                string descricao = "Abertura para inserção das vísceras"
            }
        }
        def Xform "Label_Parte2" {
            double3 xformOp:translate = (-0.3, 0.8, 0.4)
            customData = {
                string label = "Cabeça de Falcão"
                string descricao = "Representação de Qebehsenuef"
            }
        }
    }
}
```

### Exemplo de Metadados da Coleção (metadata.usda)

```usda
#usda 1.0

def Xform "colecao_egipcia" (
    customData = {
        dictionary museu = {
            string id = "colecao_egipcia"
            string nome = "Coleção Egípcia"
            string descricao = "Acervo de artefatos do Antigo Egito, período de 3000 a.C. a 30 d.C."
            string cor_primaria = "#D4A574"
            string icone = "pyramid.svg"
            dictionary configuracao = {
                bool viewer_3d_padrao = true
                string ordem_exibicao = "cronologica"
            }
            
            # Lista de itens da coleção (referências)
            string[] itens = [
                "vaso_canopo/asset.usda",
                "sarcofago/asset.usda",
                "estatueta/asset.usda"
            ]
        }
    }
)
{
}
```

---

## 🔄 CAMADA 2: PIPELINE DE PROCESSAMENTO (SIMPLIFICADO)

### Pipeline Detalhado (Sem TOML/JSON)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE UNIFICADO (USD-FIRST)                     │
└─────────────────────────────────────────────────────────────────────────────┘

        ┌─────────────────────┐
        │   ACERVO (PASTAS)   │
        │                     │
        │  ├── asset.usda    │  ← Única fonte de dados
        │  ├── modelo.glb    │
        │  └── images/       │
        └──────────┬──────────┘
                   │
                   ▼
        ┌────────────────────────────────────────────────────────────┐
        │            WATCHER / SCANNER                               │
        │  (Python + pxr.Usd)                                      │
        │                                                           │
        │  Para cada arquivo .usda:                                 │
        │  1. Abre o estágio USD (Usd.Stage.Open)                  │
        │  2. Extrai customData.museu (todos os metadados)         │
        │  3. Valida estrutura (esquema obrigatório)               │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE INDEX (Busca)                       │
        │  (Python + Qdrant)                                       │
        │                                                           │
        │  1. Extrai metadados do USDA                             │
        │  2. Concatena: nome + resumo + tags + descrição         │
        │  3. Gera embeddings (BGE)                                │
        │  4. Armazena vetores + metadados no Qdrant              │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE IIIF MANIFESTS                      │
        │  (Python)                                                 │
        │                                                           │
        │  1. Lê lista de imagens do customData.images             │
        │  2. Gera IIIF Manifest (JSON) a partir das imagens      │
        │  3. Salva em /iiif/{id}/manifest.json                    │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            OTIMIZADOR USD PARA WEB                       │
        │  (Python + pxr.Usd + WASM)                              │
        │                                                           │
        │  1. Carrega asset.usda                                   │
        │  2. Resolve referências (GLB, texturas)                 │
        │  3. Converte para USDZ (zipado, otimizado para web)     │
        │  4. Salva em /assets/{id}.usdz                          │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            GERADOR DE SITE (Next.js SSG)                 │
        │                                                           │
        │  Lê metadados do USDA e gera páginas:                    │
        │  - /colecoes/[id]                                        │
        │  - /item/[id]                                            │
        │  - /ala/[id] (digital twin)                             │
        └────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │            SAÍDA (Site Build + Assets)                    │
        │  /dist/                                                   │
        │  ├── index.html                                           │
        │  ├── item/                                               │
        │  ├── iiif/                                              │
        │  ├── assets/   (USDZ, GLB, imagens otimizadas)          │
        │  └── data/     (JSON para busca/busca dinâmica)         │
        └────────────────────────────────────────────────────────────┘
```

### Script de Extração de Metadados (Python)

```python
# scripts/extract_metadata.py
from pxr import Usd, Sdf
import json
from pathlib import Path

def extract_metadata_from_usda(usda_path: Path) -> dict:
    """Extrai todos os metadados de um arquivo USD."""
    
    # Abre o estágio USD
    stage = Usd.Stage.Open(str(usda_path))
    
    # Pega o prim raiz (assumindo que é o primeiro)
    root_prim = stage.GetPseudoRoot().GetChildren()[0]
    
    # Extrai customData
    custom_data = root_prim.GetCustomData()
    
    # Retorna apenas os dados do museu
    return custom_data.get("museu", {})

def generate_search_index(acervo_path: Path) -> list:
    """Gera índice de busca a partir de todos os arquivos USD."""
    items = []
    
    for usda_file in acervo_path.rglob("*.usda"):
        # Pula metadados de coleção
        if "metadata.usda" in str(usda_file):
            continue
            
        metadata = extract_metadata_from_usda(usda_file)
        
        # Constrói documento de busca
        doc = {
            "id": metadata.get("id", ""),
            "nome": metadata.get("nome", ""),
            "resumo": metadata.get("resumo", ""),
            "tags": metadata.get("tags", []),
            "cultura": metadata.get("cultura", ""),
            "periodo": metadata.get("periodo", ""),
            "material": metadata.get("classificacao", {}).get("material", ""),
            "path": str(usda_file),
            # Concatenação para embedding
            "text": f"{metadata.get('nome', '')} {metadata.get('resumo', '')} {' '.join(metadata.get('tags', []))}"
        }
        items.append(doc)
    
    return items

# Uso
if __name__ == "__main__":
    acervo = Path("acervo")
    items = generate_search_index(acervo)
    
    # Salva para indexação no Qdrant
    with open("search_index.json", "w") as f:
        json.dump(items, f, indent=2)
```

### Script de Extração de Imagens para IIIF

```python
# scripts/generate_iiif.py
from pxr import Usd
import json
from pathlib import Path

def generate_iiif_manifest(usda_path: Path, base_url: str) -> dict:
    """Gera IIIF Manifest a partir de um arquivo USD."""
    
    stage = Usd.Stage.Open(str(usda_path))
    root_prim = stage.GetPseudoRoot().GetChildren()[0]
    
    # Extrai dados
    metadata = root_prim.GetCustomData().get("museu", {})
    images = root_prim.GetCustomData().get("imagens", {})
    
    # Constrói IIIF Manifest v3
    manifest = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base_url}/iiif/{metadata.get('id', '')}/manifest.json",
        "type": "Manifest",
        "label": {"en": [metadata.get("nome", "Sem título")]},
        "summary": {"pt": [metadata.get("resumo", "")]},
        "metadata": [
            {"label": "Cultura", "value": metadata.get("cultura", "")},
            {"label": "Período", "value": metadata.get("periodo", "")},
            {"label": "Material", "value": metadata.get("classificacao", {}).get("material", "")},
        ],
        "items": []
    }
    
    # Adiciona cada imagem como uma canvas
    for idx, (label, path) in enumerate(images.items()):
        canvas = {
            "id": f"{base_url}/iiif/{metadata.get('id', '')}/canvas/{idx}",
            "type": "Canvas",
            "label": {"en": [label]},
            "items": [{
                "type": "AnnotationPage",
                "items": [{
                    "type": "Annotation",
                    "motivation": "painting",
                    "body": {
                        "id": f"{base_url}/acervo/{usda_path.parent}/{path}",
                        "type": "Image",
                        "format": "image/jpeg"
                    },
                    "target": f"{base_url}/iiif/{metadata.get('id', '')}/canvas/{idx}"
                }]
            }]
        }
        manifest["items"].append(canvas)
    
    return manifest

# Uso
if __name__ == "__main__":
    base_url = "https://museu.example.com"
    acervo = Path("acervo")
    
    for usda_file in acervo.rglob("*.usda"):
        if "metadata.usda" in str(usda_file):
            continue
            
        manifest = generate_iiif_manifest(usda_file, base_url)
        
        # Salva o manifesto
        output_path = Path("iiif") / usda_file.parent.stem / "manifest.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)
```

---

## 🖥️ CAMADA 3: FRONTEND (LENDO METADADOS DIRETAMENTE DO USDA)

### Lendo Metadados no Frontend com JavaScript

```typescript
// lib/usd-parser.ts
import { load } from '@loaders.gl/core';
import { USDLoader } from '@loaders.gl/usdz';

export interface ItemMetadata {
  id: string;
  nome: string;
  resumo: string;
  cultura: string;
  periodo: string;
  tags: string[];
  classificacao: {
    categoria: string;
    material: string;
    tecnica: string;
    dimensoes: {
      altura: number;
      largura: number;
      profundidade: number;
    };
  };
  localizacao: {
    ala: string;
    vitrine: string;
    numero_inventario: string;
  };
  apresentacao: {
    prioridade: string;
    rotacao_3d: boolean;
    zoom: boolean;
    preview_imagem: string;
  };
  relacoes: {
    parte_de: string;
    gemelo_digital: string;
  };
  imagens: Record<string, string>;
}

export async function loadUSDAMetadata(url: string): Promise<ItemMetadata> {
  // Carrega o arquivo USDA
  const data = await load(url, USDLoader);
  
  // Acessa os metadados (estrutura específica do loaders.gl)
  const rootPrim = data.prims?.[0];
  const customData = rootPrim?.customData || {};
  
  return customData.museu as ItemMetadata;
}

// components/ItemPage.tsx
import { useState, useEffect } from 'react';
import { loadUSDAMetadata, ItemMetadata } from '@/lib/usd-parser';
import { USDViewer } from './USDViewer';
import { IIIFViewer } from './IIIFViewer';
import { Tags } from './Tags';

export function ItemPage({ itemId }: { itemId: string }) {
  const [item, setItem] = useState<ItemMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function loadItem() {
      try {
        const data = await loadUSDAMetadata(`/acervo/${itemId}/asset.usda`);
        setItem(data);
      } catch (error) {
        console.error('Erro ao carregar item:', error);
      } finally {
        setLoading(false);
      }
    }
    loadItem();
  }, [itemId]);
  
  if (loading) return <div>Carregando...</div>;
  if (!item) return <div>Item não encontrado</div>;
  
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Coluna do Viewer */}
          <div className="lg:col-span-2">
            <h1 className="text-4xl font-serif mb-4">{item.nome}</h1>
            
            <Tabs>
              <Tab label="3D">
                <USDViewer url={`/assets/${itemId}.usdz`} />
              </Tab>
              <Tab label="Imagens">
                <IIIFViewer manifestId={item.id} />
              </Tab>
              <Tab label="Digital Twin">
                <DigitalTwinViewer alaId={item.localizacao.ala} />
              </Tab>
            </Tabs>
            
            {/* Tags e categorias */}
            <div className="mt-4 flex flex-wrap gap-2">
              {item.tags.map(tag => (
                <span key={tag} className="px-3 py-1 bg-primary-100 rounded-full text-sm">
                  #{tag}
                </span>
              ))}
            </div>
          </div>
          
          {/* Sidebar com metadados */}
          <div className="bg-white shadow-lg rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">Ficha Técnica</h2>
            
            <div className="space-y-3">
              <MetadataRow label="Cultura" value={item.cultura} />
              <MetadataRow label="Período" value={item.periodo} />
              <MetadataRow label="Categoria" value={item.classificacao.categoria} />
              <MetadataRow label="Material" value={item.classificacao.material} />
              <MetadataRow label="Técnica" value={item.classificacao.tecnica} />
              <MetadataRow label="Altura" value={`${item.classificacao.dimensoes.altura}cm`} />
              <MetadataRow label="Localização" value={item.localizacao.vitrine} />
              <MetadataRow label="Inventário" value={item.localizacao.numero_inventario} />
            </div>
            
            {/* Resumo */}
            <div className="mt-6 border-t pt-4">
              <p className="text-gray-700">{item.resumo}</p>
            </div>
            
            {/* Busca semântica integrada */}
            <div className="mt-6 border-t pt-4">
              <SemanticSearch context={{ itemId: item.id, tags: item.tags }} />
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
}
```

### Componente USD Viewer (com metadados e variantes)

```typescript
// components/USDViewer.tsx
import { useEffect, useRef, useState } from 'react';
import { load } from '@loaders.gl/core';
import { USDLoader } from '@loaders.gl/usdz';
import { Scene, WebGLRenderer, PerspectiveCamera } from 'three';

interface VariantOption {
  label: string;
  value: string;
}

export function USDViewer({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [variants, setVariants] = useState<VariantOption[]>([]);
  const [selectedVariant, setSelectedVariant] = useState('default');
  const rendererRef = useRef<WebGLRenderer | null>(null);
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Setup Three.js
    const scene = new Scene();
    const camera = new PerspectiveCamera(60, 800/600, 0.1, 1000);
    const renderer = new WebGLRenderer({ antialias: true });
    renderer.setSize(800, 600);
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;
    
    // Carrega o USDZ
    async function loadUSDZ() {
      const data = await load(url, USDLoader);
      
      // Extrai variantes do USDA
      const rootPrim = data.prims?.[0];
      const variantsData = rootPrim?.variants?.vis || {};
      const variantOptions = Object.keys(variantsData).map(key => ({
        label: key.charAt(0).toUpperCase() + key.slice(1),
        value: key
      }));
      setVariants(variantOptions);
      
      // Aplica variante selecionada
      await applyVariant(data, selectedVariant);
    }
    
    loadUSDZ();
    
    // Loop de renderização
    function animate() {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();
    
    return () => {
      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, [url]);
  
  async function applyVariant(data: any, variant: string) {
    // Lógica para aplicar a variante no modelo
    console.log(`Aplicando variante: ${variant}`);
    // ... implementação específica do USD
  }
  
  return (
    <div>
      <div ref={containerRef} className="w-full h-[600px] rounded-lg" />
      
      {/* Seletor de variantes */}
      {variants.length > 0 && (
        <div className="mt-4 flex gap-2">
          {variants.map(v => (
            <button
              key={v.value}
              onClick={() => setSelectedVariant(v.value)}
              className={`px-4 py-2 rounded ${
                selectedVariant === v.value 
                  ? 'bg-primary-600 text-white' 
                  : 'bg-gray-200 hover:bg-gray-300'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Sistema de Busca Semântica (RAG) no Frontend

```typescript
// components/SemanticSearch.tsx
import { useState } from 'react';
import { searchItems } from '@/lib/search';

interface SearchResult {
  id: string;
  nome: string;
  resumo: string;
  score: number;
  path: string;
}

export function SemanticSearch({ context }: { context?: any }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState('');
  
  async function handleSearch() {
    if (!query.trim()) return;
    
    setLoading(true);
    try {
      // Busca semântica via API
      const response = await fetch('/api/search/semantic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query,
          context,  // Passa contexto atual (ex: item atual, tags)
          limit: 5
        })
      });
      
      const data = await response.json();
      setResults(data.results);
      setAnswer(data.answer);
    } catch (error) {
      console.error('Erro na busca:', error);
    } finally {
      setLoading(false);
    }
  }
  
  return (
    <div className="border rounded-lg p-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Pergunte sobre o acervo..."
          className="flex-1 px-4 py-2 border rounded-lg"
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>
      
      {answer && (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <h3 className="font-medium">Resposta:</h3>
          <p className="text-gray-700">{answer}</p>
        </div>
      )}
      
      {results.length > 0 && (
        <div className="mt-4">
          <h4 className="font-medium mb-2">Fontes:</h4>
          <ul className="space-y-2">
            {results.map(result => (
              <li key={result.id} className="p-2 bg-gray-50 rounded">
                <a href={`/item/${result.id}`} className="text-primary-600 hover:underline">
                  {result.nome}
                </a>
                <span className="text-sm text-gray-500 ml-2">
                  (relevância: {(result.score * 100).toFixed(0)}%)
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## ⚙️ CAMADA 4: BACKEND (API REST + RAG)

### API FastAPI com Extração de Metadados do USD

```python
# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
from pathlib import Path
from pxr import Usd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    context: Optional[dict] = None
    limit: int = 5

class SearchResult(BaseModel):
    id: str
    nome: str
    resumo: str
    score: float
    path: str

# Cache dos metadados do USD
metadata_cache = {}

def load_metadata_from_usd(usda_path: Path) -> dict:
    """Carrega metadados do USD com cache."""
    if str(usda_path) in metadata_cache:
        return metadata_cache[str(usda_path)]
    
    stage = Usd.Stage.Open(str(usda_path))
    root_prim = stage.GetPseudoRoot().GetChildren()[0]
    metadata = root_prim.GetCustomData().get("museu", {})
    
    metadata_cache[str(usda_path)] = metadata
    return metadata

@app.get("/api/items/{item_id}")
async def get_item(item_id: str):
    """Busca um item pelo ID."""
    # Procura o arquivo USDA
    acervo_path = Path("acervo")
    usda_files = list(acervo_path.rglob(f"**/{item_id}/asset.usda"))
    
    if not usda_files:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    metadata = load_metadata_from_usd(usda_files[0])
    return metadata

@app.post("/api/search/semantic")
async def search_semantic(request: SearchRequest):
    """Busca semântica usando RAG."""
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    
    # Inicializa clientes
    embedder = SentenceTransformer('BAAI/bge-base-en-v1.5')
    qdrant = QdrantClient(host="localhost", port=6333)
    
    # Gera embedding da query
    query_embedding = embedder.encode(request.query)
    
    # Filtro por contexto (ex: tags do item atual)
    filter_conditions = {}
    if request.context and "tags" in request.context:
        filter_conditions = {
            "must": [{
                "key": "tags",
                "match": {"any": request.context["tags"]}
            }]
        }
    
    # Busca vetorial
    results = qdrant.search(
        collection_name="acervo",
        query_vector=query_embedding,
        limit=request.limit,
        query_filter=filter_conditions
    )
    
    # Constrói resposta
    search_results = []
    context_texts = []
    
    for hit in results:
        item = hit.payload
        search_results.append({
            "id": item["id"],
            "nome": item["nome"],
            "resumo": item["resumo"],
            "score": hit.score,
            "path": item["path"]
        })
        context_texts.append(f"""
        Item: {item['nome']}
        Descrição: {item['resumo']}
        Tags: {', '.join(item['tags'])}
        """)
    
    # Gera resposta com DeepSeek (via API)
    from openai import OpenAI
    client = OpenAI(
        base_url="https://api.deepseek.com/v1",
        api_key="sk-...",
        model="deepseek-v4-flash"
    )
    
    prompt = f"""
    Baseado no acervo do museu, responda à pergunta:
    
    Pergunta: {request.query}
    
    Contexto relevante:
    {'---'.join(context_texts)}
    
    Cite os itens específicos mencionados.
    """
    
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    
    return {
        "results": search_results,
        "answer": response.choices[0].message.content
    }
```

---

## 🔧 CAMADA 5: FERRAMENTAS E RECOMENDAÇÕES ATUALIZADAS

### Stack Tecnológico (Simplificado)

| Camada | Tecnologia | Justificativa |
|--------|------------|---------------|
| **Processamento USD** | Python + pxr.Usd | Oficial, completa, suporte total a metadados |
| **Frontend USD** | `@loaders.gl/usdz` + Three.js | Lê USDA/USDZ no browser, acessa customData |
| **Alternativa USD Frontend** | Needle USD (WASM) | Mais performático, renderização avançada |
| **Backend API** | FastAPI | Rápido, moderno, integração com Python |
| **Vector DB** | Qdrant | Open-source, performático |
| **Frontend** | Next.js 14+ | SSR, otimização, API routes |
| **UI** | shadcn/ui + Tailwind | Moderno, customizável |
| **IIIF Viewer** | Mango | Suporte IIIF v3, open-source |
| **Busca/IA** | DeepSeek API | Pay-per-use, eficiente |
| **Deploy** | Vercel + Railway | Simples, escalável |

### Benefícios da Arquitetura Unificada

1. **Uma única fonte de verdade**: Todos os dados do item (modelo + ficha + imagens) em um único arquivo USDA
2. **Pipeline simplificado**: Remove a necessidade de parsers TOML/JSON separados
3. **Integridade garantida**: Metadados e modelo nunca ficam dessincronizados
4. **Variantes nativas**: Aproveita o sistema de variantes do USD para diferentes visualizações
5. **Labels automáticos**: Metadados podem alimentar automaticamente labels na UI
6. **Busca semântica integrada**: Metadados do USDA alimentam embeddings e RAG
7. **Totalmente web-ready**: Bibliotecas JS modernas suportam leitura de USDA

---

## 📊 RESULTADO FINAL: O QUE O USUÁRIO VÊ (ATUALIZADO)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🏛️ MUSEU VIRTUAL - ACERVO DIGITAL USD-FIRST                             │
│  ───────────────────────────────────────────────────────────────────────── │
│  [Home] [Coleções] [Digital Twin] [Busca IA] [Sobre]                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  VASO CANOPO - 650 a.C.                                                    │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  [Viewer 3D com rotação automática]                              │    │
│  │                                                                   │    │
│  │  Variantes: [Default] [Exploded] [Sectioned]                    │    │
│  │                                                                   │    │
│  │  Labels interativas:                                             │    │
│  │  ● "Boca do vaso" - clique para info                            │    │
│  │  ● "Cabeça de Falcão" - clique para info                        │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       │
│  │  Ficha      │  │  Imagens    │  │  Relacionados│                       │
│  │  Técnica    │  │  (IIIF)     │  │              │                       │
│  │             │  │             │  │  • Sarcófago │                       │
│  │  Cultura:   │  │  [Front]    │  │  • Estátua   │                       │
│  │  Egípcia    │  │  [Side]     │  │              │                       │
│  │  Período:   │  │  [Detail]   │  │              │                       │
│  │  Saíta      │  │             │  │              │                       │
│  └─────────────┘  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  BUSCA INTELIGENTE (RAG)                                                    │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │  [🔍 "Quais vasos canopos existem?"]                             │    │
│  │                                                                   │    │
│  │  Resposta: "Existem 3 vasos canopos: ..."                        │    │
│  │                                                                   │    │
│  │  Fontes:                                                          │    │
│  │  • Vaso Canopo com Cabeça de Falcão (EG-001) - 92%              │    │
│  │  • Vaso Canopo com Cabeça de Chacal (EG-002) - 88%              │    │
│  │  • Vaso Canopo com Cabeça de Babuíno (EG-003) - 85%             │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 PRÓXIMOS PASSOS PARA IMPLEMENTAÇÃO

### Fase 1: Setup e Estrutura (Dia 1-2)
1. Instalar Python 3.11+, Node.js 18+
2. Configurar ambiente virtual Python com `pxr.Usd`
3. Criar estrutura de pastas do acervo
4. Criar primeiro arquivo USDA de exemplo com metadados

### Fase 2: Pipeline de Processamento (Dia 3-5)
1. Implementar script de extração de metadados do USDA
2. Implementar script de geração de IIIF manifests
3. Implementar script de otimização USD para web (USDZ)
4. Configurar Qdrant e indexar metadados

### Fase 3: Frontend Core (Dia 6-10)
1. Criar projeto Next.js com Tailwind/shadcn
2. Implementar leitura de USDA no frontend (loaders.gl)
3. Implementar USD Viewer com Three.js
4. Implementar IIIF Viewer (Mango)

### Fase 4: Features Avançadas (Dia 11-14)
1. Implementar RAG com DeepSeek API
2. Implementar Digital Twin com Three.js
3. Implementar WebSockets para robôs interativos
4. Implementar variantes e labels interativos

### Fase 5: Deploy (Dia 15)
1. Deploy frontend na Vercel
2. Deploy backend na Railway
3. Configurar Qdrant em produção
4. Deploy assets (USDZ, imagens) no S3/CDN

---

Essa arquitetura USD-first elimina toda a complexidade de gerenciar arquivos separados de metadados e simplifica drasticamente tanto o pipeline de processamento quanto o frontend. Os metadados vivem onde devem estar: junto com o modelo 3D que descrevem.

Precisa que eu detalhe alguma parte específica ou ajude a começar com o primeiro arquivo USDA?

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

