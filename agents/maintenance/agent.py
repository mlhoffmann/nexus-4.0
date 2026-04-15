"""
NEXUS 4.0 - Maintenance Agent
Manutenção preditiva e gestão de ativos. Dados reais do PostgreSQL.
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


class MaintenanceAgent(BaseAgent):
    """Agente de Manutenção Preditiva."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.MAINTENANCE,
            name="Maintenance",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        return """Você é o agente MAINTENANCE do sistema NEXUS 4.0.
Especialista em Manutenção Industrial e Gestão de Ativos.

## Competências
- Manutenção Preditiva (PdM) baseada em dados de sensores
- Análise de vibração, temperatura, pressão e corrente
- OEE (Overall Equipment Effectiveness)
- MTBF/MTTR
- TPM e RCM

## Dados
Todos os dados vêm do banco PostgreSQL (fonte única de verdade).
Sensores IoT com leituras reais em séries temporais.

## USO OBRIGATÓRIO DE FERRAMENTAS
SEMPRE use suas ferramentas (tools) para buscar dados ANTES de responder.

## ESCOPO
Cite APENAS dados que suas tools retornaram. NUNCA invente valores de sensores,
health scores ou IDs de equipamentos.
Se um campo não foi retornado, simplesmente não o mencione.

Responda em português brasileiro."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_equipment_status",
                    "description": "Status de um ou todos os equipamentos (health score, OEE, status). Dados do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "equipment_id": {"type": "string", "description": "ID do equipamento. Se vazio, retorna todos."},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sensor_readings",
                    "description": "Leituras mais recentes dos sensores IoT de um equipamento. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "equipment_id": {"type": "string"},
                        },
                        "required": ["equipment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_maintenance_history",
                    "description": "Histórico de manutenções realizadas em um equipamento. Retorna tipo, data, duração, ações realizadas, peças trocadas, custo e técnico. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "equipment_id": {"type": "string", "description": "ID do equipamento. Se vazio, retorna todas as manutenções."},
                            "limit": {"type": "integer", "description": "Número máximo de registros (padrão 10)"},
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
                return json.loads(json.dumps(
                    {"equipment": result if isinstance(result, list) else [result]} if result else {"equipment": []},
                    default=_serialize,
                ))

            elif tool_name == "get_sensor_readings":
                readings = db.get_latest_sensor_readings(arguments["equipment_id"])
                return json.loads(json.dumps({
                    "equipment_id": arguments["equipment_id"],
                    "sensors": readings,
                }, default=_serialize))

            elif tool_name == "get_maintenance_history":
                history = db.get_maintenance_history(
                    equipment_id=arguments.get("equipment_id"),
                    limit=arguments.get("limit", 10),
                )
                return json.loads(json.dumps({
                    "equipment_id": arguments.get("equipment_id"),
                    "history": history,
                    "total": len(history),
                }, default=_serialize))

            return {"error": f"Tool '{tool_name}' desconhecida"}
        except Exception as e:
            self.logger.error(f"Erro na tool {tool_name}: {e}")
            return {"error": str(e)}
