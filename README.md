# NEXUS 4.0 — Sistema Multi-Agente para Gestão de Operações Industriais

> **Estudo de caso para o curso "Sistemas Avançados em Engenharia de Produção e IA"**  
> PPGEPS/Unisinos — Prof. Dr. Marcos Hoffmann

## Visão Geral

O NEXUS 4.0 é um sistema multi-agente que simula uma **sala de guerra virtual** onde 6 agentes de IA colaboram autonomamente para gerenciar operações industriais. O sistema integra:

- **6 Agentes Especializados** com roles distintos (PCP, Qualidade, Supply Chain, Manutenção, Analytics, Coordenação)
- **RAG** (Retrieval-Augmented Generation) sobre normas ISO, manuais técnicos e procedimentos
- **WhatsApp** como interface natural com o gestor
- **Grafana** — 5 dashboards operacionais com dados em tempo real (sensores, estoque, qualidade, OEE, financeiro)
- **Streamlit** — Interface de chat com os agentes
- **N8N** para orquestração de workflows
- **Docker** para deploy containerizado (one-click)

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                        👨‍💼 GESTOR                             │
│              (WhatsApp / Chat UI / Grafana)                   │
└──────┬─────────────────┬──────────────────┬─────────────────┘
       │                 │                  │
┌──────▼──────┐  ┌───────▼───────┐  ┌───────▼──────┐
│  Evolution  │  │   Streamlit   │  │   Grafana    │
│  API (WA)   │  │   Chat UI     │  │  Dashboards  │
│  :8085      │  │   :8501       │  │  :3000       │
└──────┬──────┘  └───────┬───────┘  └───────┬──────┘
       │                 │                  │
┌──────▼─────────────────▼──────────────────│──────────────────┐
│              FastAPI + WebSocket (:8080)   │                  │
└──────────────────────┬────────────────────│─────────────────┘
                       │                    │
┌──────────────────────▼────────────────────│─────────────────┐
│               🧠 COORDINATOR AGENT        │                  │
│      (Orquestra, delega, resolve conflitos)                  │
└──┬──────┬──────┬──────┬──────┬────────────│─────────────────┘
   │      │      │      │      │            │
┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼───┐       │
│ PCP ││Qual ││ SC  ││ Mnt ││Anlst │       │
│Agent││Agent││Agent││Agent││Agent │       │
└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬───┘       │
   │      │      │      │      │            │
┌──▼──────▼──────▼──────▼──────▼────────────▼─────────────────┐
│  PostgreSQL (:5432)  │  ChromaDB (:8000)  │  N8N (:5678)    │
│  Dados operacionais  │  RAG / Embeddings  │  Workflows      │
│  Sensores IoT (TS)   │  Normas / Manuais  │  Automações     │
└─────────────────────────────────────────────────────────────┘
```

## Agentes

| Agente | Role | Responsabilidade | Ferramentas |
|--------|------|------------------|-------------|
| **Coordinator** | Orquestrador | Delega tarefas, resolve conflitos (Segurança > Qualidade > Prazo > Custo) | `delegate_to_agent`, `resolve_conflict` |
| **Planner** | PCP | MPS/MRP, sequenciamento, capacidade, gargalos (TOC) | `check_capacity`, `get_schedule`, `simulate_plan` |
| **Quality** | Qualidade | CEP, FMEA, normas ISO, NCRs, RAG em procedimentos | `get_metrics`, `defect_history`, `compliance` + RAG |
| **Supply Chain** | Suprimentos | Estoque, fornecedores, lead times, compras emergenciais | `check_inventory`, `supplier_info`, `purchase_order` |
| **Maintenance** | Manutenção | Preditiva (sensores IoT), MTBF/MTTR, OEE, health score | `equipment_health`, `schedule`, `predict_failure` |
| **Analyst** | BI/Analytics | KPIs, relatórios executivos, análise de impacto financeiro | `get_kpis`, `calculate_impact`, `generate_report` |

## Quick Start

### 1. Clone e configure

```bash
git clone https://github.com/seu-usuario/nexus-4.0.git
cd nexus-4.0
cp .env.example .env
# Edite .env e adicione sua OPENAI_API_KEY
```

### 2. Suba com Docker

```bash
# Sistema completo (sem WhatsApp)
docker compose up -d

# Com WhatsApp (Evolution API)
docker compose --profile whatsapp up -d
```

### 3. Acesse

| Serviço | URL | Descrição |
|---------|-----|-----------|
| **Grafana** | http://localhost:3000 | Dashboards operacionais (admin/nexus2024) |
| **Chat UI** | http://localhost:8501 | Chat com os agentes (Streamlit) |
| **API** | http://localhost:8080 | REST API + WebSocket |
| **N8N** | http://localhost:5678 | Workflows de automação (admin/nexus2024) |
| **ChromaDB** | http://localhost:8000 | Vector store (RAG) |

### 4. Dashboards Grafana (pré-configurados)

O Grafana já vem com **5 dashboards** prontos conectados ao PostgreSQL:

| Dashboard | O que mostra |
|-----------|-------------|
| **Visão Geral** | OEE, health scores, ordens de produção, decisões dos agentes |
| **Manutenção Preditiva** | Sensores IoT em tempo real (vibração, temperatura, corrente, pressão), health score por equipamento |
| **Supply Chain** | Níveis de estoque vs. mínimo, fornecedores, materiais críticos |
| **Qualidade** | NCRs por tipo/severidade, timeline de não-conformidades |
| **Financeiro** | Valor em estoque, custo por produto, receita potencial |

### 5. Teste via API

```bash
# Chat com o sistema (orquestra todos os agentes)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Recebi um pedido urgente de 5000 unidades do Eixo de Transmissão ET-500 para sexta. É viável?"}'

# Consultar agente diretamente
curl -X POST http://localhost:8080/agent/maintenance \
  -H "Content-Type: application/json" \
  -d '{"agent": "maintenance", "message": "Qual o status da CNC-03?"}'
```

### 6. Ingestão RAG (opcional)

```bash
# Coloque PDFs/docs em rag/knowledge_base/ e execute:
docker compose exec nexus-api python -m rag.ingest
```

## Desenvolvimento Local (sem Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# API
uvicorn main:app --reload --port 8080

# Chat UI (outro terminal)
streamlit run dashboard/streamlit_app.py
```

## Stack Tecnológica

| Componente | Tecnologia | Porta |
|------------|------------|-------|
| Agentes IA | OpenAI GPT-4o + Python | — |
| API | FastAPI + WebSocket | 8080 |
| RAG | LangChain + ChromaDB | 8000 |
| Banco de dados | PostgreSQL 16 | 5432 |
| Dashboards | **Grafana 11** | 3000 |
| Chat UI | Streamlit | 8501 |
| WhatsApp | Evolution API | 8085 |
| Workflows | N8N | 5678 |
| Infra | Docker Compose | — |

## Cenário de Demonstração

O sistema simula uma **fábrica de componentes mecânicos de precisão** com:
- 3 linhas de produção
- 4 equipamentos com sensores IoT (CNC, Prensa, Retífica, Serra)
- 3 produtos no portfólio
- 4 fornecedores (nacional e importado)
- **~2.500 leituras de sensores** pré-carregadas (séries temporais 48h)
- **12 registros de qualidade** (NCRs com diferentes severidades)
- **7 decisões de agentes** no histórico

### Exemplo de Interação

```
Gestor (WhatsApp): "Recebi pedido urgente de 5000 unidades do Eixo de Transmissão ET-500 para sexta"

NEXUS (após orquestrar 5 agentes):
✅ Pedido viável com ressalvas

📋 PCP: Capacidade disponível para 5000 un em 19 dias.
  Necessário resequenciar OP-2024-0453.

📦 Suprimentos: ALERTA - Estoque crítico de MP-002
  (Componente Eletrônico). Necessária compra emergencial
  de 4880 pç. Fornecedor recomendado: ElectroSul (5 dias).

🔧 Manutenção: CNC-03 com health score 62/100.
  Recomenda-se antecipar preventiva antes do pedido.

🔍 Qualidade: Eixo de Transmissão ET-500 conforme ISO 9001.
  Atenção: NCR aberta para defeitos dimensionais na CNC-03.

📊 Impacto Financeiro:
  - Receita adicional: R$ 925.000
  - Custo emergencial MP: R$ 33.800
  - ROI estimado: 188%

⚠️ Riscos:
  1. CNC-03 pode falhar (34% em 18 dias)
  2. Lead time do componente eletrônico
  3. Resequenciamento impacta OP-2024-0453

Aprovar? (Sim/Não)
```

## Estrutura do Projeto

```
nexus-4.0/
├── docker-compose.yml          # Infra containerizada
├── Dockerfile                  # API principal
├── Dockerfile.chat             # Chat UI (Streamlit)
├── main.py                     # FastAPI + WebSocket
├── requirements.txt
├── .env.example
├── agents/
│   ├── base_agent.py           # Classe base (ABC)
│   ├── coordinator/agent.py    # Orquestrador
│   ├── planner/agent.py        # PCP
│   ├── quality/agent.py        # Qualidade + RAG
│   ├── supply_chain/agent.py   # Suprimentos
│   ├── maintenance/agent.py    # Manutenção preditiva
│   └── analyst/agent.py        # BI/Analytics
├── rag/
│   ├── knowledge_base/         # Documentos para RAG
│   ├── ingest.py               # Pipeline de ingestão
│   └── retriever.py            # Retriever com MMR
├── whatsapp/
│   └── webhook_handler.py      # Integração Evolution API
├── dashboard/
│   └── streamlit_app.py        # Chat UI + consulta direta
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/        # PostgreSQL auto-config
│   │   └── dashboards/         # Auto-provisioning
│   └── dashboards/
│       ├── visao_geral.json    # Dashboard Visão Geral
│       ├── manutencao.json     # Dashboard Manutenção Preditiva
│       ├── supply_chain.json   # Dashboard Supply Chain
│       ├── qualidade.json      # Dashboard Qualidade
│       └── financeiro.json     # Dashboard Financeiro
├── n8n/
│   └── workflows/              # Workflows N8N exportados
└── data/
    └── init.sql                # Schema + dados + séries temporais
```

## Conceitos Acadêmicos Demonstrados

- **Sistemas Multi-Agente (MAS)** — Agentes autônomos com comunicação, coordenação e resolução de conflitos
- **RAG (Retrieval-Augmented Generation)** — IA com base de conhecimento técnico (normas, manuais)
- **Indústria 4.0** — IoT, manutenção preditiva, digital twin, sensores em tempo real
- **Engenharia de Produção** — PCP, MRP, CEP, TOC, TPM, FMEA, OEE, OTIF
- **IA Generativa** — LLMs como motor de decisão em contexto industrial
- **Observabilidade** — Grafana com séries temporais e alertas threshold

## Licença

Projeto acadêmico — uso livre para fins educacionais.

---

**PPGEPS/Unisinos** — Sistemas Avançados em Engenharia de Produção e IA
