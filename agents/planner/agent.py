"""
NEXUS 4.0 - Planner Agent (PCP)
Planejamento e Controle da Produção. Dados reais do PostgreSQL.
"""

import json
from decimal import Decimal
from typing import Any

import db
from agents.base_agent import AgentRole, BaseAgent


def _serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


class PlannerAgent(BaseAgent):
    """Agente de Planejamento e Controle da Produção."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.PLANNER,
            name="Planner (PCP)",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        return """Você é o agente PLANNER (PCP) do sistema NEXUS 4.0.
Especialista em Planejamento e Controle da Produção.

## Competências
- Planejamento Mestre de Produção (MPS)
- MRP (Planejamento de Necessidades de Materiais)
- Sequenciamento e programação de produção
- Análise de capacidade produtiva (CRP)
- Teoria das Restrições (TOC)

## Dados
Todos os dados vêm do banco PostgreSQL (fonte única de verdade).

## USO OBRIGATÓRIO DE FERRAMENTAS
SEMPRE use suas ferramentas (tools) para buscar dados ANTES de responder.

## ESCOPO
Cite APENAS dados que suas tools retornaram. NUNCA invente valores.
Se um campo não foi retornado, simplesmente não o mencione.

Responda em português brasileiro."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_production_orders",
                    "description": "Lista ordens de produção com produto, quantidade, status, progresso. Dados do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["em_andamento", "planned", "completed"]},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_products",
                    "description": "Lista todos os produtos com tempo de ciclo, custo e BOM. Dados do PostgreSQL.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_equipment_status",
                    "description": "Status de um equipamento específico ou todos: health score, OEE, capacidade, turnos, status, linha. Use para perguntas sobre disponibilidade, status ou dados de um equipamento. Dados do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "equipment_id": {"type": "string", "description": "ID do equipamento (ex: CNC-03, SERRA-01). Se vazio, retorna todos."},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_capacity_report",
                    "description": "Relatório de capacidade produtiva SEMANAL: capacidade nominal, real (ajustada por OEE), horas disponíveis, por equipamento. Use para perguntas sobre capacidade total, quanto pode produzir. Dados do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "description": "Número de dias úteis (padrão 5 = 1 semana)"},
                        },
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        try:
            if tool_name == "get_equipment_status":
                eq_id = arguments.get("equipment_id")
                result = db.get_equipment(eq_id)
                if eq_id and not result:
                    return {"error": f"Equipamento {eq_id} não encontrado"}
                data = result if isinstance(result, list) else [result] if result else []
                return json.loads(json.dumps({"equipment": data}, default=_serialize))

            elif tool_name == "get_production_orders":
                orders = db.get_production_orders(status=arguments.get("status"))
                return json.loads(json.dumps({
                    "orders": orders,
                    "total": len(orders),
                }, default=_serialize))

            elif tool_name == "get_capacity_report":
                days = arguments.get("days", 5)
                capacity = db.get_capacity_report(days=days)
                total_real = sum(int(c.get("real_capacity", 0) or 0) for c in capacity)
                return json.loads(json.dumps({
                    "period_days": days,
                    "equipment": capacity,
                    "total_real_capacity": total_real,
                }, default=_serialize))

            elif tool_name == "get_products":
                products = db.get_products()
                return json.loads(json.dumps({"products": products}, default=_serialize))

            return {"error": f"Tool '{tool_name}' desconhecida"}
        except Exception as e:
            self.logger.error(f"Erro na tool {tool_name}: {e}")
            return {"error": str(e)}
