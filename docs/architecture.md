# NEXUS 4.0 --- Documento de Arquitetura Completa

> Documento de referencia tecnica para a disciplina **Topicos Avancados de Engenharia de Producao e Inteligencia Artificial** --- PPGEPS/Unisinos
>
> Prof. Dr. Marcos Hoffmann

---

## Sumario

1. [Visao Geral do Sistema](#1-visao-geral-do-sistema)
2. [Arquitetura de Camadas](#2-arquitetura-de-camadas)
3. [Componentes de Infraestrutura (Docker)](#3-componentes-de-infraestrutura-docker)
4. [API REST (FastAPI)](#4-api-rest-fastapi)
5. [Sistema Multi-Agente](#5-sistema-multi-agente)
6. [Banco de Dados PostgreSQL](#6-banco-de-dados-postgresql)
7. [GraphRAG (Neo4j)](#7-graphrag-neo4j)
8. [RAG Vetorial (ChromaDB)](#8-rag-vetorial-chromadb)
9. [Automacoes N8N](#9-automacoes-n8n)
10. [Dashboards Grafana](#10-dashboards-grafana)
11. [Integracao WhatsApp (Meta Cloud API)](#11-integracao-whatsapp-meta-cloud-api)
12. [Chat UI (Streamlit)](#12-chat-ui-streamlit)
13. [Fluxo de Dados Completo](#13-fluxo-de-dados-completo)
14. [Integridade de Dados](#14-integridade-de-dados)
15. [Stack Tecnologica](#15-stack-tecnologica)
16. [Como Executar](#16-como-executar)
17. [Conceitos Academicos Demonstrados](#17-conceitos-academicos-demonstrados)

---

## 1. Visao Geral do Sistema

O **NEXUS 4.0** e um sistema multi-agente (MAS --- Multi-Agent System) para gestao de operacoes industriais, projetado como plataforma didatica e funcional que integra conceitos de Engenharia de Producao com tecnicas modernas de Inteligencia Artificial.

O sistema simula uma fabrica metalmecanica que produz tres produtos (eixos de transmissao, engrenagens helicoidais e buchas de mancal), com dados operacionais realistas armazenados em PostgreSQL e enriquecidos por um grafo de conhecimento em Neo4j.

### Principios Fundamentais

- **Fonte unica de verdade**: todos os dados operacionais residem no PostgreSQL. O Neo4j (GraphRAG) e o ChromaDB (RAG vetorial) sao camadas complementares de enriquecimento, nunca fontes primarias.
- **Integridade de dados**: os agentes NUNCA inventam dados --- toda informacao numerica apresentada ao usuario foi consultada via ferramentas (tools) que executam queries SQL reais.
- **Orquestracao inteligente**: o Coordinator analisa a demanda do usuario, determina quais agentes especialistas acionar, coleta respostas e consolida em uma visao unificada.
- **Arquitetura containerizada**: todos os componentes rodam em Docker, facilitando reproducao e deploy.

### Contexto Industrial Simulado

```
Fabrica Metalmecanica NEXUS
  |
  |--- LINHA-01 (Usinagem + Acabamento)
  |       |--- CNC-03      (Centro de Usinagem XR-500, health: 62, OEE: 72.5%)
  |       |--- SERRA-01    (Serra CNC SC-300, health: 85, OEE: 84.5%)
  |       |--- RETIFICA-01 (Retifica Cilindrica RC-100, health: 91, OEE: 89.0%)
  |
  |--- LINHA-02 (Conformacao)
  |       |--- PRENSA-01   (Prensa Hidraulica PH-200, health: 88, OEE: 87.3%)
  |
  |--- Produtos
  |       |--- PROD-001: Eixo de Transmissao ET-500 (R$ 185,00, ciclo: 42 min)
  |       |--- PROD-002: Engrenagem Helicoidal EH-200 (R$ 320,00, ciclo: 55 min)
  |       |--- PROD-003: Bucha de Mancal BM-100 (R$ 95,00, ciclo: 25 min)
  |
  |--- 12 Materiais (MP-001 a MP-012) com classificacao ABC/XYZ
  |--- 8 Fornecedores (FORN-001 a FORN-008)
  |--- 3 Ordens de Producao ativas
  |--- 12 NCRs historicas
  |--- Sensores IoT com leituras a cada 15 min (series temporais 48h)
```

---

## 2. Arquitetura de Camadas

O NEXUS 4.0 segue uma arquitetura em camadas, onde cada camada tem responsabilidades bem definidas:

```
+=====================================================================+
|                        CAMADA DE INTERFACE                          |
|   +------------------+  +------------------+  +------------------+  |
|   | Streamlit Chat   |  | WhatsApp (Meta)  |  | Grafana          |  |
|   | porta 8501       |  | webhook /webhook |  | porta 3000       |  |
|   +--------+---------+  +--------+---------+  +--------+---------+  |
+============|========================|===================|===========+
             |                        |                   |
+============|========================|===================|===========+
|            v          CAMADA DE API (FastAPI - porta 8080)          |
|   +-------------------------------------------------------------+  |
|   |  /chat          POST   Orquestracao via Coordinator          |  |
|   |  /agent/{name}  POST   Consulta direta a agente             |  |
|   |  /monitor/*     GET    Endpoints para N8N                   |  |
|   |  /graphrag/*    GET/POST  Consultas ao grafo                |  |
|   |  /rag/*         GET/POST  Consultas vetoriais               |  |
|   |  /ws            WS     WebSocket tempo real                 |  |
|   +-------------------------------------------------------------+  |
+=====================================================================+
             |
+============|========================================================+
|            v       CAMADA DE AGENTES (Multi-Agent System)           |
|                                                                     |
|   +-------------------------------------------------------------+  |
|   |                    COORDINATOR                               |  |
|   |    Analisa -> _determine_agents -> Delega -> Consolida       |  |
|   +----+----------+----------+----------+----------+------------+  |
|        |          |          |          |          |                 |
|   +----v---+ +----v---+ +----v---+ +----v---+ +----v--------+      |
|   |Planner | |Quality | |Supply  | |Mainten.| |Analyst      |      |
|   | (PCP)  | |        | |Chain   | |        | |             |      |
|   +----+---+ +----+---+ +----+---+ +----+---+ +----+-------+      |
|        |          |          |          |          |                 |
|   +----v----------v----------v----------v----------v------------+   |
|   |               BaseAgent (classe abstrata)                   |   |
|   |  - system_prompt   - tools   - think()   - execute_tool()  |   |
|   |  - memory          - tool_choice: required/auto             |   |
|   +-------------------------------------------------------------+   |
+=====================================================================+
             |
+============|========================================================+
|            v          CAMADA DE DADOS E CONHECIMENTO                |
|                                                                     |
|   +----------------+  +----------------+  +---------------------+   |
|   | PostgreSQL     |  | Neo4j          |  | ChromaDB            |   |
|   | porta 5432     |  | porta 7687     |  | porta 8000          |   |
|   |                |  |                |  |                     |   |
|   | Fonte primaria |  | Grafo de       |  | RAG Vetorial        |   |
|   | de dados       |  | conhecimento   |  | (normas, manuais)   |   |
|   | (12 tabelas)   |  | (relacoes)     |  | (embeddings)        |   |
|   +-------+--------+  +-------+--------+  +----------+----------+   |
|           |                    ^                      |              |
|           |  graph_populate.py |                      |              |
|           +--->----------------+                      |              |
|              (PostgreSQL -> Neo4j)                    |              |
+=====================================================================+
             |
+============|========================================================+
|            v         CAMADA DE AUTOMACAO E OBSERVABILIDADE          |
|                                                                     |
|   +-------------------+  +----------------------------------------+ |
|   | N8N               |  | Grafana                                | |
|   | porta 5678        |  | porta 3000                             | |
|   |                   |  |                                        | |
|   | 4 workflows:      |  | 9 dashboards:                         | |
|   | - Monitor sensores|  | - Visao Geral (home)                  | |
|   | - Alerta estoque  |  | - Manutencao preditiva                | |
|   | - Relatorio diario|  | - Supply Chain                        | |
|   | - Orquestracao    |  | - Qualidade, Financeiro, etc.          | |
|   +-------------------+  +----------------------------------------+ |
+=====================================================================+
```

---

## 3. Componentes de Infraestrutura (Docker)

O sistema e definido em um unico `docker-compose.yml` com 8 servicos. Todos os volumes sao persistentes e nomeados.

### 3.1 Tabela de Containers

| Container         | Imagem                        | Porta(s)      | Papel                                        | Depende de  |
|--------------------|-------------------------------|---------------|----------------------------------------------|-------------|
| `nexus-postgres`   | `postgres:16-alpine`          | `5432`        | Banco relacional --- fonte primaria de dados  | ---         |
| `nexus-chromadb`   | `chromadb/chroma:latest`      | `8000`        | Banco vetorial para RAG                       | ---         |
| `nexus-neo4j`      | `neo4j:5.21-community`        | `7474`, `7687`| Grafo de conhecimento (GraphRAG)              | ---         |
| `nexus-n8n`        | `n8nio/n8n:latest`            | `5678`        | Automacao de workflows                        | postgres    |
| `nexus-api`        | Build local (`Dockerfile`)    | `8080`        | API FastAPI + agentes                         | postgres, chromadb |
| `nexus-chat`       | Build local (`Dockerfile.chat`)| `8501`       | Interface Streamlit                           | nexus-api   |
| `nexus-grafana`    | `grafana/grafana:11.1.0`      | `3000`        | Dashboards operacionais                       | postgres    |
| `nexus-whatsapp`   | `atendai/evolution-api:latest`| `8085`        | WhatsApp (Meta Cloud API, opcional, profile)   | postgres    |

### 3.2 Volumes Persistentes

```
postgres_data   -> /var/lib/postgresql/data       (dados do banco)
chroma_data     -> /chroma/chroma                 (vetores e embeddings)
neo4j_data      -> /data                          (grafo Neo4j)
n8n_data        -> /home/node/.n8n                (workflows N8N)
grafana_data    -> /var/lib/grafana               (dashboards Grafana)
```

### 3.3 Health Checks

- **PostgreSQL**: `pg_isready -U nexus` a cada 5s (5 retries)
- **Neo4j**: HTTP GET em `localhost:7474` a cada 10s (5 retries)
- O container `nexus-api` so inicia apos PostgreSQL estar healthy

### 3.4 Bind Mounts (Desenvolvimento)

| Container       | Host                               | Container                                   |
|------------------|-------------------------------------|---------------------------------------------|
| `nexus-postgres` | `./data/init.sql`                  | `/docker-entrypoint-initdb.d/init.sql`      |
| `nexus-api`      | `./agents`, `./rag`, `./data`      | `/app/agents`, `/app/rag`, `/app/data`      |
| `nexus-n8n`      | `./n8n/workflows`                  | `/home/node/workflows`                      |
| `nexus-grafana`  | `./grafana/provisioning`, `./grafana/dashboards` | Provisioning + dashboards         |

---

## 4. API REST (FastAPI)

O arquivo `main.py` define a API FastAPI (versao 4.0.0) que e o ponto de entrada unico para todas as interacoes com o sistema.

### 4.1 Inicializacao (Lifespan)

A funcao `lifespan()` e executada na inicializacao da aplicacao e realiza:

1. Cria o cliente `AsyncOpenAI` (modelo configuravel via `OPENAI_MODEL`, padrao `gpt-4.1`)
2. Tenta conectar ao RAG Vetorial (ChromaDB) --- tolerante a falhas
3. Tenta conectar ao GraphRAG (Neo4j) --- tolerante a falhas
4. Instancia os 5 agentes especialistas, passando `rag_retriever` e `graph_retriever`
5. Instancia o `CoordinatorAgent` e registra todos os agentes nele
6. Inicializa o `WhatsAppHandler` --- tolerante a falhas
7. Armazena tudo no dicionario global `nexus_state`

### 4.2 Endpoints

#### Endpoints Principais

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `GET`  | `/`                             | Status do sistema, lista de agentes registrados, versao                 |
| `GET`  | `/health`                       | Health check: agentes ativos, RAG disponivel, WhatsApp conectado        |
| `POST` | `/chat`                         | **Endpoint principal** --- envia mensagem ao Coordinator que orquestra  |
| `POST` | `/agent/{agent_name}`           | Consulta direta a um agente especifico (bypass do Coordinator)          |
| `GET`  | `/agents`                       | Lista todos os agentes com nome, role, tamanho de memoria, msgs processadas |

#### Endpoints de Monitoramento (chamados pelo N8N)

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `GET`  | `/monitor/sensors`              | Verifica sensores de CNC-03, PRENSA-01, RETIFICA-01, SERRA-01 (a cada 5 min) |
| `GET`  | `/monitor/inventory`            | Verifica niveis de estoque e materiais criticos (a cada 1h)             |
| `POST` | `/monitor/log`                  | Registra execucao de workflow N8N no banco                              |
| `GET`  | `/report/daily`                 | Gera relatorio executivo diario via Coordinator (N8N as 8h)             |

#### Endpoints RAG Vetorial

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `POST` | `/rag/query`                    | Consulta direta ao ChromaDB com query e parametro `k`                   |
| `GET`  | `/rag/stats`                    | Estatisticas da colecao (nome, contagem de documentos)                  |

#### Endpoints GraphRAG

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `POST` | `/graphrag/query`               | Consulta ao grafo de conhecimento por query textual                     |
| `GET`  | `/graphrag/impact/{equipment_id}` | Analise de impacto em cascata de um equipamento                       |
| `GET`  | `/graphrag/supply-chain/{product_id}` | Cadeia de suprimentos completa de um produto via grafo             |
| `GET`  | `/graphrag/quality/{product_id}` | Cadeia de qualidade de um produto (NCRs, normas, equipamentos)         |
| `POST` | `/graphrag/populate`            | Repopula o grafo a partir do PostgreSQL                                 |

#### Endpoints WhatsApp

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `GET`  | `/webhook`                      | Verificacao do webhook pela Meta (responde ao challenge)                 |
| `POST` | `/webhook`                      | Recebe mensagens do WhatsApp e processa via Coordinator                  |
| `POST` | `/webhook/whatsapp`             | Endpoint legado de compatibilidade                                      |

#### WebSocket

| Metodo | Path                            | Descricao                                                               |
|--------|---------------------------------|-------------------------------------------------------------------------|
| `WS`   | `/ws`                           | WebSocket para dashboard em tempo real (broadcast de eventos)            |

### 4.3 Modelos de Dados (Pydantic)

```python
class UserRequest(BaseModel):
    message: str                          # Mensagem do usuario
    user_id: str = "gestor"               # Identificador do usuario
    conversation_id: str | None = None    # ID da conversa (criado automaticamente)
    context: dict | None = None           # Contexto adicional

class AgentQuery(BaseModel):
    agent: str                            # Nome do agente alvo
    message: str                          # Mensagem/pergunta
    context: dict | None = None           # Contexto adicional
```

---

## 5. Sistema Multi-Agente

O coracao do NEXUS 4.0 e seu sistema multi-agente, composto por 1 coordenador e 5 especialistas.

### 5.1 BaseAgent (Classe Base)

Definida em `agents/base_agent.py`, a classe `BaseAgent` e abstrata e fornece toda a infraestrutura comum:

#### Enumeracoes e Modelos

```python
class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    QUALITY = "quality"
    SUPPLY_CHAIN = "supply_chain"
    MAINTENANCE = "maintenance"
    ANALYST = "analyst"

class AgentMessage(BaseModel):
    sender: AgentRole
    receiver: AgentRole | str
    content: str
    message_type: str           # request, response, alert, report
    context: dict
    conversation_id: str | None

class AgentDecision(BaseModel):
    agent: AgentRole
    decision: str
    confidence: float           # 0.0 a 1.0
    reasoning: str
    actions: list[str]
    risks: list[str]
    data: dict
```

#### Construtor

Cada agente recebe:
- `role` (AgentRole) e `name` (str)
- `openai_client` (AsyncOpenAI)
- `model` (padrao: `gpt-4.1`)
- `rag_retriever` (RAGRetriever, opcional)
- `graph_retriever` (GraphRAGRetriever, opcional)

E mantem internamente:
- `memory` --- lista de mensagens recentes (sliding window de 10)
- `message_history` --- historico de AgentMessages entre agentes
- `_force_tools` --- flag para forcar uso de ferramentas

#### Metodo `think()` --- Fluxo Principal

O metodo `think(input_message, context)` e o coracao do processamento:

```
                        think(input_message)
                               |
                               v
               +-------------------------------+
               | 1. Monta system_prompt        |
               |    + data_integrity_prompt     |
               +-------------------------------+
                               |
                               v
               +-------------------------------+
               | 2. Consulta GraphRAG (Neo4j)  |
               |    Se disponivel, busca       |
               |    contexto relacional        |
               +-------------------------------+
                               |
                               v
               +-------------------------------+
               | 3. Consulta RAG Vetorial      |
               |    (ChromaDB) se use_rag=True |
               +-------------------------------+
                               |
                               v
               +-------------------------------+
               | 4. Adiciona contexto          |
               |    operacional + memoria      |
               +-------------------------------+
                               |
                               v
               +-------------------------------+
               | 5. Chama OpenAI API           |
               |    com tools + tool_choice    |
               +-------------------------------+
                               |
                     +---------+---------+
                     |                   |
                     v                   v
              [tem tool_calls]     [sem tool_calls]
                     |                   |
                     v                   v
         +--------------------+    retorna content
         | _handle_tool_calls |
         | (executa + chama   |
         |  OpenAI novamente) |
         +--------------------+
                     |
                     v
              retorna resposta
```

#### tool_choice --- Mecanismo de Integridade

O parametro `tool_choice` da OpenAI API controla se o modelo DEVE usar ferramentas:

| Agente         | tool_choice  | Justificativa                                               |
|----------------|-------------|--------------------------------------------------------------|
| Coordinator    | `auto`       | Na fase de consolidacao nao precisa de tools                 |
| Coordinator    | `required`   | Quando `_force_tools=True` (fase de delegacao)               |
| Planner        | `required`   | SEMPRE deve consultar PostgreSQL antes de responder          |
| Quality        | `required`   | SEMPRE deve consultar PostgreSQL antes de responder          |
| Supply Chain   | `required`   | SEMPRE deve consultar PostgreSQL antes de responder          |
| Maintenance    | `required`   | SEMPRE deve consultar PostgreSQL antes de responder          |
| Analyst        | `required`   | SEMPRE deve consultar PostgreSQL antes de responder          |

Isso garante que os agentes especialistas **nunca respondem com dados inventados** --- sao obrigados a executar pelo menos uma query SQL real.

#### Outros Metodos

- `process_message(AgentMessage)` --- processa mensagem inter-agente
- `make_decision(problem)` --- retorna AgentDecision estruturada com confidence
- `reset_memory()` --- limpa memoria de curto prazo

### 5.2 CoordinatorAgent (Orquestrador)

Definido em `agents/coordinator/agent.py`, e o "cerebro central" do NEXUS.

#### Ferramentas (Tools)

| Tool                | Descricao                                         |
|---------------------|---------------------------------------------------|
| `delegate_to_agent` | Delega tarefa para um agente especialista          |
| `resolve_conflict`  | Resolve conflito entre recomendacoes divergentes   |

#### Metodo `orchestrate()` --- Fluxo de Orquestracao

```
orchestrate(user_request)
       |
       v
+----------------------------------+
| FASE 1: _determine_agents()     |
| Analise por palavras-chave da   |
| mensagem do usuario             |
+----------------------------------+
       |
       v
+----------------------------------+
| FASE 2: Delegacao Direta        |
| Para cada agente selecionado:   |
| - Envia tarefa enriquecida      |
| - Coleta resposta (com dados    |
|   obrigatorios via tools)       |
+----------------------------------+
       |
       v
+----------------------------------+
| FASE 3: Consolidacao            |
| _consolidate() SEM tools        |
| (apenas sintese de texto)       |
| - Preserva valores exatos       |
| - Usa tabelas markdown          |
| - Adapta profundidade           |
+----------------------------------+
       |
       v
    Resposta final ao usuario
```

#### Metodo `_determine_agents()` --- Roteamento por Palavras-Chave

O metodo analisa a mensagem do usuario e seleciona agentes por correspondencia de palavras-chave:

| Agente         | Palavras-chave ativadoras                                                |
|----------------|--------------------------------------------------------------------------|
| Supply Chain   | fornecedor, material, estoque, compra, supply, mp-                       |
| Quality        | qualidade, ncr, defeito, norma, iso, conformidade                        |
| Maintenance    | manutencao, sensor, falha, health, vibracao, temperatura                 |
| Planner        | producao, capacidade, pedido, ordem, plano, equipamento, cnc, oee, turno |
| Analyst        | relatorio, kpi, custo, impacto, financ, roi, melhor                      |

**Regras especiais:**
- Se nenhuma palavra-chave corresponde, **todos os agentes sao acionados**
- Se "melhor" aparece na query, o Analyst e adicionado automaticamente

#### Prioridade de Resolucao de Conflitos

```
Seguranca > Qualidade > Prazo > Custo
```

### 5.3 PlannerAgent (PCP)

**Arquivo:** `agents/planner/agent.py`
**Especialidade:** Planejamento e Controle da Producao

| Tool                   | Descricao                                          | Query SQL                |
|------------------------|-----------------------------------------------------|--------------------------|
| `get_production_orders`| Ordens de producao com produto, status, progresso   | `production_orders JOIN products` |
| `get_products`         | Lista todos os produtos com ciclo, custo, BOM       | `products`               |
| `get_equipment_status` | Status do equipamento: health, OEE, turnos, linha   | `equipment`              |
| `get_capacity_report`  | Capacidade semanal: nominal, real (OEE), horas      | `equipment` com calculos |

**Competencias no Prompt:** MPS, MRP, Sequenciamento, CRP, TOC

### 5.4 QualityAgent

**Arquivo:** `agents/quality/agent.py`
**Especialidade:** Gestao da Qualidade Industrial

| Tool                   | Descricao                                          | Query SQL                |
|------------------------|-----------------------------------------------------|--------------------------|
| `get_quality_records`  | NCRs com tipo, severidade, causa raiz, status       | `quality_records JOIN products` |
| `get_quality_summary`  | Resumo: total NCRs, abertas, criticas, por tipo     | `quality_records` (agregacoes) |
| `get_product_info`     | Dados do produto (especificacoes, BOM, normas)      | `products`               |

**Competencias no Prompt:** CEP, Ishikawa, 5 Porques, FMEA, ISO 9001, ISO 14001, IATF 16949, Cp, Cpk

### 5.5 SupplyChainAgent

**Arquivo:** `agents/supply_chain/agent.py`
**Especialidade:** Gestao da Cadeia de Suprimentos e Materiais

| Tool                    | Descricao                                          | Query SQL                        |
|-------------------------|-----------------------------------------------------|----------------------------------|
| `check_inventory`       | Estoque com classificacao ABC/XYZ, status, cobertura| `materials` (+ BOM via `products`) |
| `get_supplier_info`     | Fornecedores com preco, lead time, rating, qualidade| `suppliers JOIN supplier_materials` |
| `get_purchase_orders`   | Pedidos de compra em andamento                      | `purchase_orders JOIN suppliers JOIN materials` |
| `get_inventory_movements`| Movimentacoes de estoque (N dias)                  | `inventory_movements`            |

**Competencias no Prompt:** ABC/XYZ, EOQ, ROP, Estoque de Seguranca, Giro, TCO, Previsao de Demanda

### 5.6 MaintenanceAgent

**Arquivo:** `agents/maintenance/agent.py`
**Especialidade:** Manutencao Industrial e Gestao de Ativos

| Tool                    | Descricao                                          | Query SQL                |
|-------------------------|-----------------------------------------------------|--------------------------|
| `get_equipment_status`  | Status, health score, OEE de equipamentos           | `equipment`              |
| `get_sensor_readings`   | Leituras mais recentes dos sensores IoT             | `sensor_readings` (DISTINCT ON) |

**Competencias no Prompt:** PdM, Analise de vibracao/temperatura/pressao/corrente, OEE, MTBF/MTTR, TPM, RCM

### 5.7 AnalystAgent

**Arquivo:** `agents/analyst/agent.py`
**Especialidade:** Business Intelligence e Analytics Industrial

| Tool                    | Descricao                                          | Query SQL                |
|-------------------------|-----------------------------------------------------|--------------------------|
| `get_kpis`              | KPIs consolidados: equipamentos, estoque, qualidade, producao | 4 queries agregadas |
| `get_stock_valuation`   | Valorizacao do estoque por classe ABC e categoria   | `materials` (calculo Python) |
| `get_supplier_rankings` | Ranking de fornecedores por rating, confiabilidade  | `suppliers JOIN supplier_materials` |

**Competencias no Prompt:** KPIs (OEE, OTIF, lead time, throughput), Relatorios, ROI, Tendencias

---

## 6. Banco de Dados PostgreSQL

### 6.1 Diagrama de Tabelas

```
+-------------------+     +-------------------+     +------------------+
|    products       |     |   materials       |     |   suppliers      |
|-------------------|     |-------------------|     |------------------|
| id (PK)           |     | id (PK)           |     | id (PK)          |
| name              |     | name              |     | name             |
| description       |     | unit              |     | cnpj             |
| unit_cost_brl     |     | category          |     | rating           |
| cycle_time_min    |     | abc_class (A/B/C) |     | lead_time_days   |
| bom (JSONB)       |     | xyz_class (X/Y/Z) |     | reliability_pct  |
+--------+----------+     | stock_current     |     | quality_pct      |
         |                 | stock_min         |     | price_compet.    |
         |                 | stock_safety      |     | location         |
         |                 | stock_max         |     | payment_terms    |
         |                 | reorder_point     |     | min_order_value  |
         |                 | eoq               |     | certified_iso    |
         |                 | unit_cost_brl     |     | status           |
         |                 | avg_daily_consump.|     +--------+---------+
         |                 | lead_time_days    |              |
         |                 | location_warehouse|              |
         |                 +--------+----------+              |
         |                          |                         |
         |    +---------------------+-------------------------+
         |    |                     |
         |    v                     v
         |  +-----------------------+-----+
         |  |   supplier_materials        |
         |  |-----------------------------|
         |  | id (PK, SERIAL)             |
         |  | supplier_id (FK)            |
         |  | material_id (FK)            |
         |  | unit_price_brl              |
         |  | lead_time_days              |
         |  | min_order_qty               |
         |  | is_preferred                |
         |  | delivery_rating             |
         |  +-----------------------------+
         |
         |  +---------------------------+
         +->| production_orders         |
         |  |---------------------------|     +-------------------+
         |  | id (PK)                   |     | equipment         |
         |  | product_id (FK)           |     |-------------------|
         |  | quantity                   |     | id (PK)           |
         |  | line_id                    |     | name              |
         |  | start_date, end_date       |     | type              |
         |  | status                     |     | line_id           |
         |  | progress_pct               |     | health_score      |
         |  | priority                   |     | oee_pct           |
         |  +---------------------------+     | status            |
         |                                    | capacity_pcs_hour |
         |  +---------------------------+     | shifts_per_day    |
         +->| quality_records           |     | hours_per_shift   |
            |---------------------------|     | planned_downtime  |
            | id (PK)                   |     +--------+----------+
            | product_id (FK)           |              |
            | type                      |              v
            | severity                  |     +-------------------+
            | root_cause                |     | sensor_readings   |
            | status                    |     |-------------------|
            | created_at                |     | id (PK, BIGSERIAL)|
            +---------------------------+     | equipment_id (FK) |
                                              | sensor_type       |
+---------------------------+                 | value             |
| purchase_orders           |                 | unit              |
|---------------------------|                 | threshold         |
| id (PK)                   |                 | status            |
| supplier_id (FK)          |                 | read_at           |
| material_id (FK)          |                 +-------------------+
| quantity                   |
| unit_price_brl             |   +---------------------------+
| total_brl                  |   | inventory_movements       |
| status                     |   |---------------------------|
| urgency (normal/urgent/    |   | id (PK, BIGSERIAL)        |
|          emergency)        |   | material_id (FK)          |
| order_date                 |   | movement_type             |
| expected_delivery          |   | quantity                   |
| received_qty               |   | unit_cost_brl              |
| quality_status              |   | reference_doc              |
+---------------------------+   | reason                     |
                                 | created_at                 |
+---------------------------+   +---------------------------+
| material_forecasts        |
|---------------------------|   +---------------------------+
| id (PK, SERIAL)           |   | automation_logs           |
| material_id (FK)          |   |---------------------------|
| period_start, period_end  |   | id (PK, BIGSERIAL)        |
| forecast_qty              |   | workflow_name              |
| actual_qty                 |   | trigger_type               |
| forecast_method            |   | status                     |
| mape_pct                   |   | summary                    |
+---------------------------+   | details (JSONB)            |
                                 | agents_involved (TEXT[])   |
+---------------------------+   | duration_ms                |
| conversations             |   +---------------------------+
|---------------------------|
| id (PK, UUID)             |   +---------------------------+
| user_phone                 |   | messages                  |
| started_at                 |   |---------------------------|
| status                     |   | id (PK, UUID)             |
| summary                   |   | conversation_id (FK)      |
+---------------------------+   | sender                     |
                                 | content                    |
+---------------------------+   | message_type               |
| agent_decisions           |   | metadata (JSONB)           |
|---------------------------|   | created_at                 |
| id (PK, UUID)             |   +---------------------------+
| conversation_id (FK)      |
| agent_role                 |
| decision                   |
| confidence (FLOAT)         |
| reasoning                  |
| actions (JSONB)            |
| risks (JSONB)              |
| data (JSONB)               |
| created_at                 |
+---------------------------+
```

### 6.2 Tabelas --- Resumo

| # | Tabela                | Registros Iniciais | Finalidade                              |
|---|------------------------|--------------------|-----------------------------------------|
| 1 | `products`            | 3                  | Produtos fabricados (com BOM em JSONB)  |
| 2 | `materials`           | 12                 | Materiais com classificacao ABC/XYZ     |
| 3 | `suppliers`           | 8                  | Fornecedores com metricas de qualidade  |
| 4 | `supplier_materials`  | 14                 | Relacao N:M fornecedor-material         |
| 5 | `purchase_orders`     | 7                  | Pedidos de compra ativos                |
| 6 | `inventory_movements` | 20                 | Movimentacoes de estoque (30 dias)      |
| 7 | `material_forecasts`  | 9                  | Previsoes de demanda (4 meses)          |
| 8 | `equipment`           | 4                  | Equipamentos com health score e OEE     |
| 9 | `production_orders`   | 3                  | Ordens de producao ativas               |
| 10| `quality_records`     | 12                 | NCRs (nao-conformidades)                |
| 11| `sensor_readings`     | ~1536              | Series temporais IoT (48h, 15 min)      |
| 12| `conversations`       | 0                  | Conversas com o sistema                 |
| 13| `messages`            | 0                  | Mensagens dentro de conversas           |
| 14| `agent_decisions`     | 7                  | Decisoes historicas dos agentes         |
| 15| `automation_logs`     | 0                  | Logs de execucao de automacoes N8N      |

### 6.3 Modulo `db.py`

O modulo `db.py` e a camada de acesso a dados, usando `psycopg2` diretamente (sem ORM). Fornece:

**Funcoes genericas:**
- `query(sql, params)` --- executa SELECT, retorna `list[dict]` via `RealDictCursor`
- `query_one(sql, params)` --- executa SELECT, retorna `dict | None`
- `execute(sql, params)` --- executa INSERT/UPDATE/DELETE, retorna rowcount

**Funcoes de dominio (Supply Chain):**
- `get_all_materials(abc_class, critical_only)` --- com status calculado (CRITICO/REPOR/OK)
- `get_material_by_id(material_id)` --- com stock_value, days_of_supply, status
- `get_materials_for_product(product_id)` --- BOM completo via `jsonb_array_elements`
- `get_suppliers_for_material(material_id)` --- JOIN com `supplier_materials`
- `get_purchase_orders(status, material_id)` --- com nome do fornecedor e material
- `get_inventory_movements(material_id, days)` --- movimentacoes recentes
- `get_material_forecasts(material_id)` --- previsoes de demanda com MAPE

**Funcoes de dominio (Qualidade):**
- `get_quality_records(product_id, limit)` --- NCRs com nome do produto
- `get_quality_summary(product_id, days)` --- totais + agrupamento por tipo
- `get_product_compliance(product_id)` --- dados completos do produto

**Funcoes de dominio (Equipamentos/Manutencao):**
- `get_equipment(equipment_id)` --- busca por ID exato, nome parcial, ou todos
- `get_capacity_report(days)` --- calculo real de capacidade (nominal x OEE x downtime)
- `get_latest_sensor_readings(equipment_id)` --- ultima leitura de cada sensor (DISTINCT ON)
- `get_sensor_history(equipment_id, sensor_type, hours)` --- historico de sensor

**Funcoes de dominio (Producao):**
- `get_production_orders(status)` --- com dados do produto (nome, ciclo, custo)
- `get_products()` --- lista completa

**Funcoes de dominio (KPIs):**
- `get_kpis_summary()` --- 4 queries agregadas (equipment, stock, quality, production)

### 6.4 Detalhes Importantes das Queries

**Calculo de status do material (inline):**
```sql
CASE WHEN stock_current < stock_min THEN 'CRITICO'
     WHEN stock_current <= reorder_point THEN 'REPOR'
     ELSE 'OK' END AS status
```

**Calculo de capacidade real:**
```sql
-- Capacidade real = nominal x OEE x (1 - parada_planejada)
ROUND((capacity_pcs_hour * shifts_per_day * hours_per_shift * dias *
       (oee_pct / 100) * (1 - planned_downtime_pct / 100))::numeric, 0) AS real_capacity
```

**BOM via JSONB (lateral join):**
```sql
JOIN LATERAL jsonb_array_elements(p.bom) AS b(elem)
  ON b.elem->>'material_id' = m.id
```

---

## 7. GraphRAG (Neo4j)

O GraphRAG e a camada de conhecimento relacional do NEXUS 4.0. Ele modela as entidades industriais como nos e suas conexoes como arestas em um grafo Neo4j.

### 7.1 Entidades (Nos)

| Label           | Propriedades Principais                                      | Fonte PostgreSQL       |
|-----------------|--------------------------------------------------------------|------------------------|
| `Produto`       | id, nome, descricao, custo_unitario, tempo_ciclo_min         | `products`             |
| `Material`      | id, nome, unidade, categoria, classe_abc, classe_xyz, estoque, custo, consumo_diario, etc. | `materials` |
| `Equipamento`   | id, nome, tipo, health_score, oee, status                    | `equipment`            |
| `Fornecedor`    | id, nome, rating, lead_time_dias, confiabilidade, qualidade, localizacao, certificado_iso | `suppliers` |
| `OrdemProducao` | id, quantidade, status, progresso, prioridade, linha         | `production_orders`    |
| `NCR`           | id, tipo, severidade, causa_raiz, status                     | `quality_records`      |
| `Sensor`        | id (gerado), tipo, valor_atual, unidade, threshold, status   | `sensor_readings` (DISTINCT ON) |
| `PedidoCompra`  | id, quantidade, preco_unitario, total, status, urgencia      | `purchase_orders`      |

### 7.2 Relacoes (Arestas)

| Relacao            | De               | Para            | Propriedades               | Tipo        |
|--------------------|------------------|-----------------|----------------------------|-------------|
| `USA_MATERIAL`     | Produto          | Material        | quantidade, unidade        | Dados (BOM) |
| `FORNECE`          | Fornecedor       | Material        | preco, lead_time, pedido_minimo, preferencial | Dados (supplier_materials) |
| `PRODUZ_PRODUTO`   | OrdemProducao    | Produto         | ---                        | Dados       |
| `AFETA_PRODUTO`    | NCR              | Produto         | ---                        | Dados       |
| `MONITORA`         | Sensor           | Equipamento     | ---                        | Dados       |
| `COMPRADO_DE`      | PedidoCompra     | Fornecedor      | ---                        | Dados       |
| `COMPRA_MATERIAL`  | PedidoCompra     | Material        | ---                        | Dados       |
| `PRODUZ`           | Equipamento      | Produto         | ---                        | **Inferida** |
| `ORIGINADA_EM`     | NCR              | Equipamento     | ---                        | **Inferida** |
| `CONSUMIDO_POR`    | Material         | Equipamento     | tipo (refrigerante, ferramenta_corte, etc.) | **Inferida** |

### 7.3 `graph_populate.py` --- Populacao do Grafo

**Principio: zero hardcode de dados.** O script le TUDO do PostgreSQL e cria o grafo no Neo4j.

**Fluxo:**

```
1. Limpa grafo existente (MATCH (n) DETACH DELETE n)
2. Le tabela products   -> Cria nos Produto
3. Le tabela materials  -> Cria nos Material
4. Le tabela equipment  -> Cria nos Equipamento
5. Le tabela suppliers  -> Cria nos Fornecedor
6. Le production_orders -> Cria nos OrdemProducao
7. Le quality_records   -> Cria nos NCR
8. Le sensor_readings   -> Cria nos Sensor (DISTINCT ON por equipamento + tipo)
9. Cria relacoes a partir de dados:
   - Produto -[USA_MATERIAL]-> Material (via campo JSONB bom)
   - Fornecedor -[FORNECE]-> Material (via tabela supplier_materials)
   - OrdemProducao -[PRODUZ_PRODUTO]-> Produto
   - NCR -[AFETA_PRODUTO]-> Produto
   - Sensor -[MONITORA]-> Equipamento
   - PedidoCompra -[COMPRADO_DE]-> Fornecedor
   - PedidoCompra -[COMPRA_MATERIAL]-> Material
10. Cria relacoes INFERIDAS (logica de negocio):
    - Equipamento -[PRODUZ]-> Produto (via linha de producao)
    - NCR -[ORIGINADA_EM]-> Equipamento (NCRs de produtos em equipamentos com status != operational)
    - Material -[CONSUMIDO_POR]-> Equipamento (mapeamento de consumiveis)
11. Verifica totais (nos e relacoes)
```

**Relacoes inferidas** sao aquelas que nao existem em uma tabela especifica do PostgreSQL, mas sao derivadas da logica de negocio industrial. Exemplo: se a CNC-03 esta na LINHA-01 e a OP-2024-0451 tambem esta na LINHA-01, entao CNC-03 PRODUZ o produto dessa OP.

### 7.4 `graph_retriever.py` --- Consulta ao Grafo

O `GraphRAGRetriever` combina busca por entidade + travessia de relacoes.

#### Fluxo de Consulta

```
retrieve(query)
     |
     v
_extract_entities(query)           <- Identifica IDs por palavras-chave
     |                                 ("aço" -> MP-001, "CNC" -> CNC-03)
     |
     +--- entities encontradas?
     |         |
     |    SIM: _get_entity_context(entity_id)
     |         |
     |         v
     |    Cypher: MATCH (n {id: $id})
     |            OPTIONAL MATCH (n)-[r1]-(n2)      <- 1 hop
     |            OPTIONAL MATCH (n2)-[r2]-(n3)     <- 2 hops
     |            RETURN n, conexoes_diretas, conexoes_2hop
     |
     |    NAO: _broad_search(query)
     |         |
     |         v
     |    Se "risco/problema/status":
     |         Busca equipamentos com status != operational
     |    Se "estoque/material/critico":
     |         Busca materiais com estoque < estoque_min
     |    Senao:
     |         Resumo geral da fabrica (contagem por tipo)
     |
     v
_to_documents(results)             <- Converte para langchain Document
     |
     v
_format_context(ctx)               <- Texto formatado para o LLM
```

#### Queries Especializadas

O `GraphRAGRetriever` expoe tres metodos de consulta especifica:

1. **`get_supply_chain_for_product(product_id)`** --- Toda a cadeia de suprimentos: produto -> materiais -> fornecedores (com estoque, lead time, rating)

2. **`get_impact_chain(equipment_id)`** --- Analise de impacto em cascata: equipamento -> produtos afetados -> ordens impactadas -> NCRs -> sensores -> linhas

3. **`get_quality_chain(product_id)`** --- Cadeia de qualidade: produto -> NCRs (com tipo, severidade, causa raiz, equipamento de origem) -> normas aplicaveis

### 7.5 Como o GraphRAG Complementa o PostgreSQL

```
+-------------------+     +-------------------+
|   PostgreSQL      |     |     Neo4j         |
|   (Detalhes)      |     |   (Conexoes)      |
|                   |     |                   |
| Preco exato do    |     | Quem fornece o    |
| fornecedor X para |     | material Y que e  |
| o material Y      |     | usado no produto Z|
|                   |     | produzido na CNC-03|
| Health score 62   |     | que tem NCR aberta|
| OEE 72.5%         |     | e manutencao      |
| Vibracao 7.2 mm/s |     | PM-2024-156       |
|                   |     | agendada           |
+-------------------+     +-------------------+
         |                         |
         v                         v
+------------------------------------------+
|        Agente (combina ambos)            |
|                                          |
| "A CNC-03 (health: 62, vibracao: 7.2    |
|  mm/s) produz o PROD-001, que tem       |
|  NCR-2024-089 aberta por desgaste de    |
|  ferramenta. Fornecedor ElectroSul      |
|  (R$ 52,00, lead time 5 dias, rating    |
|  4.5) pode fornecer o MP-002."          |
+------------------------------------------+
```

O grafo fornece o **contexto relacional** ("quem se conecta com quem"), enquanto o PostgreSQL fornece os **dados detalhados** (precos, metricas, quantidades). Os agentes usam ambos simultaneamente.

---

## 8. RAG Vetorial (ChromaDB)

O RAG Vetorial armazena documentos tecnicos (normas, procedimentos, manuais) como embeddings para busca semantica.

### 8.1 Pipeline de Ingestao (`rag/ingest.py`)

```
Diretorio de documentos (rag/knowledge_base/)
         |
         v
+---------------------------+
| DirectoryLoader           |
| Suporta: PDF, MD, TXT     |
| (PyPDFLoader, Unstructured|
|  MarkdownLoader, TextLoader)|
+---------------------------+
         |
         v
+---------------------------+
| RecursiveCharacterText    |
| Splitter                  |
| chunk_size: 1000          |
| chunk_overlap: 200        |
| separators: \n\n, \n, . , |
+---------------------------+
         |
         v
+---------------------------+
| OpenAIEmbeddings          |
| modelo: text-embedding-   |
|         3-small           |
+---------------------------+
         |
         v
+---------------------------+
| ChromaDB (porta 8000)     |
| colecao:                  |
| nexus_knowledge_base      |
+---------------------------+
```

### 8.2 Retriever (`rag/retriever.py`)

- **Tipo de busca:** MMR (Maximal Marginal Relevance)
- **Parametros:** k=5, fetch_k=10, lambda_mult=0.7
- **Threshold minimo de relevancia:** 0.3 (para busca com scores)
- Conecta ao ChromaDB via HTTP client ou diretorio local

### 8.3 Documentos de Exemplo (Knowledge Base)

Quando nao ha documentos no diretorio, o sistema cria automaticamente 4 documentos de exemplo:

| Documento     | Tipo              | Area          | Conteudo                                       |
|---------------|-------------------|---------------|------------------------------------------------|
| `PQ-001`      | Procedimento      | Qualidade     | Inspecao de recebimento, amostragem NBR 5426, criterios de aceitacao |
| `MM-CNC-03`   | Manual Manutencao | Manutencao    | Plano preventivo diario/semanal/mensal/semestral, MTBF, MTTR |
| `PGF-001`     | Politica          | Supply Chain  | Classificacao de fornecedores, criterios de avaliacao, lead times |
| `ET-PROD-001` | Especificacao     | Engenharia    | BOM do Eixo ET-500, processo de fabricacao, requisitos de qualidade |

### 8.4 Integracao com Agentes

O RAG vetorial e acionado quando o contexto inclui `use_rag=True`. O conteudo recuperado e injetado como mensagem de sistema com o prefixo "Base de Conhecimento (RAG Vetorial)".

---

## 9. Automacoes N8N

O N8N (porta 5678) executa 4 workflows automatizados que monitoram a operacao e geram alertas.

### 9.1 Workflows

| # | Workflow                       | Arquivo JSON                    | Trigger                  | Endpoint Chamado         |
|---|--------------------------------|---------------------------------|--------------------------|--------------------------|
| 1 | **Monitor de Sensores**        | `monitor_sensores.json`         | Cron a cada 5 minutos    | `GET /monitor/sensors`   |
| 2 | **Alerta de Estoque**          | `alerta_estoque.json`           | Cron a cada 1 hora       | `GET /monitor/inventory` |
| 3 | **Relatorio Diario**           | `relatorio_diario.json`         | Cron as 08:00            | `GET /report/daily`      |
| 4 | **Orquestracao**               | `nexus_orchestration.json`      | Webhook (sob demanda)    | `POST /chat`             |

### 9.2 Fluxo Tipico de Automacao

```
N8N Cron (5 min)
       |
       v
  GET /monitor/sensors
       |
       v
  Resposta: { status: "warning", alerts: [...] }
       |
       v
  Condicao: status != "success"?
       |
  SIM: POST /monitor/log (registra alerta)
       |
       v
  Notificacao (email/webhook/WhatsApp)
```

---

## 10. Dashboards Grafana

O Grafana (porta 3000) conecta diretamente ao PostgreSQL e renderiza 9 dashboards operacionais.

### 10.1 Lista de Dashboards

| # | Dashboard                 | Arquivo JSON            | Conteudo Principal                                    |
|---|---------------------------|-------------------------|-------------------------------------------------------|
| 1 | **Home**                  | `home.json`             | Dashboard inicial com visao geral consolidada         |
| 2 | **Visao Geral**           | `visao_geral.json`      | KPIs globais: OEE medio, health, estoque, qualidade   |
| 3 | **Manutencao**            | `manutencao.json`       | Sensores IoT, health score, tendencias de vibracao     |
| 4 | **Supply Chain**          | `supply_chain.json`     | Niveis de estoque, materiais criticos, pedidos ativos  |
| 5 | **Qualidade**             | `qualidade.json`        | NCRs abertas/fechadas, severidade, causa raiz          |
| 6 | **Financeiro**            | `financeiro.json`       | Valorizacao de estoque, custos, pedidos de compra      |
| 7 | **Materiais**             | `materiais.json`        | Detalhamento por material: classificacao, cobertura    |
| 8 | **Automacoes**            | `automacoes.json`       | Logs de execucao dos workflows N8N                     |
| 9 | **Grafo**                 | `grafo.json`            | Visualizacao das relacoes do GraphRAG                  |

### 10.2 Configuracao

- **Autenticacao:** admin/nexus2024 (configuravel via `GRAFANA_USER`, `GRAFANA_PASSWORD`)
- **Acesso anonimo:** habilitado como Viewer
- **Home dashboard:** `home.json` (configurado via env var)
- **Provisioning:** configuracao automatica via `./grafana/provisioning`
- **Data source:** PostgreSQL (conexao automatica via provisioning)

---

## 11. Integracao WhatsApp (Meta Cloud API)

O NEXUS 4.0 implementa integracao nativa com a Meta WhatsApp Cloud API via o modulo `whatsapp/webhook_handler.py`.

### 11.1 Arquitetura da Integracao

```
                    Meta WhatsApp Cloud API
                    (graph.facebook.com/v21.0)
                              |
                    +---------+---------+
                    |                   |
               Webhook IN          Send OUT
               (POST /webhook)     (POST /{phone_id}/messages)
                    |                   ^
                    v                   |
              +-----+-------------------+-----+
              |      WhatsAppHandler          |
              |-------------------------------|
              | verify_webhook()              |
              | parse_incoming()              |
              | send_message()                |
              | _format_for_whatsapp()        |
              | _split_message()              |
              +-------------------------------+
```

### 11.2 Webhook Verification

A Meta exige verificacao do webhook via GET request:

1. Meta envia `GET /webhook?hub.mode=subscribe&hub.verify_token=nexus40&hub.challenge=XYZ`
2. O handler verifica se `mode == "subscribe"` e `token == verify_token`
3. Retorna o `challenge` em PlainTextResponse (status 200)

### 11.3 Processamento de Mensagens

1. Meta envia `POST /webhook` com payload JSON contendo a mensagem
2. `parse_incoming()` extrai: `entry[0].changes[0].value.messages[0]`
3. Filtra apenas mensagens de tipo `text` (ignora imagens, audio, etc.)
4. Cria `UserRequest` com `user_id = phone` e envia para `POST /chat`
5. Resposta do Coordinator e enviada de volta via `send_message()`

### 11.4 Formatacao de Mensagens

O metodo `_format_for_whatsapp()` converte Markdown para formato WhatsApp:

| Markdown            | WhatsApp          |
|---------------------|-------------------|
| `## Titulo`         | `*Titulo*`        |
| `**bold**`          | `*bold*`          |
| Tabelas markdown    | Blocos numerados  |
| `---` (separador)   | (removido)        |

Tabelas markdown sao convertidas em blocos com a primeira coluna como titulo bold e as demais como linhas indentadas:

```
Markdown:                      WhatsApp:
| Forn | Lead | Preco |        *1. ElectroSul*
|------|------|-------|           Lead: 5 dias
| ElectroSul | 5 | 52 |          Preco: 52
```

### 11.5 Limite de Caracteres

O WhatsApp limita mensagens a 4096 caracteres. O metodo `_split_message()` divide mensagens longas em chunks respeitando paragrafos.

---

## 12. Chat UI (Streamlit)

O Streamlit (porta 8501) e a interface principal de conversacao, definida em `dashboard/streamlit_app.py`.

### 12.1 Paginas

| Pagina                    | Funcionalidade                                                |
|---------------------------|---------------------------------------------------------------|
| **Chat com NEXUS**         | Conversa com o Coordinator (orquestracao completa)            |
| **Consulta Direta**        | Conversa direta com agente especifico (bypass Coordinator)    |
| **Status dos Agentes**     | Visualizacao da arquitetura e metricas em tempo real          |

### 12.2 Graficos Automaticos (Plotly)

O Chat UI detecta automaticamente tabelas markdown nas respostas e gera graficos Plotly:

```
Resposta do agente (markdown com tabela)
              |
              v
     parse_markdown_table()        <- Extrai DataFrame do markdown
              |
              v
     render_chart(df)              <- Gera graficos automaticamente
              |
              +--- Bar chart comparativo (sempre, ate 3 colunas numericas)
              |
              +--- Ranking horizontal (se detecta coluna rating/score/OEE)
```

**Logica de selecao de grafico:**
- **Bar chart comparativo** e sempre gerado com as 3 primeiras colunas numericas
- **Ranking horizontal** e gerado adicionalmente se detecta colunas com nomes como "rating", "score", "oee", "health", "confiab", "qualid"
- Cores padrao: `#3498db`, `#e74c3c`, `#2ecc71`, `#f39c12`, `#9b59b6`
- Escala de cores RdYlGn para rankings

### 12.3 Consulta Direta a Agentes

A pagina "Consulta Direta" permite selecionar um dos 5 agentes e conversar diretamente, sem passar pelo Coordinator:

| Agente        | Endpoint                    |
|---------------|------------------------------|
| Planner (PCP) | `POST /agent/planner`        |
| Quality       | `POST /agent/quality`        |
| Supply Chain  | `POST /agent/supply_chain`   |
| Maintenance   | `POST /agent/maintenance`    |
| Analyst       | `POST /agent/analyst`        |

Cada agente mantem historico de conversa separado no `session_state`.

### 12.4 Sidebar

A sidebar inclui:
- Titulo e descricao do sistema
- Navegacao entre as 3 paginas
- Link direto para o Grafana (dashboards operacionais)
- Creditos: "Sistemas Avancados em Engenharia de Producao e IA --- PPGEPS/Unisinos"

---

## 13. Fluxo de Dados Completo

### Exemplo: "Recebi um pedido urgente de 5000 unidades do Eixo ET-500 para sexta. E viavel?"

```
PASSO 1: ENTRADA
=================
Usuario digita no Chat UI (Streamlit)
  -> POST http://nexus-api:8080/chat
     { "message": "Recebi um pedido urgente de 5000...",
       "user_id": "dashboard" }

PASSO 2: ROTEAMENTO (Coordinator._determine_agents)
====================================================
Palavras detectadas: "pedido" -> PLANNER
                     "5000 unidades" -> PLANNER
                     "ET-500" -> nenhum match explicito
Nenhum match unico -> TODOS OS AGENTES sao acionados
  [PLANNER, QUALITY, SUPPLY_CHAIN, MAINTENANCE, ANALYST]

PASSO 3: DELEGACAO (Coordinator.orchestrate - Fase 1)
=====================================================
Para CADA agente selecionado, o Coordinator envia a tarefa enriquecida:

  3a. PLANNER.think()
      -> tool_choice: "required"
      -> Chama get_equipment_status() -> SQL: SELECT * FROM equipment
      -> Chama get_capacity_report(5) -> SQL: SELECT ... capacidade semanal
      -> Chama get_production_orders() -> SQL: SELECT ... ordens ativas
      -> Retorna: "Capacidade real semanal: 2.640 un. Eixo ET-500 precisa
         de 19 dias. CNC-03 com health 62 (atencao). OP-0453 pode ser
         resequenciada."

  3b. SUPPLY_CHAIN.think()
      -> tool_choice: "required"
      -> Chama check_inventory(product_id="PROD-001") -> SQL: BOM + estoque
      -> Chama get_supplier_info("MP-002") -> SQL: fornecedores do sensor
      -> Retorna: "MP-002 CRITICO (120 un, min 500). Necessidade: 5000 un.
         ElectroSul: R$ 52, 5 dias, rating 4.5.
         TechComponents: R$ 45, 7 dias, rating 4.2.
         GlobalParts: R$ 38.50, 21 dias, rating 3.8."

  3c. QUALITY.think()
      -> tool_choice: "required"
      -> Chama get_quality_records(product_id="PROD-001")
      -> Chama get_product_info("PROD-001")
      -> Retorna: "12 NCRs nos ultimos 30 dias, 3 abertas.
         NCR-2024-089 (major) por desgaste CNC-03.
         Tolerancia +-0.02mm, dureza 58-62 HRC."

  3d. MAINTENANCE.think()
      -> tool_choice: "required"
      -> Chama get_equipment_status("CNC-03")
      -> Chama get_sensor_readings("CNC-03")
      -> Retorna: "CNC-03: health 62, vibracao 7.2 mm/s (threshold 8.0),
         temperatura 68 C. Status: atencao."

  3e. ANALYST.think()
      -> tool_choice: "required"
      -> Chama get_kpis()
      -> Retorna: "OEE medio 83.3%, estoque total R$ X,
         3 ordens ativas totalizando Y unidades."

PASSO 4: CONTEXTO GraphRAG (em paralelo com cada agente)
=========================================================
Cada agente, em think(), consulta o GraphRAG:
  -> graph_retriever.retrieve("pedido 5000 ET-500")
  -> _extract_entities(): "5000" + "PROD-001" detectado
  -> _get_entity_context("PROD-001"):
     Cypher: MATCH (n {id: "PROD-001"})-[r1]-(n2)-[r2]-(n3)
     Retorna:
       Produto: Eixo de Transmissao ET-500
       -> [usa material] -> Material: Barra de Aco SAE 1045 (estoque: 850)
       -> [usa material] -> Material: Sensor de Posicao Angular (estoque: 120)
       -> [afeta produto] <- NCR: NCR-2024-089 (major, desgaste CNC-03)
       -> [produz] <- Equipamento: CNC-03 (health: 62, oee: 72.5%)
       via Material 'Sensor' -> [fornece] <- Fornecedor: ElectroSul
       via Equipamento 'CNC-03' -> [monitora] <- Sensor: vibracao (7.2 mm/s)

PASSO 5: CONSOLIDACAO (Coordinator.orchestrate - Fase 2)
=========================================================
O Coordinator recebe as 5 respostas e chama _consolidate():
  -> SEM tools (tool_choice nao e usado)
  -> Monta prompt com todas as respostas dos agentes
  -> Preserva valores EXATOS (preco 52.00, health 62, etc.)
  -> Gera tabela markdown comparativa + recomendacao

PASSO 6: RESPOSTA
==================
Coordinator retorna resposta consolidada:
  "## Viabilidade do Pedido: 5000 un. Eixo ET-500
   Status: Viavel com ressalvas
   [tabela comparativa de fornecedores]
   [acoes necessarias: compra emergencial, antecipar manutencao]
   [riscos: CNC-03 com vibracao elevada]
   Recomendacao: Aprovar com compra emergencial via ElectroSul"

PASSO 7: INTERFACE
==================
Chat UI (Streamlit):
  -> Renderiza markdown da resposta
  -> parse_markdown_table() detecta a tabela
  -> render_chart() gera grafico Plotly comparativo
  -> Exibe tudo ao usuario

Se WhatsApp configurado:
  -> _format_for_whatsapp() converte tabela para blocos
  -> _split_message() se > 4000 chars
  -> POST graph.facebook.com/v21.0/{phone_id}/messages
```

---

## 14. Integridade de Dados

A integridade de dados e um principio central do NEXUS 4.0, implementado em multiplas camadas.

### 14.1 Prompts de Integridade

O `data_integrity_prompt` e injetado no system prompt de TODOS os agentes (via `BaseAgent.think()`). Ele define regras absolutas:

**O que o agente DEVE fazer:**
1. Citar valores EXATAMENTE como aparecem nos dados
2. Quando entidades tem valores DIFERENTES, citar CADA valor individualmente
3. Usar IDs e nomes EXATOS dos dados
4. Manter a escala original (rating 0-5 permanece 0-5)
5. Diferenciar dados entre entidades

**O que o agente NUNCA deve fazer:**
1. Inventar valores numericos
2. Generalizar dados individuais
3. Converter escalas (rating 4.2/5.0 nao vira 8.4/10)
4. Arredondar valores (96.0% nao vira "quase 100%")
5. Preencher dados ausentes com estimativas
6. Criar metricas derivadas sem base
7. Listar campos como "dado nao disponivel" (deve omitir)

### 14.2 tool_choice: required vs auto

| Cenario                     | tool_choice | Efeito                                      |
|-----------------------------|-------------|----------------------------------------------|
| Agente especialista (sempre)| `required`  | Modelo e OBRIGADO a chamar pelo menos 1 tool |
| Coordinator (delegacao)     | `required`  | Quando `_force_tools=True`                   |
| Coordinator (consolidacao)  | Nao se aplica| `_consolidate()` nao usa tools              |

Isso impede que agentes "improvisem" respostas sem consultar dados reais.

### 14.3 Escopo dos Agentes

Cada agente tem em seu prompt instrucoes explicitas de escopo:

- **Quality**: "NAO invente dados sobre precos, fornecedores ou lead times --- isso e responsabilidade do Supply Chain."
- **Supply Chain**: "Cite APENAS valores que vieram das ferramentas (tools) ou do grafo."
- **Maintenance**: "NUNCA invente valores de sensores, health scores ou IDs de equipamentos."
- **Analyst**: "NUNCA invente dados brutos (precos, NCRs, ratings, percentuais, IDs)."

### 14.4 Coordinator --- Preservacao na Consolidacao

O Coordinator tem regras adicionais para a fase de consolidacao:

- "Preserve todos os valores numericos EXATAMENTE como os agentes informaram"
- "Se um agente disse 'rating 4.2', voce diz 'rating 4.2'"
- "Se um dado nao existe, simplesmente OMITA o campo"
- "Suas analises e recomendacoes podem ser interpretativas, mas os DADOS devem ser fieis"

### 14.5 Fontes de Verdade

```
+-------------------+     +-------------------+
| Fonte Primaria    |     | Fonte Complementar|
|                   |     |                   |
| PostgreSQL        |     | Neo4j (GraphRAG)  |
| (via tools)       |     | (via retrieve())  |
|                   |     |                   |
| Dados detalhados: |     | Relacoes entre    |
| precos, metricas, |     | entidades, cadeias|
| quantidades,      |     | de suprimentos,   |
| series temporais  |     | impacto em cascata|
+-------------------+     +-------------------+
         |                         |
         v                         v
     AMBAS sao confiaveis e complementares.
     Se uma tool retorna um campo, esse dado e REAL
     mesmo que o grafo nao o contenha.
```

---

## 15. Stack Tecnologica

### 15.1 Linguagens e Frameworks

| Componente       | Tecnologia              | Versao/Detalhes                       |
|------------------|-------------------------|---------------------------------------|
| Backend API      | Python + FastAPI         | Async, Pydantic, CORS                 |
| LLM              | OpenAI API              | Modelo: gpt-4.1 (configuravel)        |
| Chat UI          | Streamlit               | Com Plotly para graficos automaticos   |
| Dashboards       | Grafana                 | v11.1.0, provisioning automatico       |
| Automacao        | N8N                     | Workflows JSON, cron + webhook         |

### 15.2 Bancos de Dados

| Banco            | Tecnologia              | Papel                                 |
|------------------|-------------------------|---------------------------------------|
| Relacional       | PostgreSQL 16 Alpine    | Fonte primaria de dados operacionais   |
| Grafo            | Neo4j 5.21 Community    | Grafo de conhecimento (GraphRAG)       |
| Vetorial         | ChromaDB                | RAG vetorial (embeddings)              |

### 15.3 Bibliotecas Python Principais

| Biblioteca       | Uso                                                |
|------------------|----------------------------------------------------|
| `openai`         | Cliente async para API da OpenAI                    |
| `psycopg2`       | Conexao direta com PostgreSQL (RealDictCursor)     |
| `neo4j`          | Driver oficial para Neo4j (Cypher queries)          |
| `langchain-chroma`| Integracao ChromaDB com LangChain                  |
| `langchain-openai`| Embeddings OpenAI via LangChain                    |
| `httpx`          | Cliente HTTP async (envio WhatsApp)                 |
| `pydantic`       | Validacao de dados (modelos de request)              |
| `plotly`         | Graficos interativos no Streamlit                    |
| `pandas`         | Manipulacao de DataFrames (parse de tabelas)         |
| `streamlit`      | Interface web interativa                             |

### 15.4 Infraestrutura

| Componente       | Tecnologia              |
|------------------|-------------------------|
| Containers       | Docker + Docker Compose  |
| Orquestracao     | docker-compose v3.9      |
| Volumes          | Docker named volumes     |
| Rede             | Docker bridge network    |

---

## 16. Como Executar

### 16.1 Pre-requisitos

- Docker e Docker Compose instalados
- Chave de API da OpenAI (`OPENAI_API_KEY`)
- (Opcional) Credenciais da Meta WhatsApp Cloud API

### 16.2 Passo a Passo

```bash
# 1. Clone ou acesse o diretorio do projeto
cd nexus-4.0/

# 2. Copie e configure as variaveis de ambiente
cp .env.example .env
# Edite o .env e insira sua OPENAI_API_KEY

# 3. Suba toda a infraestrutura
docker compose up -d

# 4. Aguarde os health checks (PostgreSQL + Neo4j)
docker compose ps   # Verifique se todos estao "healthy" ou "running"

# 5. Popule o grafo de conhecimento (GraphRAG)
# (apos PostgreSQL e Neo4j estarem prontos)
docker compose exec nexus-api python -m rag.graph_populate

# 6. (Opcional) Ingeste documentos no RAG vetorial
docker compose exec nexus-api python -m rag.ingest

# 7. Acesse os servicos:
#    - Chat UI:    http://localhost:8501
#    - API Docs:   http://localhost:8080/docs  (Swagger)
#    - Grafana:    http://localhost:3000  (admin/nexus2024)
#    - N8N:        http://localhost:5678  (admin/nexus2024)
#    - Neo4j:      http://localhost:7474  (neo4j/nexus2024)
```

### 16.3 Variaveis de Ambiente

| Variavel                    | Padrao        | Descricao                              |
|-----------------------------|---------------|----------------------------------------|
| `OPENAI_API_KEY`            | (obrigatorio) | Chave da API OpenAI                    |
| `OPENAI_MODEL`              | `gpt-4.1`    | Modelo LLM a utilizar                  |
| `POSTGRES_PASSWORD`         | `nexus2024`   | Senha do PostgreSQL                    |
| `NEO4J_PASSWORD`            | `nexus2024`   | Senha do Neo4j                         |
| `N8N_USER` / `N8N_PASSWORD` | `admin` / `nexus2024` | Credenciais do N8N             |
| `GRAFANA_USER` / `GRAFANA_PASSWORD` | `admin` / `nexus2024` | Credenciais do Grafana |
| `WHATSAPP_ACCESS_TOKEN`     | (opcional)    | Token de acesso da Meta                |
| `WHATSAPP_PHONE_NUMBER_ID`  | (opcional)    | ID do numero de telefone na Meta       |
| `WHATSAPP_VERIFY_TOKEN`     | `nexus40`     | Token de verificacao do webhook        |
| `LOG_LEVEL`                 | `INFO`        | Nivel de log (DEBUG, INFO, WARNING)    |

### 16.4 Portas Utilizadas

```
+--------+-------------------+-----------------------------------+
| Porta  | Servico           | Acesso                            |
+--------+-------------------+-----------------------------------+
| 5432   | PostgreSQL        | Conexao interna (agentes, Grafana)|
| 7474   | Neo4j Browser     | http://localhost:7474              |
| 7687   | Neo4j Bolt        | Conexao interna (GraphRAG)        |
| 8000   | ChromaDB          | Conexao interna (RAG vetorial)    |
| 8080   | NEXUS API         | http://localhost:8080/docs         |
| 8501   | Chat UI           | http://localhost:8501              |
| 5678   | N8N               | http://localhost:5678              |
| 3000   | Grafana           | http://localhost:3000              |
| 8085   | Meta Cloud API     | (opcional, profile whatsapp)       |
+--------+-------------------+-----------------------------------+
```

---

## 17. Conceitos Academicos Demonstrados

O NEXUS 4.0 integra e demonstra diversos conceitos relevantes para programas de pos-graduacao em Engenharia de Producao e Inteligencia Artificial:

### 17.1 Engenharia de Producao

| Conceito                            | Onde e Demonstrado                                       |
|-------------------------------------|----------------------------------------------------------|
| **PCP (Planejamento e Controle da Producao)** | PlannerAgent: MPS, MRP, sequenciamento, CRP     |
| **Gestao de Estoques**              | SupplyChainAgent: classificacao ABC/XYZ, EOQ, ROP, estoque de seguranca |
| **Gestao da Qualidade**             | QualityAgent: CEP, Ishikawa, FMEA, NCRs, Cp/Cpk         |
| **Manutencao Industrial**           | MaintenanceAgent: PdM, TPM, RCM, MTBF/MTTR, OEE         |
| **Gestao da Cadeia de Suprimentos** | SupplyChainAgent: avaliacao de fornecedores, TCO, lead time |
| **Teoria das Restricoes (TOC)**     | PlannerAgent: identificacao de gargalos, capacidade      |
| **Lean Manufacturing (OEE)**        | Calculo real de capacidade: nominal x OEE x downtime     |
| **Normas ISO 9001, IATF 16949**     | QualityAgent + RAG vetorial com procedimentos            |

### 17.2 Inteligencia Artificial

| Conceito                            | Onde e Demonstrado                                       |
|-------------------------------------|----------------------------------------------------------|
| **Sistemas Multi-Agente (MAS)**     | 6 agentes com roles, comunicacao e coordenacao            |
| **LLMs (Large Language Models)**    | OpenAI GPT-4.1 como motor de raciocinio dos agentes      |
| **Function Calling / Tool Use**     | Agentes executam queries SQL via tools da API OpenAI      |
| **RAG (Retrieval-Augmented Generation)** | ChromaDB com embeddings + busca MMR                  |
| **GraphRAG (Graph-based RAG)**      | Neo4j com travessia de relacoes ate 2 hops               |
| **Prompt Engineering**              | System prompts especializados por dominio                 |
| **Agente Coordenador (Orquestrador)**| Coordinator: decomposicao, delegacao, consolidacao       |
| **Resolucao de Conflitos**          | Prioridade Seguranca > Qualidade > Prazo > Custo         |
| **Decisoes Estruturadas**           | AgentDecision com confidence, reasoning, risks            |
| **Manutencao Preditiva (PdM)**      | Sensores IoT + analise de tendencias via LLM             |

### 17.3 Engenharia de Software

| Conceito                            | Onde e Demonstrado                                       |
|-------------------------------------|----------------------------------------------------------|
| **Arquitetura de Microsservicos**   | Cada servico em container Docker independente             |
| **API REST**                        | FastAPI com Swagger automatico, validacao Pydantic        |
| **WebSocket**                       | Comunicacao em tempo real para dashboard                   |
| **Event-Driven Architecture**       | N8N workflows com cron triggers e webhooks                |
| **Infrastructure as Code**          | Docker Compose declarativo, provisioning Grafana          |
| **12-Factor App**                   | Configuracao via variaveis de ambiente                    |
| **Observabilidade**                 | Grafana dashboards, logging estruturado, automation_logs  |
| **Tolerancia a Falhas**             | Inicializacao graceful (RAG, GraphRAG, WhatsApp opcionais)|
| **Separacao de Responsabilidades**  | Cada agente com escopo bem definido, db.py como DAL       |

### 17.4 Industria 4.0

| Conceito                            | Onde e Demonstrado                                       |
|-------------------------------------|----------------------------------------------------------|
| **Digital Twin (Gemeo Digital)**    | Representacao digital da fabrica com dados realistas      |
| **IoT (Internet das Coisas)**       | Sensores de vibracao, temperatura, pressao, corrente      |
| **Integracao Vertical**             | Chao de fabrica (sensores) -> Gestao (agentes) -> Interface |
| **Tomada de Decisao Assistida por IA** | Agentes analisam dados e recomendam acoes              |
| **Conectividade (WhatsApp)**        | Gestores recebem alertas e interagem pelo celular         |
| **Grafo de Conhecimento Industrial**| Relacoes entre produtos, materiais, equipamentos, NCRs   |

---

> **NEXUS 4.0** --- Sistema Multi-Agente para Gestao de Operacoes Industriais
> Disciplina: Topicos Avancados de Engenharia de Producao e Inteligencia Artificial
> PPGEPS/Unisinos --- Prof. Dr. Marcos Hoffmann
