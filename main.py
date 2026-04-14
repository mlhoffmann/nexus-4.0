"""
NEXUS 4.0 - API Principal
Sistema Multi-Agente para Gestão de Operações Industriais.
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

from agents import (
    AnalystAgent,
    CoordinatorAgent,
    MaintenanceAgent,
    PlannerAgent,
    QualityAgent,
    SupplyChainAgent,
)
from whatsapp.webhook_handler import WhatsAppHandler

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nexus")

# Estado global do sistema
nexus_state = {
    "coordinator": None,
    "agents": {},
    "whatsapp": None,
    "conversations": {},
    "websocket_clients": [],
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa e finaliza o sistema NEXUS."""
    logger.info("=" * 60)
    logger.info("  NEXUS 4.0 - Inicializando Sistema Multi-Agente")
    logger.info("=" * 60)

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1")

    # Tenta inicializar RAG vetorial (ChromaDB - opcional)
    rag_retriever = None
    try:
        from rag.retriever import RAGRetriever

        rag_retriever = RAGRetriever()
        logger.info("RAG Vetorial (ChromaDB) conectado")
    except Exception as e:
        logger.warning(f"RAG Vetorial não disponível: {e}")

    # Tenta inicializar GraphRAG (Neo4j - opcional)
    graph_retriever = None
    try:
        from rag.graph_retriever import GraphRAGRetriever

        graph_retriever = GraphRAGRetriever()
        nexus_state["graph_retriever"] = graph_retriever
        logger.info("GraphRAG (Neo4j) conectado")
    except Exception as e:
        logger.warning(f"GraphRAG não disponível: {e}")

    # Inicializa agentes (com ambos os retrievers)
    agents = {
        "planner": PlannerAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever),
        "quality": QualityAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever),
        "supply_chain": SupplyChainAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever),
        "maintenance": MaintenanceAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever),
        "analyst": AnalystAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever),
    }

    coordinator = CoordinatorAgent(openai_client, model=model, rag_retriever=rag_retriever, graph_retriever=graph_retriever)
    for agent in agents.values():
        coordinator.register_agent(agent)

    nexus_state["coordinator"] = coordinator
    nexus_state["agents"] = agents

    # WhatsApp handler (opcional)
    try:
        nexus_state["whatsapp"] = WhatsAppHandler()
        logger.info("WhatsApp handler inicializado")
    except Exception as e:
        logger.warning(f"WhatsApp não configurado: {e}")

    logger.info(f"Sistema NEXUS 4.0 online com {len(agents) + 1} agentes")
    logger.info("=" * 60)

    yield

    logger.info("NEXUS 4.0 - Desligando...")


app = FastAPI(
    title="NEXUS 4.0",
    description="Sistema Multi-Agente para Gestão de Operações Industriais",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Modelos
# ============================================


class UserRequest(BaseModel):
    message: str
    user_id: str = "gestor"
    conversation_id: str | None = None
    context: dict | None = None


class AgentQuery(BaseModel):
    agent: str
    message: str
    context: dict | None = None


# ============================================
# Endpoints
# ============================================


@app.get("/")
async def root():
    agents_info = {}
    if nexus_state["coordinator"]:
        for role, agent in nexus_state["coordinator"].agent_registry.items():
            agents_info[role.value] = {"name": agent.name, "role": role.value}
    return {
        "system": "NEXUS 4.0",
        "status": "online",
        "agents": agents_info,
        "version": "4.0.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agents_active": len(nexus_state.get("agents", {})) + 1,
        "rag_available": nexus_state.get("rag") is not None,
        "whatsapp_connected": nexus_state.get("whatsapp") is not None,
    }


@app.post("/chat")
async def chat(request: UserRequest):
    """Endpoint principal — envia mensagem para o Coordinator que orquestra tudo."""
    coordinator = nexus_state["coordinator"]
    if not coordinator:
        return {"error": "Sistema não inicializado"}

    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Notifica WebSocket clients
    await _broadcast_ws({
        "type": "user_message",
        "conversation_id": conversation_id,
        "content": request.message,
        "timestamp": datetime.now().isoformat(),
    })

    # Orquestra via Coordinator
    response = await coordinator.orchestrate(
        user_request=request.message,
        conversation_id=conversation_id,
        context=request.context,
    )

    # Notifica WebSocket clients
    await _broadcast_ws({
        "type": "coordinator_response",
        "conversation_id": conversation_id,
        "content": response,
        "timestamp": datetime.now().isoformat(),
    })

    # Envia via WhatsApp se configurado
    if nexus_state.get("whatsapp") and request.user_id != "dashboard":
        try:
            await nexus_state["whatsapp"].send_message(request.user_id, response)
        except Exception as e:
            logger.warning(f"Erro ao enviar WhatsApp: {e}")

    return {
        "conversation_id": conversation_id,
        "response": response,
        "agents_involved": list(coordinator.agent_registry.keys()),
    }


@app.post("/agent/{agent_name}")
async def query_agent(agent_name: str, query: AgentQuery):
    """Consulta direta a um agente específico (para debug/demo)."""
    agents = nexus_state.get("agents", {})
    agent = agents.get(agent_name)
    if not agent:
        return {"error": f"Agente '{agent_name}' não encontrado", "available": list(agents.keys())}

    response = await agent.think(query.message, query.context)
    return {"agent": agent_name, "response": response}


@app.get("/agents")
async def list_agents():
    """Lista todos os agentes e seus status."""
    agents = nexus_state.get("agents", {})
    result = {}
    for name, agent in agents.items():
        result[name] = {
            "name": agent.name,
            "role": agent.role.value,
            "memory_size": len(agent.memory),
            "messages_processed": len(agent.message_history),
        }
    return result


# ============================================
# Endpoints de Monitoramento (chamados pelo N8N)
# ============================================


@app.get("/monitor/sensors")
async def monitor_sensors():
    """Verifica sensores de todos os equipamentos. Chamado pelo N8N a cada 5 min."""
    maintenance = nexus_state.get("agents", {}).get("maintenance")
    if not maintenance:
        return {"error": "Agente de manutenção não disponível"}

    alerts = []
    equipment_list = ["CNC-03", "PRENSA-01", "RETIFICA-01", "SERRA-01"]

    for eq_id in equipment_list:
        health = await maintenance.execute_tool("get_equipment_health", {"equipment_id": eq_id, "include_sensors": True})
        if health.get("health_score", 100) < 75 or health.get("alerts"):
            alerts.append({
                "equipment_id": eq_id,
                "health_score": health.get("health_score"),
                "status": health.get("status"),
                "alerts": health.get("alerts", []),
                "sensors": health.get("sensors"),
            })

    status = "success"
    summary = f"Verificados {len(equipment_list)} equipamentos."
    if alerts:
        critical = [a for a in alerts if a["health_score"] < 50]
        if critical:
            status = "critical"
            summary += f" {len(critical)} CRÍTICO(s)!"
        else:
            status = "warning"
            summary += f" {len(alerts)} em atenção."
    else:
        summary += " Todos normais."

    return {
        "status": status,
        "summary": summary,
        "equipment_checked": len(equipment_list),
        "alerts": alerts,
        "alert_count": len(alerts),
    }


@app.get("/monitor/inventory")
async def monitor_inventory():
    """Verifica níveis de estoque. Chamado pelo N8N a cada 1h."""
    supply_chain = nexus_state.get("agents", {}).get("supply_chain")
    if not supply_chain:
        return {"error": "Agente de supply chain não disponível"}

    inventory = await supply_chain.execute_tool("check_inventory", {"product_id": "PROD-001"})
    critical_materials = [
        m for m in inventory.get("bom_status", []) if m.get("status") == "critico"
    ]

    status = "success"
    summary = f"Verificados {inventory.get('total_materials', 0)} materiais."
    if critical_materials:
        status = "critical"
        names = ", ".join([m["name"] for m in critical_materials])
        summary += f" CRÍTICO: {names}"
    else:
        summary += " Estoques adequados."

    return {
        "status": status,
        "summary": summary,
        "materials_checked": inventory.get("total_materials", 0),
        "critical": critical_materials,
        "critical_count": len(critical_materials),
        "all_materials": inventory.get("bom_status", []),
    }


@app.post("/monitor/log")
async def log_automation(entry: dict):
    """Registra execução de automação N8N no banco. Chamado pelo N8N após cada workflow."""
    # Em produção, gravaria no PostgreSQL via SQLAlchemy
    logger.info(
        f"[AUTOMAÇÃO] {entry.get('workflow_name')}: {entry.get('status')} — {entry.get('summary')}"
    )
    return {"logged": True}


@app.get("/report/daily")
async def daily_report():
    """Gera relatório diário consolidado. Chamado pelo N8N às 8h."""
    coordinator = nexus_state["coordinator"]
    if not coordinator:
        return {"error": "Sistema não inicializado"}

    report = await coordinator.orchestrate(
        user_request="Gere um relatório executivo diário com: status de produção, qualidade, "
                     "estoque, manutenção e indicadores financeiros. Destaque riscos e ações urgentes.",
        conversation_id=str(uuid.uuid4()),
        context={"source": "automated_daily_report"},
    )

    return {
        "status": "success",
        "report": report,
        "generated_by": "n8n_cron",
    }


@app.post("/rag/query")
async def rag_query(query: dict):
    """Consulta direta ao sistema RAG."""
    try:
        from rag.retriever import RAGRetriever

        retriever = RAGRetriever()
        docs = await retriever.retrieve(query.get("query", ""), k=query.get("k", 5))
        return {
            "query": query.get("query"),
            "results": [
                {"content": doc.page_content, "metadata": doc.metadata} for doc in docs
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/rag/stats")
async def rag_stats():
    """Estatísticas da base RAG."""
    try:
        from rag.retriever import RAGRetriever

        retriever = RAGRetriever()
        return retriever.get_collection_stats()
    except Exception as e:
        return {"error": str(e)}


# ============================================
# GraphRAG Endpoints
# ============================================


@app.post("/graphrag/query")
async def graphrag_query(query: dict):
    """Consulta o grafo de conhecimento."""
    graph = nexus_state.get("graph_retriever")
    if not graph:
        return {"error": "GraphRAG não disponível (Neo4j offline?)"}

    docs = await graph.retrieve(query.get("query", ""), k=query.get("k", 5))
    return {
        "query": query.get("query"),
        "results": [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs],
    }


@app.get("/graphrag/impact/{equipment_id}")
async def graphrag_impact(equipment_id: str):
    """Análise de impacto em cascata de um equipamento via grafo."""
    graph = nexus_state.get("graph_retriever")
    if not graph:
        return {"error": "GraphRAG não disponível"}
    return {"equipment_id": equipment_id, "impact_analysis": graph.get_impact_chain(equipment_id)}


@app.get("/graphrag/supply-chain/{product_id}")
async def graphrag_supply_chain(product_id: str):
    """Cadeia de suprimentos completa de um produto via grafo."""
    graph = nexus_state.get("graph_retriever")
    if not graph:
        return {"error": "GraphRAG não disponível"}
    return {"product_id": product_id, "supply_chain": graph.get_supply_chain_for_product(product_id)}


@app.get("/graphrag/quality/{product_id}")
async def graphrag_quality(product_id: str):
    """Cadeia de qualidade de um produto via grafo."""
    graph = nexus_state.get("graph_retriever")
    if not graph:
        return {"error": "GraphRAG não disponível"}
    return {"product_id": product_id, "quality_chain": graph.get_quality_chain(product_id)}


@app.post("/graphrag/populate")
async def graphrag_populate():
    """Popula/repopula o grafo de conhecimento."""
    try:
        from rag.graph_populate import populate_graph
        populate_graph()
        return {"status": "success", "message": "Grafo de conhecimento populado"}
    except Exception as e:
        return {"error": str(e)}


# ============================================
# WhatsApp Webhook
# ============================================


@app.get("/webhook")
async def webhook_verify_meta(request: Request):
    """Verificação do webhook pela Meta. Responde ao challenge."""
    params = dict(request.query_params)
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    logger.info(f"Webhook verify: mode={mode}, token={token}, challenge={challenge[:20]}...")

    handler = nexus_state.get("whatsapp")
    if not handler:
        logger.warning("WhatsApp handler não configurado")
        return PlainTextResponse(challenge, status_code=200)

    result = handler.verify_webhook(mode, token, challenge)
    if result:
        return PlainTextResponse(result, status_code=200)

    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def whatsapp_webhook_meta(payload: dict):
    """Recebe mensagens do WhatsApp via Meta Cloud API."""
    handler = nexus_state.get("whatsapp")
    if not handler:
        return {"status": "ok"}  # Meta espera 200 mesmo sem handler

    message = handler.parse_incoming(payload)
    if not message:
        return {"status": "ok"}

    # Processa via Coordinator
    request = UserRequest(
        message=message["text"],
        user_id=message["phone"],
    )
    result = await chat(request)
    return {"status": "processed", "conversation_id": result["conversation_id"]}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook_legacy(payload: dict):
    """Compatibilidade com webhook antigo."""
    return await whatsapp_webhook_meta(payload)


# ============================================
# WebSocket (Dashboard em tempo real)
# ============================================


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket para dashboard em tempo real."""
    await ws.accept()
    nexus_state["websocket_clients"].append(ws)
    logger.info("Dashboard conectado via WebSocket")

    try:
        while True:
            data = await ws.receive_text()
            # Permite enviar mensagens via WebSocket também
            msg = json.loads(data)
            if msg.get("type") == "chat":
                request = UserRequest(message=msg["content"], user_id="dashboard")
                result = await chat(request)
                await ws.send_json(result)
    except WebSocketDisconnect:
        nexus_state["websocket_clients"].remove(ws)
        logger.info("Dashboard desconectado")


async def _broadcast_ws(message: dict):
    """Envia mensagem para todos os WebSocket clients conectados."""
    disconnected = []
    for ws in nexus_state["websocket_clients"]:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        nexus_state["websocket_clients"].remove(ws)
