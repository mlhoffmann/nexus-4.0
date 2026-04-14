"""
NEXUS 4.0 - Analyst Agent
Business Intelligence e Analytics. Dados reais do PostgreSQL.
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


class AnalystAgent(BaseAgent):
    """Agente Analista — BI e geração de relatórios."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.ANALYST,
            name="Analyst",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        return """Você é o agente ANALYST do sistema NEXUS 4.0.
Especialista em Business Intelligence e Analytics Industrial.

## Competências
- Análise de KPIs operacionais (OEE, OTIF, lead time, throughput)
- Geração de relatórios gerenciais e executivos
- Análise de custo-benefício e ROI
- Análise de tendências e forecasting

## Dados
Todos os dados vêm do banco PostgreSQL (fonte única de verdade).

## USO OBRIGATÓRIO DE FERRAMENTAS
SEMPRE use suas ferramentas (tools) para buscar dados ANTES de responder.

## ESCOPO
Você SOMENTE pode analisar dados que suas ferramentas retornaram.
NUNCA invente dados brutos (preços, NCRs, ratings, percentuais, IDs).
Se um dado não foi retornado, simplesmente não o mencione.

Responda em português brasileiro."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_kpis",
                    "description": "Obtém KPIs consolidados: equipamentos, estoque, qualidade, produção. Dados do PostgreSQL.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stock_valuation",
                    "description": "Valorização do estoque por classe ABC e categoria. Dados do PostgreSQL.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_supplier_rankings",
                    "description": "Ranking de fornecedores por rating, confiabilidade e qualidade. Dados do PostgreSQL.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        try:
            if tool_name == "get_kpis":
                kpis = db.get_kpis_summary()
                return json.loads(json.dumps(kpis, default=_serialize))

            elif tool_name == "get_stock_valuation":
                materials = db.get_all_materials()
                by_abc = {}
                by_category = {}
                total = 0.0
                for m in materials:
                    val = float(m.get("stock_value_brl", 0) or 0)
                    total += val
                    abc = m.get("abc_class", "?")
                    cat = m.get("category", "?")
                    by_abc[abc] = by_abc.get(abc, 0) + val
                    by_category[cat] = by_category.get(cat, 0) + val
                return {
                    "total_value_brl": round(total, 2),
                    "by_abc_class": {k: round(v, 2) for k, v in by_abc.items()},
                    "by_category": {k: round(v, 2) for k, v in by_category.items()},
                    "materials_count": len(materials),
                }

            elif tool_name == "get_supplier_rankings":
                # Query direta para ranking
                suppliers = db.query("""
                    SELECT s.id, s.name, s.rating, s.reliability_pct, s.quality_pct,
                           s.lead_time_days, s.location, s.certified_iso,
                           COUNT(sm.id) AS materials_supplied
                    FROM suppliers s
                    LEFT JOIN supplier_materials sm ON s.id = sm.supplier_id
                    WHERE s.status = 'active'
                    GROUP BY s.id
                    ORDER BY s.rating DESC
                """)
                return json.loads(json.dumps({"suppliers": suppliers}, default=_serialize))

            return {"error": f"Tool '{tool_name}' desconhecida"}
        except Exception as e:
            self.logger.error(f"Erro na tool {tool_name}: {e}")
            return {"error": str(e)}
