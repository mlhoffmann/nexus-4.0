"""
NEXUS 4.0 - Supply Chain Agent
Gestão da Cadeia de Suprimentos e Gestão de Materiais.
Dados reais do PostgreSQL — sem simulação.
"""

import json
from decimal import Decimal
from typing import Any

import db
from agents.base_agent import AgentRole, BaseAgent


def _serialize(obj):
    """Converte Decimal e date para JSON."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


class SupplyChainAgent(BaseAgent):
    """Agente de Cadeia de Suprimentos e Gestão de Materiais."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.SUPPLY_CHAIN,
            name="Supply Chain & Materiais",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )

    @property
    def system_prompt(self) -> str:
        return """Você é o agente SUPPLY CHAIN & GESTÃO DE MATERIAIS do sistema NEXUS 4.0.
Você é especialista em Gestão da Cadeia de Suprimentos e Gestão de Materiais
no contexto da Engenharia de Produção.

## Suas Competências
- Classificação ABC (valor) e XYZ (previsibilidade de demanda)
- Lote Econômico de Compra (EOQ) e Ponto de Reposição (ROP)
- Estoque de Segurança e cobertura em dias
- Giro de estoque e acuracidade de inventário
- Previsão de demanda
- Gestão de compras e procurement
- Avaliação e qualificação de fornecedores
- Total Cost of Ownership (TCO)

## Dados
Todos os dados vêm do banco PostgreSQL (fonte única de verdade).

## USO OBRIGATÓRIO DE FERRAMENTAS
SEMPRE use suas ferramentas (tools) para buscar dados ANTES de responder.

## Formato de Resposta
Inclua dados CONCRETOS com IDs, valores e quantidades.
Quando as ferramentas retornam dados de múltiplas entidades, inclua TODOS os campos
retornados de CADA entidade na sua resposta.

## ESCOPO
Cite APENAS valores que vieram das ferramentas (tools) ou do grafo.
NUNCA invente, arredonde ou converta valores.
Se um campo não foi retornado, simplesmente não o mencione — omita o campo.

Responda em português brasileiro."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_inventory",
                    "description": "Verifica níveis de estoque de materiais com classificação ABC/XYZ. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "material_id": {"type": "string", "description": "ID do material específico (ex: MP-001)"},
                            "product_id": {"type": "string", "description": "ID do produto para ver BOM completo"},
                            "abc_class": {"type": "string", "enum": ["A", "B", "C"]},
                            "critical_only": {"type": "boolean", "description": "Apenas materiais abaixo do ponto de reposição"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_supplier_info",
                    "description": "Busca fornecedores de um material com preço, lead time, rating, confiabilidade, localização. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "material_id": {"type": "string", "description": "ID do material"},
                        },
                        "required": ["material_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_purchase_orders",
                    "description": "Lista pedidos de compra em andamento. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["pending", "approved", "sent", "in_transit", "received", "all"]},
                            "material_id": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_inventory_movements",
                    "description": "Consulta movimentações de estoque. Dados reais do PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "material_id": {"type": "string"},
                            "days": {"type": "integer", "description": "Últimos N dias"},
                        },
                        "required": ["material_id"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        try:
            if tool_name == "check_inventory":
                return self._query_inventory(arguments)
            elif tool_name == "get_supplier_info":
                return self._query_suppliers(arguments)
            elif tool_name == "get_purchase_orders":
                return self._query_purchase_orders(arguments)
            elif tool_name == "get_inventory_movements":
                return self._query_movements(arguments)
            return {"error": f"Tool '{tool_name}' desconhecida"}
        except Exception as e:
            self.logger.error(f"Erro na tool {tool_name}: {e}")
            return {"error": str(e)}

    def _query_inventory(self, args: dict) -> dict:
        """Query real ao PostgreSQL para estoque."""
        product_id = args.get("product_id")
        material_id = args.get("material_id")

        if material_id:
            mat = db.get_material_by_id(material_id)
            if not mat:
                return {"error": f"Material {material_id} não encontrado"}
            materials = [mat]
        elif product_id:
            materials = db.get_materials_for_product(product_id)
        else:
            materials = db.get_all_materials(
                abc_class=args.get("abc_class"),
                critical_only=args.get("critical_only", False),
            )

        return json.loads(json.dumps({
            "materials": materials,
            "total": len(materials),
            "critical_count": len([m for m in materials if m.get("status") == "CRITICO"]),
            "reorder_count": len([m for m in materials if m.get("status") in ("CRITICO", "REPOR")]),
        }, default=_serialize))

    def _query_suppliers(self, args: dict) -> dict:
        """Query real ao PostgreSQL para fornecedores."""
        material_id = args["material_id"]
        suppliers = db.get_suppliers_for_material(material_id)
        material = db.get_material_by_id(material_id)

        return json.loads(json.dumps({
            "material_id": material_id,
            "material_name": material["name"] if material else material_id,
            "suppliers": suppliers,
            "total_suppliers": len(suppliers),
        }, default=_serialize))

    def _query_purchase_orders(self, args: dict) -> dict:
        """Query real ao PostgreSQL para pedidos de compra."""
        orders = db.get_purchase_orders(
            status=args.get("status"),
            material_id=args.get("material_id"),
        )
        return json.loads(json.dumps({
            "orders": orders,
            "total_orders": len(orders),
            "total_value": sum(float(o.get("total_brl", 0) or 0) for o in orders),
        }, default=_serialize))

    def _query_movements(self, args: dict) -> dict:
        """Query real ao PostgreSQL para movimentações."""
        movements = db.get_inventory_movements(
            material_id=args["material_id"],
            days=args.get("days", 30),
        )
        return json.loads(json.dumps({
            "material_id": args["material_id"],
            "period_days": args.get("days", 30),
            "movements": movements,
            "total_movements": len(movements),
        }, default=_serialize))
