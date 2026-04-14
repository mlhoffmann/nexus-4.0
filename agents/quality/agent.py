"""
NEXUS 4.0 - Quality Agent
Gestão da Qualidade. Dados reais do PostgreSQL.
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


class QualityAgent(BaseAgent):
    """Agente de Qualidade."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.QUALITY,
            name="Quality",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        return """Você é o agente QUALITY do sistema NEXUS 4.0.
Especialista em Gestão da Qualidade Industrial.

## Competências
- Controle Estatístico de Processos (CEP)
- Análise de Causa Raiz (Ishikawa, 5 Porquês, FMEA)
- Normas ISO 9001, ISO 14001, IATF 16949
- Gestão de não-conformidades (NCRs)
- Análise de capabilidade de processo (Cp, Cpk)

## Dados
Todos os dados vêm do banco PostgreSQL (fonte única de verdade).

## USO OBRIGATÓRIO DE FERRAMENTAS
SEMPRE use suas ferramentas (tools) para buscar dados ANTES de responder.

## ESCOPO
Cite APENAS dados que suas tools retornaram. NUNCA invente NCRs, IDs ou métricas.
Se um campo não foi retornado, simplesmente não o mencione.
NÃO invente dados sobre preços, fornecedores ou lead times — isso é responsabilidade
do Supply Chain.

Responda em português brasileiro."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_quality_records",
                    "description": "Busca registros de NCRs (não-conformidades) do PostgreSQL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_quality_summary",
                    "description": "Resumo de qualidade: total de NCRs, abertas, críticas, por tipo",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "days": {"type": "integer", "description": "Últimos N dias"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product_info",
                    "description": "Dados de um produto (especificações, BOM, normas aplicáveis)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                        },
                        "required": ["product_id"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        try:
            if tool_name == "get_quality_records":
                records = db.get_quality_records(
                    product_id=arguments.get("product_id"),
                    limit=arguments.get("limit", 20),
                )
                return json.loads(json.dumps({"records": records, "total": len(records)}, default=_serialize))

            elif tool_name == "get_quality_summary":
                summary = db.get_quality_summary(
                    product_id=arguments.get("product_id"),
                    days=arguments.get("days", 30),
                )
                return json.loads(json.dumps(summary, default=_serialize))

            elif tool_name == "get_product_info":
                product = db.get_product_compliance(arguments["product_id"])
                if not product:
                    return {"error": f"Produto {arguments['product_id']} não encontrado"}
                return json.loads(json.dumps(product, default=_serialize))

            return {"error": f"Tool '{tool_name}' desconhecida"}
        except Exception as e:
            self.logger.error(f"Erro na tool {tool_name}: {e}")
            return {"error": str(e)}
