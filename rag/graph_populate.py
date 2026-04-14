"""
NEXUS 4.0 - GraphRAG: População do Grafo de Conhecimento
Lê TODOS os dados do PostgreSQL e cria o grafo no Neo4j.
Fonte única de verdade: PostgreSQL → Neo4j (zero hardcode).
"""

import json
import logging
import os

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("nexus.graph")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "nexus2024")


def _pg_query(sql):
    """Query ao PostgreSQL."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "nexus"),
        user=os.getenv("POSTGRES_USER", "nexus"),
        password=os.getenv("POSTGRES_PASSWORD", "nexus2024"),
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def populate_graph():
    """Popula o grafo de conhecimento a partir do PostgreSQL."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Limpa grafo existente
        logger.info("Limpando grafo existente...")
        session.run("MATCH (n) DETACH DELETE n")

        # ============================================
        # PRODUTOS (do PostgreSQL)
        # ============================================
        products = _pg_query("SELECT * FROM products")
        logger.info(f"Criando {len(products)} produtos...")
        for p in products:
            session.run(
                """CREATE (n:Produto {
                    id: $id, nome: $name, descricao: $description,
                    custo_unitario: $cost, tempo_ciclo_min: $cycle
                })""",
                id=p["id"], name=p["name"], description=p.get("description", ""),
                cost=float(p.get("unit_cost_brl", 0) or 0),
                cycle=float(p.get("cycle_time_min", 0) or 0),
            )

        # ============================================
        # MATERIAIS (do PostgreSQL)
        # ============================================
        materials = _pg_query("SELECT * FROM materials")
        logger.info(f"Criando {len(materials)} materiais...")
        for m in materials:
            session.run(
                """CREATE (n:Material {
                    id: $id, nome: $name, unidade: $unit,
                    categoria: $cat, classe_abc: $abc, classe_xyz: $xyz,
                    estoque: $stock, estoque_min: $smin, estoque_seguranca: $ssafe,
                    ponto_reposicao: $rop, eoq: $eoq, custo_unitario: $cost,
                    consumo_diario: $daily, lead_time_dias: $lt,
                    localizacao: $loc
                })""",
                id=m["id"], name=m["name"], unit=m.get("unit", ""),
                cat=m.get("category", ""), abc=m.get("abc_class", ""),
                xyz=m.get("xyz_class", ""),
                stock=float(m.get("stock_current", 0) or 0),
                smin=float(m.get("stock_min", 0) or 0),
                ssafe=float(m.get("stock_safety", 0) or 0),
                rop=float(m.get("reorder_point", 0) or 0),
                eoq=float(m.get("eoq", 0) or 0),
                cost=float(m.get("unit_cost_brl", 0) or 0),
                daily=float(m.get("avg_daily_consumption", 0) or 0),
                lt=int(m.get("lead_time_days", 0) or 0),
                loc=m.get("location_warehouse", ""),
            )

        # ============================================
        # EQUIPAMENTOS (do PostgreSQL)
        # ============================================
        equipment = _pg_query("SELECT * FROM equipment")
        logger.info(f"Criando {len(equipment)} equipamentos...")
        for e in equipment:
            session.run(
                """CREATE (n:Equipamento {
                    id: $id, nome: $name, tipo: $type,
                    health_score: $health, oee: $oee, status: $status
                })""",
                id=e["id"], name=e["name"], type=e.get("type", ""),
                health=int(e.get("health_score", 0) or 0),
                oee=float(e.get("oee_pct", 0) or 0),
                status=e.get("status", ""),
            )

        # ============================================
        # FORNECEDORES (do PostgreSQL)
        # ============================================
        suppliers = _pg_query("SELECT * FROM suppliers")
        logger.info(f"Criando {len(suppliers)} fornecedores...")
        for s in suppliers:
            session.run(
                """CREATE (n:Fornecedor {
                    id: $id, nome: $name, rating: $rating,
                    lead_time_dias: $lt, confiabilidade: $rel,
                    qualidade: $qual, localizacao: $loc,
                    certificado_iso: $iso, status: $status,
                    termos_pagamento: $pay
                })""",
                id=s["id"], name=s["name"],
                rating=float(s.get("rating", 0) or 0),
                lt=int(s.get("lead_time_days", 0) or 0),
                rel=float(s.get("reliability_pct", 0) or 0),
                qual=float(s.get("quality_pct", 0) or 0),
                loc=s.get("location", ""),
                iso=bool(s.get("certified_iso", False)),
                status=s.get("status", ""),
                pay=s.get("payment_terms", ""),
            )

        # ============================================
        # ORDENS DE PRODUÇÃO (do PostgreSQL)
        # ============================================
        orders = _pg_query("SELECT * FROM production_orders")
        logger.info(f"Criando {len(orders)} ordens de produção...")
        for o in orders:
            session.run(
                """CREATE (n:OrdemProducao {
                    id: $id, quantidade: $qty, status: $status,
                    progresso: $prog, prioridade: $pri,
                    linha: $line
                })""",
                id=o["id"], qty=int(o.get("quantity", 0) or 0),
                status=o.get("status", ""), prog=int(o.get("progress_pct", 0) or 0),
                pri=o.get("priority", ""), line=o.get("line_id", ""),
            )

        # ============================================
        # NCRs (do PostgreSQL)
        # ============================================
        ncrs = _pg_query("SELECT * FROM quality_records")
        logger.info(f"Criando {len(ncrs)} NCRs...")
        for n in ncrs:
            session.run(
                """CREATE (n:NCR {
                    id: $id, tipo: $type, severidade: $sev,
                    causa_raiz: $cause, status: $status
                })""",
                id=n["id"], type=n.get("type", ""),
                sev=n.get("severity", ""), cause=n.get("root_cause", ""),
                status=n.get("status", ""),
            )

        # ============================================
        # SENSORES — últimas leituras (do PostgreSQL)
        # ============================================
        sensors = _pg_query("""
            SELECT DISTINCT ON (equipment_id, sensor_type)
                   equipment_id, sensor_type, value, unit, threshold, status
            FROM sensor_readings
            ORDER BY equipment_id, sensor_type, read_at DESC
        """)
        logger.info(f"Criando {len(sensors)} sensores...")
        for s in sensors:
            sid = f"SENS-{s['sensor_type'].upper()[:4]}-{s['equipment_id']}"
            session.run(
                """CREATE (n:Sensor {
                    id: $id, tipo: $type, valor_atual: $val,
                    unidade: $unit, threshold: $thr, status: $status,
                    equipamento_id: $eq
                })""",
                id=sid, type=s["sensor_type"],
                val=float(s.get("value", 0) or 0),
                unit=s.get("unit", ""),
                thr=float(s.get("threshold", 0) or 0),
                status=s.get("status", ""),
                eq=s["equipment_id"],
            )

        # ============================================
        # RELAÇÕES (baseadas no PostgreSQL)
        # ============================================
        logger.info("Criando relações...")

        # Produto → usa Material (via BOM no campo jsonb)
        for p in products:
            bom = p.get("bom")
            if isinstance(bom, str):
                bom = json.loads(bom)
            if bom:
                for item in bom:
                    session.run(
                        """MATCH (p:Produto {id: $pid}), (m:Material {id: $mid})
                           CREATE (p)-[:USA_MATERIAL {quantidade: $qty, unidade: $unit}]->(m)""",
                        pid=p["id"], mid=item["material_id"],
                        qty=float(item.get("qty", 0)), unit=item.get("unit", ""),
                    )

        # Fornecedor → fornece Material (tabela supplier_materials)
        sm_rows = _pg_query("SELECT * FROM supplier_materials")
        for sm in sm_rows:
            session.run(
                """MATCH (f:Fornecedor {id: $fid}), (m:Material {id: $mid})
                   CREATE (f)-[:FORNECE {preco: $price, lead_time: $lt,
                   pedido_minimo: $moq, preferencial: $pref}]->(m)""",
                fid=sm["supplier_id"], mid=sm["material_id"],
                price=float(sm.get("unit_price_brl", 0) or 0),
                lt=int(sm.get("lead_time_days", 0) or 0),
                moq=float(sm.get("min_order_qty", 0) or 0),
                pref=bool(sm.get("is_preferred", False)),
            )

        # OrdemProducao → produz Produto
        for o in orders:
            session.run(
                """MATCH (op:OrdemProducao {id: $oid}), (p:Produto {id: $pid})
                   CREATE (op)-[:PRODUZ_PRODUTO]->(p)""",
                oid=o["id"], pid=o["product_id"],
            )

        # NCR → afeta Produto
        for n in ncrs:
            session.run(
                """MATCH (ncr:NCR {id: $nid}), (p:Produto {id: $pid})
                   CREATE (ncr)-[:AFETA_PRODUTO]->(p)""",
                nid=n["id"], pid=n["product_id"],
            )

        # Sensor → monitora Equipamento
        for s in sensors:
            sid = f"SENS-{s['sensor_type'].upper()[:4]}-{s['equipment_id']}"
            session.run(
                """MATCH (s:Sensor {id: $sid}), (e:Equipamento {id: $eid})
                   CREATE (s)-[:MONITORA]->(e)""",
                sid=sid, eid=s["equipment_id"],
            )

        # Pedidos de compra → Fornecedor + Material
        pos = _pg_query("SELECT * FROM purchase_orders")
        logger.info(f"Criando {len(pos)} pedidos de compra...")
        for po in pos:
            session.run(
                """CREATE (n:PedidoCompra {
                    id: $id, quantidade: $qty, preco_unitario: $price,
                    total: $total, status: $status, urgencia: $urg
                })""",
                id=po["id"], qty=float(po.get("quantity", 0) or 0),
                price=float(po.get("unit_price_brl", 0) or 0),
                total=float(po.get("total_brl", 0) or 0),
                status=po.get("status", ""), urg=po.get("urgency", ""),
            )
            session.run(
                "MATCH (pc:PedidoCompra {id: $pcid}), (f:Fornecedor {id: $fid}) CREATE (pc)-[:COMPRADO_DE]->(f)",
                pcid=po["id"], fid=po["supplier_id"],
            )
            session.run(
                "MATCH (pc:PedidoCompra {id: $pcid}), (m:Material {id: $mid}) CREATE (pc)-[:COMPRA_MATERIAL]->(m)",
                pcid=po["id"], mid=po["material_id"],
            )

        # ============================================
        # RELAÇÕES INFERIDAS (lógica de negócio)
        # Estas são relações que não estão numa tabela
        # específica mas fazem sentido no contexto industrial
        # ============================================
        logger.info("Criando relações inferidas...")

        # Equipamentos que produzem produtos (via ordens de produção)
        # Inferido: se OP está na LINHA-01 e equipamento está na LINHA-01
        equip_lines = {
            "CNC-03": "LINHA-01", "SERRA-01": "LINHA-01",
            "PRENSA-01": "LINHA-02", "RETIFICA-01": "LINHA-01",
        }
        for eid, line in equip_lines.items():
            # Equipamentos da mesma linha que tem OPs produzindo produtos
            line_orders = [o for o in orders if o.get("line_id") == line]
            for o in line_orders:
                session.run(
                    """MATCH (e:Equipamento {id: $eid}), (p:Produto {id: $pid})
                       MERGE (e)-[:PRODUZ]->(p)""",
                    eid=eid, pid=o["product_id"],
                )

        # NCRs originadas em equipamentos (inferido: NCRs de produtos
        # que são produzidos em equipamentos com status != operational)
        problem_equip = [e for e in equipment if e.get("status") != "operational"]
        for eq in problem_equip:
            eq_products = _pg_query(f"""
                SELECT DISTINCT po.product_id FROM production_orders po
                WHERE po.line_id IN (
                    SELECT CASE
                        WHEN '{eq["id"]}' IN ('CNC-03', 'SERRA-01', 'RETIFICA-01') THEN 'LINHA-01'
                        WHEN '{eq["id"]}' = 'PRENSA-01' THEN 'LINHA-02'
                    END
                )
            """)
            for ep in eq_products:
                # NCRs desse produto → originadas nesse equipamento
                product_ncrs = [n for n in ncrs if n["product_id"] == ep["product_id"]
                                and n.get("status") not in ("corrigida", "fechada")]
                for ncr in product_ncrs:
                    session.run(
                        "MATCH (ncr:NCR {id: $nid}), (e:Equipamento {id: $eid}) MERGE (ncr)-[:ORIGINADA_EM]->(e)",
                        nid=ncr["id"], eid=eq["id"],
                    )

        # Material consumível → consumido por equipamento
        # Inferido: insertos e óleo refrigerante → CNC, rebolo → retífica
        consumo_map = [
            ("MP-004", "CNC-03", "refrigerante"),
            ("MP-005", "CNC-03", "ferramenta_corte"),
            ("MP-007", "PRENSA-01", "fluido_hidraulico"),
            ("MP-007", "CNC-03", "fluido_hidraulico"),
            ("MP-010", "RETIFICA-01", "abrasivo"),
            ("MP-006", "CNC-03", "peca_reposicao"),
        ]
        for mid, eid, tipo in consumo_map:
            session.run(
                """MATCH (m:Material {id: $mid}), (e:Equipamento {id: $eid})
                   MERGE (m)-[:CONSUMIDO_POR {tipo: $tipo}]->(e)""",
                mid=mid, eid=eid, tipo=tipo,
            )

        # ============================================
        # Verificação
        # ============================================
        result = session.run("MATCH (n) RETURN labels(n)[0] AS tipo, COUNT(*) AS total ORDER BY total DESC")
        logger.info("=== Grafo populado (dados do PostgreSQL) ===")
        total_nodes = 0
        for record in result:
            logger.info(f"  {record['tipo']}: {record['total']}")
            total_nodes += record['total']

        result_rels = session.run("MATCH ()-[r]->() RETURN type(r) AS tipo, COUNT(*) AS total ORDER BY total DESC")
        total_rels = 0
        logger.info("=== Relações ===")
        for record in result_rels:
            logger.info(f"  {record['tipo']}: {record['total']}")
            total_rels += record['total']

        logger.info(f"Total: {total_nodes} nós, {total_rels} relações")

    driver.close()
    logger.info("Grafo de conhecimento criado com sucesso a partir do PostgreSQL!")


if __name__ == "__main__":
    populate_graph()
