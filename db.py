"""
NEXUS 4.0 - Módulo de Banco de Dados
Conexão com PostgreSQL — fonte única de verdade para todos os agentes.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger("nexus.db")

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "nexus"),
    "user": os.getenv("POSTGRES_USER", "nexus"),
    "password": os.getenv("POSTGRES_PASSWORD", "nexus2024"),
}


@contextmanager
def get_connection():
    """Context manager para conexão com PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, params: tuple | None = None) -> list[dict]:
    """Executa uma query SELECT e retorna lista de dicts."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def query_one(sql: str, params: tuple | None = None) -> dict | None:
    """Executa uma query SELECT e retorna um único dict ou None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | None = None) -> int:
    """Executa INSERT/UPDATE/DELETE e retorna rowcount."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


# ============================================
# Queries para Supply Chain / Materiais
# ============================================


def get_all_materials(abc_class: str | None = None, critical_only: bool = False) -> list[dict]:
    """Retorna todos os materiais com status calculado."""
    sql = """
        SELECT id, name, unit, category, abc_class, xyz_class,
               stock_current, stock_min, stock_safety, stock_max,
               reorder_point, eoq, unit_cost_brl, avg_daily_consumption,
               lead_time_days, location_warehouse,
               ROUND(stock_current * unit_cost_brl, 2) AS stock_value_brl,
               CASE WHEN avg_daily_consumption > 0
                    THEN ROUND((stock_current / avg_daily_consumption)::numeric, 0)
                    ELSE NULL END AS days_of_supply,
               CASE WHEN stock_current < stock_min THEN 'CRITICO'
                    WHEN stock_current <= reorder_point THEN 'REPOR'
                    ELSE 'OK' END AS status
        FROM materials
        WHERE 1=1
    """
    params: list[Any] = []
    if abc_class:
        sql += " AND abc_class = %s"
        params.append(abc_class)
    if critical_only:
        sql += " AND stock_current <= reorder_point"
    sql += " ORDER BY abc_class, name"
    return query(sql, tuple(params) if params else None)


def get_material_by_id(material_id: str) -> dict | None:
    """Retorna um material específico."""
    return query_one("""
        SELECT *, ROUND(stock_current * unit_cost_brl, 2) AS stock_value_brl,
               CASE WHEN avg_daily_consumption > 0
                    THEN ROUND((stock_current / avg_daily_consumption)::numeric, 0)
                    ELSE NULL END AS days_of_supply,
               CASE WHEN stock_current < stock_min THEN 'CRITICO'
                    WHEN stock_current <= reorder_point THEN 'REPOR'
                    ELSE 'OK' END AS status
        FROM materials WHERE id = %s
    """, (material_id,))


def get_materials_for_product(product_id: str) -> list[dict]:
    """Retorna materiais do BOM de um produto com status de estoque."""
    return query("""
        SELECT m.id, m.name, m.unit, m.abc_class, m.xyz_class,
               m.stock_current, m.stock_min, m.stock_safety, m.reorder_point,
               m.unit_cost_brl, m.avg_daily_consumption,
               CASE WHEN m.avg_daily_consumption > 0
                    THEN ROUND((m.stock_current / m.avg_daily_consumption)::numeric, 0)
                    ELSE NULL END AS days_of_supply,
               CASE WHEN m.stock_current < m.stock_min THEN 'CRITICO'
                    WHEN m.stock_current <= m.reorder_point THEN 'REPOR'
                    ELSE 'OK' END AS status,
               b.elem->>'qty' AS bom_qty,
               b.elem->>'unit' AS bom_unit
        FROM materials m
        JOIN products p ON TRUE
        JOIN LATERAL jsonb_array_elements(p.bom) AS b(elem) ON b.elem->>'material_id' = m.id
        WHERE p.id = %s
        ORDER BY m.abc_class
    """, (product_id,))


def get_suppliers_for_material(material_id: str) -> list[dict]:
    """Retorna fornecedores de um material com dados completos."""
    return query("""
        SELECT s.id, s.name, s.rating, s.lead_time_days, s.reliability_pct,
               s.quality_pct, s.price_competitiveness, s.location,
               s.payment_terms, s.min_order_value, s.certified_iso, s.status,
               sm.unit_price_brl, sm.lead_time_days AS specific_lead_time,
               sm.min_order_qty, sm.is_preferred, sm.delivery_rating
        FROM suppliers s
        JOIN supplier_materials sm ON s.id = sm.supplier_id
        WHERE sm.material_id = %s AND s.status = 'active'
        ORDER BY sm.is_preferred DESC, s.rating DESC
    """, (material_id,))


def get_purchase_orders(status: str | None = None, material_id: str | None = None) -> list[dict]:
    """Retorna pedidos de compra."""
    sql = """
        SELECT po.id, po.quantity, po.unit_price_brl, po.total_brl,
               po.status, po.urgency, po.order_date, po.expected_delivery,
               po.received_qty, po.quality_status, po.notes,
               s.name AS supplier_name, m.name AS material_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        JOIN materials m ON po.material_id = m.id
        WHERE 1=1
    """
    params: list[Any] = []
    if status and status != "all":
        sql += " AND po.status = %s"
        params.append(status)
    if material_id:
        sql += " AND po.material_id = %s"
        params.append(material_id)
    sql += " ORDER BY po.order_date DESC"
    return query(sql, tuple(params) if params else None)


def get_inventory_movements(material_id: str, days: int = 30) -> list[dict]:
    """Retorna movimentações de estoque."""
    return query("""
        SELECT material_id, movement_type, quantity, unit_cost_brl,
               reference_doc, reason, created_at
        FROM inventory_movements
        WHERE material_id = %s AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
    """, (material_id, days))


def get_material_forecasts(material_id: str) -> list[dict]:
    """Retorna previsões de demanda."""
    return query("""
        SELECT material_id, period_start, period_end,
               forecast_qty, actual_qty, forecast_method, mape_pct
        FROM material_forecasts
        WHERE material_id = %s
        ORDER BY period_start
    """, (material_id,))


# ============================================
# Queries para Qualidade
# ============================================


def get_quality_records(product_id: str | None = None, limit: int = 20) -> list[dict]:
    """Retorna registros de qualidade (NCRs)."""
    sql = """
        SELECT qr.id, qr.type, qr.severity, qr.root_cause, qr.status, qr.created_at,
               p.name AS product_name, p.id AS product_id
        FROM quality_records qr
        JOIN products p ON qr.product_id = p.id
    """
    params: list[Any] = []
    if product_id:
        sql += " WHERE qr.product_id = %s"
        params.append(product_id)
    sql += f" ORDER BY qr.created_at DESC LIMIT {limit}"
    return query(sql, tuple(params) if params else None)


def get_quality_summary(product_id: str | None = None, days: int = 30) -> dict:
    """Retorna resumo de qualidade."""
    where = "WHERE qr.product_id = %s AND" if product_id else "WHERE"
    params: list[Any] = [product_id] if product_id else []

    totals = query_one(f"""
        SELECT COUNT(*) AS total_ncrs,
               COUNT(*) FILTER (WHERE qr.status NOT IN ('corrigida', 'fechada')) AS open_ncrs,
               COUNT(*) FILTER (WHERE qr.severity = 'critical') AS critical_ncrs
        FROM quality_records qr
        {where} qr.created_at > NOW() - INTERVAL '{days} days'
    """, tuple(params) if params else None)

    by_type = query(f"""
        SELECT qr.type, COUNT(*) AS total
        FROM quality_records qr
        {where} qr.created_at > NOW() - INTERVAL '{days} days'
        GROUP BY qr.type ORDER BY total DESC
    """, tuple(params) if params else None)

    return {"totals": totals or {}, "by_type": by_type}


def get_product_compliance(product_id: str) -> dict | None:
    """Retorna dados de um produto para análise de conformidade."""
    return query_one("SELECT * FROM products WHERE id = %s", (product_id,))


# ============================================
# Queries para Equipamentos / Manutenção
# ============================================


def get_equipment(equipment_id: str | None = None) -> list[dict] | dict | None:
    """Retorna equipamento(s). Aceita busca por ID ou nome (parcial)."""
    if equipment_id:
        # Tenta por ID exato primeiro
        result = query_one("SELECT * FROM equipment WHERE id = %s", (equipment_id,))
        if result:
            return result
        # Tenta por nome (busca parcial, case-insensitive)
        result = query_one("SELECT * FROM equipment WHERE LOWER(name) LIKE LOWER(%s)", (f"%{equipment_id}%",))
        if result:
            return result
        # Tenta por ID parcial
        return query_one("SELECT * FROM equipment WHERE LOWER(id) LIKE LOWER(%s)", (f"%{equipment_id}%",))
    return query("SELECT * FROM equipment ORDER BY health_score ASC")


def get_capacity_report(days: int = 5) -> list[dict]:
    """Retorna relatório de capacidade produtiva com cálculo real."""
    return query("""
        SELECT e.id, e.name, e.type, e.line_id, e.status,
               e.capacity_pcs_hour,
               e.shifts_per_day,
               e.hours_per_shift,
               e.oee_pct,
               e.health_score,
               e.planned_downtime_pct,
               -- Horas disponíveis no período
               (e.shifts_per_day * e.hours_per_shift * %s) AS total_hours,
               -- Horas líquidas (descontando parada planejada)
               ROUND((e.shifts_per_day * e.hours_per_shift * %s *
                      (1 - e.planned_downtime_pct / 100))::numeric, 1) AS net_hours,
               -- Capacidade nominal no período
               (e.capacity_pcs_hour * e.shifts_per_day * e.hours_per_shift * %s) AS nominal_capacity,
               -- Capacidade real (nominal × OEE)
               ROUND((e.capacity_pcs_hour * e.shifts_per_day * e.hours_per_shift * %s *
                      (e.oee_pct / 100) *
                      (1 - e.planned_downtime_pct / 100))::numeric, 0) AS real_capacity,
               -- Capacidade real por hora
               ROUND((e.capacity_pcs_hour * (e.oee_pct / 100))::numeric, 1) AS real_pcs_hour
        FROM equipment e
        ORDER BY e.line_id, e.id
    """, (days, days, days, days))


def get_latest_sensor_readings(equipment_id: str) -> list[dict]:
    """Retorna última leitura de cada sensor de um equipamento."""
    return query("""
        SELECT DISTINCT ON (sensor_type)
               sensor_type, value, unit, threshold, status, read_at
        FROM sensor_readings
        WHERE equipment_id = %s
        ORDER BY sensor_type, read_at DESC
    """, (equipment_id,))


def get_sensor_history(equipment_id: str, sensor_type: str, hours: int = 48) -> list[dict]:
    """Retorna histórico de um sensor."""
    return query("""
        SELECT value, unit, threshold, status, read_at
        FROM sensor_readings
        WHERE equipment_id = %s AND sensor_type = %s
              AND read_at > NOW() - INTERVAL '%s hours'
        ORDER BY read_at
    """, (equipment_id, sensor_type, hours))


# ============================================
# Queries para Produção (PCP)
# ============================================


def get_production_orders(status: str | None = None) -> list[dict]:
    """Retorna ordens de produção."""
    sql = """
        SELECT po.id, po.quantity, po.line_id, po.start_date, po.end_date,
               po.status, po.progress_pct, po.priority,
               p.name AS product_name, p.id AS product_id,
               p.cycle_time_min, p.unit_cost_brl
        FROM production_orders po
        JOIN products p ON po.product_id = p.id
    """
    params: list[Any] = []
    if status:
        sql += " WHERE po.status = %s"
        params.append(status)
    sql += " ORDER BY po.priority DESC, po.start_date"
    return query(sql, tuple(params) if params else None)


def get_products() -> list[dict]:
    """Retorna todos os produtos."""
    return query("SELECT * FROM products ORDER BY id")


# ============================================
# Queries para KPIs / Analytics
# ============================================


def get_kpis_summary() -> dict:
    """Retorna KPIs consolidados."""
    equipment_kpis = query_one("""
        SELECT ROUND(AVG(oee_pct)::numeric, 1) AS avg_oee,
               ROUND(AVG(health_score)::numeric, 0) AS avg_health,
               COUNT(*) FILTER (WHERE status != 'operational') AS equipment_warning
        FROM equipment
    """)

    stock_kpis = query_one("""
        SELECT ROUND(SUM(stock_current * unit_cost_brl)::numeric, 2) AS total_stock_value,
               COUNT(*) FILTER (WHERE stock_current < stock_min) AS critical_materials,
               COUNT(*) AS total_materials
        FROM materials
    """)

    quality_kpis = query_one("""
        SELECT COUNT(*) AS total_ncrs_30d,
               COUNT(*) FILTER (WHERE status NOT IN ('corrigida', 'fechada')) AS open_ncrs
        FROM quality_records
        WHERE created_at > NOW() - INTERVAL '30 days'
    """)

    production_kpis = query_one("""
        SELECT COUNT(*) AS active_orders,
               SUM(quantity) AS total_units
        FROM production_orders
        WHERE status IN ('em_andamento', 'planned')
    """)

    return {
        "equipment": equipment_kpis or {},
        "stock": stock_kpis or {},
        "quality": quality_kpis or {},
        "production": production_kpis or {},
    }
