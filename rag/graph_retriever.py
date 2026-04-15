"""
NEXUS 4.0 - GraphRAG Retriever
Consulta o grafo de conhecimento no Neo4j para enriquecer o contexto dos agentes.
Combina busca por entidade + travessia de relações + RAG vetorial.
"""

import logging
import os
from typing import Any

from neo4j import GraphDatabase

logger = logging.getLogger("nexus.graphrag")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "nexus2024")


class GraphRAGRetriever:
    """Retriever que combina Neo4j (grafo) com contexto relacional."""

    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        logger.info("GraphRAG Retriever conectado ao Neo4j")

    def close(self):
        self.driver.close()

    async def retrieve(self, query: str, k: int = 5) -> list:
        """Busca no grafo baseado na query. Retorna documentos formatados."""
        results = []

        # Identifica entidades mencionadas na query
        entities = self._extract_entities(query)

        with self.driver.session() as session:
            for entity_id in entities:
                # Busca o nó e todas as suas relações (1-2 hops)
                context = self._get_entity_context(session, entity_id)
                if context:
                    results.append(context)

            # Se não encontrou entidades específicas, faz busca ampla
            if not results:
                results = self._broad_search(session, query)

        # Converte para formato compatível com o RAG existente
        return self._to_documents(results, k)

    def _extract_entities(self, query: str) -> list[str]:
        """Extrai IDs de entidades mencionadas na query."""
        query_upper = query.upper()
        entities = []

        # Produtos
        for pid in ["PROD-001", "PROD-002", "PROD-003", "PROD-004", "PROD-005", "PROD-006", "PROD-007", "PROD-008"]:
            if pid in query_upper:
                entities.append(pid)
        if "EIXO" in query_upper or "ET-500" in query_upper or "TRANSMISS" in query_upper:
            entities.append("PROD-001")
        if "ENGRENAGEM" in query_upper or "EH-200" in query_upper or "HELICOIDAL" in query_upper:
            entities.append("PROD-002")
        if "BUCHA" in query_upper or "BM-100" in query_upper or "MANCAL" in query_upper:
            entities.append("PROD-003")
        if "FLANGE" in query_upper or "FA-300" in query_upper or "ACOPLAMENTO" in query_upper:
            entities.append("PROD-004")
        if "PINO" in query_upper or "PG-150" in query_upper or "GUIA" in query_upper:
            entities.append("PROD-005")
        if "CAME" in query_upper or "CC-250" in query_upper or "COMANDO" in query_upper:
            entities.append("PROD-006")
        if "LUVA" in query_upper or "LE-180" in query_upper or "ESTRIADA" in query_upper:
            entities.append("PROD-007")
        if "POLIA" in query_upper or "PS-120" in query_upper or "SINCRONIZADORA" in query_upper:
            entities.append("PROD-008")

        # Equipamentos
        for eid in ["CNC-03", "PRENSA-01", "RETIFICA-01", "SERRA-01"]:
            if eid in query_upper:
                entities.append(eid)

        # Materiais
        for mid in ["MP-001", "MP-002", "MP-003", "MP-004", "MP-005", "MP-006", "MP-007"]:
            if mid in query_upper:
                entities.append(mid)
        if "SENSOR" in query_upper or "POSIÇÃO ANGULAR" in query_upper or "POSICAO ANGULAR" in query_upper:
            entities.append("MP-002")
        if "AÇO" in query_upper or "ACO" in query_upper or "SAE 1045" in query_upper:
            entities.append("MP-001")
        if "INSERTO" in query_upper or "CNMG" in query_upper or "METAL DURO" in query_upper:
            entities.append("MP-005")
        if "ROLAMENTO" in query_upper or "SKF" in query_upper:
            entities.append("MP-006")
        if "REBOLO" in query_upper or "ABRASIVO" in query_upper:
            entities.append("MP-010")

        # Fornecedores
        if "ELECTROSUL" in query_upper:
            entities.append("FORN-003")
        if "TECHCOMPONENT" in query_upper:
            entities.append("FORN-001")
        if "GLOBALPART" in query_upper:
            entities.append("FORN-002")
        if "AÇOBRASIL" in query_upper or "ACOBRASIL" in query_upper:
            entities.append("FORN-004")

        # Ordens
        for opid in ["OP-2024-0451", "OP-2024-0452", "OP-2024-0453"]:
            if opid in query_upper:
                entities.append(opid)

        # Manutenção
        if "PM-2024-156" in query_upper or ("MANUTENÇÃO" in query_upper and "CNC" in query_upper):
            entities.append("PM-2024-156")

        # Contexto amplo por tema
        if "ESTOQUE" in query_upper or "SUPRIMENTO" in query_upper or "COMPRA" in query_upper:
            entities.extend(["MP-001", "MP-002", "MP-003"])
        if "MANUTENÇÃO" in query_upper or "MANUTEN" in query_upper or "SENSOR" in query_upper:
            entities.append("CNC-03")
        if "QUALIDADE" in query_upper or "NCR" in query_upper or "DEFEITO" in query_upper:
            entities.append("PROD-001")
        if "PEDIDO" in query_upper and "5000" in query:
            entities.append("PROD-001")

        return list(set(entities))

    def _get_entity_context(self, session, entity_id: str) -> dict | None:
        """Busca um nó e todas as suas conexões até 2 hops."""
        result = session.run("""
            MATCH (n {id: $id})
            OPTIONAL MATCH (n)-[r1]-(n2)
            OPTIONAL MATCH (n2)-[r2]-(n3)
            WHERE n3 <> n
            RETURN n, labels(n)[0] AS tipo,
                   collect(DISTINCT {
                       rel: type(r1),
                       node: properties(n2),
                       node_type: labels(n2)[0]
                   }) AS conexoes_diretas,
                   collect(DISTINCT {
                       via: properties(n2).nome,
                       via_type: labels(n2)[0],
                       rel2: type(r2),
                       node: properties(n3),
                       node_type: labels(n3)[0]
                   }) AS conexoes_2hop
        """, id=entity_id)

        record = result.single()
        if not record:
            return None

        node_props = dict(record["n"])
        return {
            "entity_id": entity_id,
            "entity_type": record["tipo"],
            "properties": node_props,
            "direct_connections": [
                c for c in record["conexoes_diretas"]
                if c["node"] is not None
            ],
            "indirect_connections": [
                c for c in record["conexoes_2hop"]
                if c["node"] is not None and c["via"] is not None
            ],
        }

    def _broad_search(self, session, query: str) -> list[dict]:
        """Busca ampla quando não encontra entidades específicas."""
        results = []

        # Busca por equipamentos em atenção
        if any(w in query.upper() for w in ["RISCO", "PROBLEMA", "ALERTA", "STATUS"]):
            result = session.run("""
                MATCH (e:Equipamento)
                WHERE e.status <> 'operational'
                MATCH (e)-[r]-(connected)
                RETURN e, labels(e)[0] AS tipo,
                       collect({rel: type(r), node: properties(connected), node_type: labels(connected)[0]}) AS conexoes
            """)
            for record in result:
                results.append({
                    "entity_id": dict(record["e"])["id"],
                    "entity_type": "Equipamento",
                    "properties": dict(record["e"]),
                    "direct_connections": [c for c in record["conexoes"] if c["node"]],
                    "indirect_connections": [],
                })

        # Busca por materiais críticos
        if any(w in query.upper() for w in ["ESTOQUE", "MATERIAL", "RUPTURA", "CRITICO"]):
            result = session.run("""
                MATCH (m:Material)
                WHERE m.estoque < m.estoque_min
                MATCH (m)-[r]-(connected)
                RETURN m, collect({rel: type(r), node: properties(connected), node_type: labels(connected)[0]}) AS conexoes
            """)
            for record in result:
                results.append({
                    "entity_id": dict(record["m"])["id"],
                    "entity_type": "Material",
                    "properties": dict(record["m"]),
                    "direct_connections": [c for c in record["conexoes"] if c["node"]],
                    "indirect_connections": [],
                })

        # Busca geral — retorna visão da fábrica
        if not results:
            result = session.run("""
                MATCH (n)
                WITH labels(n)[0] AS tipo, count(*) AS total
                RETURN tipo, total ORDER BY total DESC
            """)
            summary = {record["tipo"]: record["total"] for record in result}
            results.append({
                "entity_id": "FACTORY",
                "entity_type": "Summary",
                "properties": {"resumo": "Visão geral da fábrica", "entidades": summary},
                "direct_connections": [],
                "indirect_connections": [],
            })

        return results

    def _to_documents(self, results: list[dict], k: int) -> list:
        """Converte resultados do grafo em documentos de texto para o agente."""
        from langchain_core.documents import Document

        documents = []
        for ctx in results[:k]:
            text = self._format_context(ctx)
            doc = Document(
                page_content=text,
                metadata={
                    "source": f"graphrag:{ctx['entity_id']}",
                    "entity_type": ctx["entity_type"],
                },
            )
            documents.append(doc)

        return documents

    def _format_context(self, ctx: dict) -> str:
        """Formata o contexto do grafo em texto legível para o LLM."""
        lines = []
        props = ctx["properties"]
        etype = ctx["entity_type"]
        eid = ctx["entity_id"]

        lines.append(f"## {etype}: {props.get('nome', eid)}")
        lines.append(f"ID: {eid}")

        # Propriedades relevantes
        skip_keys = {"id", "nome"}
        for key, value in props.items():
            if key not in skip_keys and value is not None:
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {value}")

        # Conexões diretas
        if ctx["direct_connections"]:
            lines.append("\n### Conexões Diretas:")
            seen = set()
            for conn in ctx["direct_connections"]:
                node = conn.get("node", {})
                key = f"{conn.get('rel')}-{node.get('id', node.get('nome', ''))}"
                if key in seen:
                    continue
                seen.add(key)
                rel = conn["rel"].replace("_", " ").lower()
                node_name = node.get("nome", node.get("id", "?"))
                node_type = conn.get("node_type", "?")
                lines.append(f"- [{rel}] → {node_type}: {node_name}")

                # Adiciona detalhes relevantes do nó conectado
                for detail_key in ["estoque", "health_score", "status", "rating", "lead_time_dias", "severidade", "causa_raiz"]:
                    if detail_key in node:
                        lines.append(f"    {detail_key}: {node[detail_key]}")

        # Conexões indiretas (2 hops)
        if ctx["indirect_connections"]:
            lines.append("\n### Conexões Indiretas (via cadeia de relações):")
            seen = set()
            for conn in ctx["indirect_connections"]:
                node = conn.get("node", {})
                via = conn.get("via", "?")
                key = f"{via}-{node.get('id', node.get('nome', ''))}"
                if key in seen:
                    continue
                seen.add(key)
                node_name = node.get("nome", node.get("id", "?"))
                node_type = conn.get("node_type", "?")
                rel2 = (conn.get("rel2") or "").replace("_", " ").lower()
                lines.append(f"- via {conn.get('via_type', '?')} '{via}' → [{rel2}] → {node_type}: {node_name}")

        return "\n".join(lines)

    # ============================================
    # Queries especializadas para os agentes
    # ============================================

    def get_supply_chain_for_product(self, product_id: str) -> str:
        """Retorna toda a cadeia de suprimentos de um produto."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Produto {id: $pid})-[:USA_MATERIAL]->(m:Material)<-[:FORNECE]-(f:Fornecedor)
                RETURN m.nome AS material, m.estoque AS estoque, m.estoque_min AS minimo,
                       f.nome AS fornecedor, f.lead_time_dias AS lead_time, f.rating AS rating,
                       f.confiabilidade AS confiabilidade
                ORDER BY m.estoque - m.estoque_min ASC
            """, pid=product_id)
            lines = [f"## Cadeia de Suprimentos — {product_id}\n"]
            for r in result:
                status = "CRÍTICO" if r["estoque"] < r["minimo"] else "OK"
                lines.append(f"Material: {r['material']} (estoque: {r['estoque']}, min: {r['minimo']}) [{status}]")
                lines.append(f"  → Fornecedor: {r['fornecedor']} | Lead time: {r['lead_time']}d | Rating: {r['rating']} | Confiab: {r['confiabilidade']}%")
            return "\n".join(lines)

    def get_impact_chain(self, equipment_id: str) -> str:
        """Se um equipamento falhar, qual o impacto em cascata?"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Equipamento {id: $eid})
                OPTIONAL MATCH (e)-[:PRODUZ]->(p:Produto)
                OPTIONAL MATCH (e)<-[:PARA_EQUIPAMENTO]-(pm:Manutencao)
                OPTIONAL MATCH (e)<-[:ORIGINADA_EM]-(ncr:NCR)
                OPTIONAL MATCH (e)-[:PERTENCE]->(l:Linha)
                OPTIONAL MATCH (op:OrdemProducao)-[:PRODUZ_PRODUTO]->(p)
                OPTIONAL MATCH (s:Sensor)-[:MONITORA]->(e)
                RETURN e, collect(DISTINCT p.nome) AS produtos,
                       collect(DISTINCT pm.id) AS manutencoes,
                       collect(DISTINCT ncr.id) AS ncrs,
                       collect(DISTINCT l.id) AS linhas,
                       collect(DISTINCT op.id) AS ordens_afetadas,
                       collect(DISTINCT {tipo: s.tipo, valor: s.valor_atual, threshold: s.threshold}) AS sensores
            """, eid=equipment_id)
            record = result.single()
            if not record:
                return f"Equipamento {equipment_id} não encontrado no grafo."

            e = dict(record["e"])
            lines = [
                f"## Análise de Impacto — {e.get('nome', equipment_id)}",
                f"Health Score: {e.get('health_score')}/100 | OEE: {e.get('oee')}% | Status: {e.get('status')}",
                f"\nProdutos afetados: {', '.join(record['produtos']) or 'nenhum'}",
                f"Ordens de produção impactadas: {', '.join(record['ordens_afetadas']) or 'nenhuma'}",
                f"Linhas afetadas: {', '.join(record['linhas']) or 'nenhuma'}",
                f"NCRs relacionadas: {', '.join(record['ncrs']) or 'nenhuma'}",
                f"Manutenções agendadas: {', '.join(record['manutencoes']) or 'nenhuma'}",
                "\nSensores:",
            ]
            for s in record["sensores"]:
                if s["tipo"]:
                    pct = round((s["valor"] / s["threshold"]) * 100, 1) if s["threshold"] else 0
                    lines.append(f"  {s['tipo']}: {s['valor']} / {s['threshold']} ({pct}% do threshold)")
            return "\n".join(lines)

    def get_quality_chain(self, product_id: str) -> str:
        """Retorna toda a cadeia de qualidade de um produto."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Produto {id: $pid})
                OPTIONAL MATCH (p)<-[:AFETA_PRODUTO]-(ncr:NCR)
                OPTIONAL MATCH (ncr)-[:ORIGINADA_EM]->(e:Equipamento)
                OPTIONAL MATCH (p)-[:REQUER_NORMA]->(n:Norma)
                RETURN p, collect(DISTINCT {ncr: ncr.id, tipo: ncr.tipo, severidade: ncr.severidade,
                       causa: ncr.causa_raiz, status: ncr.status, equipamento: e.nome}) AS ncrs,
                       collect(DISTINCT n.nome) AS normas
            """, pid=product_id)
            record = result.single()
            if not record:
                return f"Produto {product_id} não encontrado."

            p = dict(record["p"])
            lines = [
                f"## Cadeia de Qualidade — {p.get('nome', product_id)}",
                f"Tolerância: {p.get('tolerancia')} | Rugosidade: {p.get('rugosidade')} | Dureza: {p.get('dureza')}",
                f"Normas aplicáveis: {', '.join(record['normas'])}",
                f"\nNão-Conformidades ({len([n for n in record['ncrs'] if n['ncr']])} registros):",
            ]
            for ncr in record["ncrs"]:
                if ncr["ncr"]:
                    lines.append(f"  {ncr['ncr']} [{ncr['severidade']}] — {ncr['tipo']}: {ncr['causa']}")
                    if ncr["equipamento"]:
                        lines.append(f"    Originada em: {ncr['equipamento']}")
                    lines.append(f"    Status: {ncr['status']}")
            return "\n".join(lines)
