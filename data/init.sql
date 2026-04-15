-- NEXUS 4.0 - Schema do Banco de Dados
-- Armazena decisões, histórico de agentes e dados operacionais

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Conversas e Mensagens
-- ============================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_phone VARCHAR(20),
    started_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active',
    summary TEXT
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    sender VARCHAR(50) NOT NULL,  -- 'user', 'coordinator', 'planner', etc.
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'text',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- Decisões dos Agentes
-- ============================================

CREATE TABLE agent_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    agent_role VARCHAR(30) NOT NULL,
    decision TEXT NOT NULL,
    confidence FLOAT,
    reasoning TEXT,
    actions JSONB DEFAULT '[]',
    risks JSONB DEFAULT '[]',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- Dados Operacionais (Simulados)
-- ============================================

CREATE TABLE products (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    unit_cost_brl DECIMAL(10,2),
    cycle_time_min DECIMAL(5,1),
    bom JSONB DEFAULT '[]'
);

CREATE TABLE materials (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    category VARCHAR(30),          -- materia_prima, componente, embalagem, consumivel, quimico
    abc_class CHAR(1) DEFAULT 'C', -- Classificação ABC (valor)
    xyz_class CHAR(1) DEFAULT 'X', -- Classificação XYZ (previsibilidade demanda)
    stock_current DECIMAL(10,2) DEFAULT 0,
    stock_min DECIMAL(10,2) DEFAULT 0,
    stock_safety DECIMAL(10,2) DEFAULT 0,
    stock_max DECIMAL(10,2) DEFAULT 0,
    reorder_point DECIMAL(10,2) DEFAULT 0, -- Ponto de reposição
    eoq DECIMAL(10,2) DEFAULT 0,           -- Lote Econômico de Compra
    unit_cost_brl DECIMAL(10,2),
    last_unit_cost_brl DECIMAL(10,2),       -- Último preço pago
    avg_daily_consumption DECIMAL(10,2) DEFAULT 0,
    lead_time_days INTEGER DEFAULT 7,
    shelf_life_days INTEGER,                -- Validade (para químicos)
    location_warehouse VARCHAR(50),         -- Endereço no almoxarifado
    ncm_code VARCHAR(12),                   -- NCM para importação
    last_purchase_date DATE,
    last_count_date DATE                    -- Último inventário
);

CREATE TABLE suppliers (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    cnpj VARCHAR(18),
    rating DECIMAL(2,1),
    lead_time_days INTEGER,
    reliability_pct DECIMAL(4,1),
    quality_pct DECIMAL(4,1) DEFAULT 100,   -- % lotes aprovados
    price_competitiveness DECIMAL(3,1),      -- Nota 0-10
    location VARCHAR(100),
    payment_terms VARCHAR(50),               -- Ex: "30/60/90 DDL"
    min_order_value DECIMAL(10,2),
    certified_iso BOOLEAN DEFAULT false,
    last_audit_date DATE,
    status VARCHAR(20) DEFAULT 'active'      -- active, blocked, probation
);

CREATE TABLE supplier_materials (
    id SERIAL PRIMARY KEY,
    supplier_id VARCHAR(20) REFERENCES suppliers(id),
    material_id VARCHAR(20) REFERENCES materials(id),
    unit_price_brl DECIMAL(10,2),
    lead_time_days INTEGER,
    min_order_qty DECIMAL(10,2),
    is_preferred BOOLEAN DEFAULT false,
    last_delivery_date DATE,
    delivery_rating DECIMAL(2,1),             -- Nota última entrega
    UNIQUE(supplier_id, material_id)
);

CREATE TABLE purchase_orders (
    id VARCHAR(20) PRIMARY KEY,
    supplier_id VARCHAR(20) REFERENCES suppliers(id),
    material_id VARCHAR(20) REFERENCES materials(id),
    quantity DECIMAL(10,2) NOT NULL,
    unit_price_brl DECIMAL(10,2),
    total_brl DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'pending',     -- pending, approved, sent, in_transit, received, rejected
    urgency VARCHAR(10) DEFAULT 'normal',     -- normal, urgent, emergency
    order_date DATE DEFAULT CURRENT_DATE,
    expected_delivery DATE,
    actual_delivery DATE,
    received_qty DECIMAL(10,2),
    quality_status VARCHAR(20),               -- approved, rejected, partial
    notes TEXT
);

CREATE TABLE inventory_movements (
    id BIGSERIAL PRIMARY KEY,
    material_id VARCHAR(20) REFERENCES materials(id),
    movement_type VARCHAR(20) NOT NULL,       -- entrada, saida, ajuste, devolucao, transferencia
    quantity DECIMAL(10,2) NOT NULL,
    unit_cost_brl DECIMAL(10,2),
    reference_doc VARCHAR(30),                -- OP, PO, ajuste manual
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE material_forecasts (
    id SERIAL PRIMARY KEY,
    material_id VARCHAR(20) REFERENCES materials(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    forecast_qty DECIMAL(10,2),
    actual_qty DECIMAL(10,2),
    forecast_method VARCHAR(30),              -- media_movel, exp_smoothing, manual
    mape_pct DECIMAL(5,2),                    -- Mean Absolute Percentage Error
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE equipment (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50),
    line_id VARCHAR(20),
    health_score INTEGER DEFAULT 100,
    oee_pct DECIMAL(4,1),
    status VARCHAR(20) DEFAULT 'operational',
    capacity_pcs_hour INTEGER,             -- Capacidade nominal (peças/hora)
    shifts_per_day INTEGER DEFAULT 1,       -- Turnos por dia (1, 2 ou 3)
    hours_per_shift DECIMAL(3,1) DEFAULT 8, -- Horas por turno
    planned_downtime_pct DECIMAL(4,1) DEFAULT 5, -- Parada planejada %
    last_maintenance TIMESTAMP
);

CREATE TABLE maintenance_history (
    id VARCHAR(20) PRIMARY KEY,
    equipment_id VARCHAR(20) REFERENCES equipment(id),
    maintenance_type VARCHAR(30) NOT NULL,  -- preventiva, corretiva, preditiva, calibração
    scheduled_date TIMESTAMP,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    duration_hours DECIMAL(5,2),
    description TEXT NOT NULL,              -- O que foi feito
    actions_performed TEXT[],               -- Ações específicas realizadas
    parts_replaced TEXT[],                  -- Peças trocadas
    labor_hours DECIMAL(5,2),
    cost_brl DECIMAL(10,2),
    technician VARCHAR(100),
    status VARCHAR(20) DEFAULT 'concluida', -- agendada, em_andamento, concluida, cancelada
    notes TEXT
);

CREATE TABLE production_orders (
    id VARCHAR(20) PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(id),
    quantity INTEGER NOT NULL,
    line_id VARCHAR(20),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'planned',
    progress_pct INTEGER DEFAULT 0,
    priority VARCHAR(10) DEFAULT 'normal'
);

CREATE TABLE sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    equipment_id VARCHAR(20) REFERENCES equipment(id),
    sensor_type VARCHAR(30) NOT NULL,
    value DECIMAL(10,3) NOT NULL,
    unit VARCHAR(10),
    threshold DECIMAL(10,3),
    status VARCHAR(10) DEFAULT 'normal',
    read_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quality_records (
    id VARCHAR(20) PRIMARY KEY,
    product_id VARCHAR(20) REFERENCES products(id),
    type VARCHAR(30),
    severity VARCHAR(10),
    root_cause TEXT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE automation_logs (
    id BIGSERIAL PRIMARY KEY,
    workflow_name VARCHAR(100) NOT NULL,
    trigger_type VARCHAR(20) NOT NULL DEFAULT 'cron',  -- cron, webhook, manual
    status VARCHAR(20) NOT NULL DEFAULT 'success',     -- success, warning, critical, error
    summary TEXT,
    details JSONB DEFAULT '{}',
    agents_involved TEXT[],
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- Dados Iniciais
-- ============================================

INSERT INTO products VALUES
('PROD-001', 'Eixo de Transmissão ET-500',
 'Eixo de transmissão em aço SAE 1045 temperado e retificado para aplicações automotivas. Tolerância ±0.02mm, rugosidade Ra 0.8, dureza 58-62 HRC. Processo: Corte → Usinagem CNC → Têmpera/Revenimento → Retífica → Montagem sensor → Inspeção → Embalagem.',
 185.00, 42.0,
 '[{"material_id": "MP-001", "qty": 2.5, "unit": "kg"}, {"material_id": "MP-002", "qty": 1, "unit": "pç"}, {"material_id": "MP-009", "qty": 4, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-002', 'Engrenagem Helicoidal EH-200',
 'Engrenagem helicoidal módulo 2, 40 dentes, em aço SAE 4340 com tratamento térmico de cementação. Aplicação em redutores industriais. Processo: Corte → Usinagem CNC (desbaste + acabamento) → Cementação → Retífica de dentes.',
 320.00, 55.0,
 '[{"material_id": "MP-001", "qty": 5.0, "unit": "kg"}, {"material_id": "MP-009", "qty": 6, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-003', 'Bucha de Mancal BM-100',
 'Bucha autolubrificante para mancal de deslizamento, em bronze SAE 65. Aplicação em equipamentos rotativos de baixa velocidade. Processo: Corte → Usinagem CNC → Aplicação graxa → Embalagem.',
 95.00, 25.0,
 '[{"material_id": "MP-001", "qty": 1.2, "unit": "kg"}, {"material_id": "MP-011", "qty": 0.1, "unit": "kg"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-004', 'Flange de Acoplamento FA-300',
 'Flange de acoplamento em aço SAE 1045 para conexão de eixos em sistemas de transmissão automotiva. 6 furos M10 em padrão circular. Tolerância ±0.05mm. Processo: Corte → Usinagem CNC → Furação → Inspeção → Embalagem.',
 145.00, 35.0,
 '[{"material_id": "MP-001", "qty": 3.0, "unit": "kg"}, {"material_id": "MP-009", "qty": 6, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-005', 'Pino Guia PG-150',
 'Pino guia de precisão em aço SAE 4140 temperado e retificado. Tolerância h6, rugosidade Ra 0.4. Aplicação em matrizes e dispositivos de fixação. Processo: Corte → Usinagem CNC → Têmpera → Retífica centerless.',
 65.00, 18.0,
 '[{"material_id": "MP-001", "qty": 0.8, "unit": "kg"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-006', 'Came de Comando CC-250',
 'Came de comando em aço SAE 8620 cementado para sistemas de distribuição automotiva. Perfil de came usinado em 5 eixos. Dureza superficial 58-62 HRC, núcleo 30-35 HRC. Processo: Corte → Usinagem CNC 5 eixos → Cementação → Retífica de perfil.',
 410.00, 68.0,
 '[{"material_id": "MP-001", "qty": 4.5, "unit": "kg"}, {"material_id": "MP-009", "qty": 2, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-007', 'Luva Estriada LE-180',
 'Luva estriada em aço SAE 4340 para acoplamento de eixos com transmissão de torque. 16 estrias involuta, módulo 1.5. Processo: Corte → Usinagem CNC → Brocheamento de estrias → Têmpera por indução.',
 275.00, 48.0,
 '[{"material_id": "MP-001", "qty": 3.5, "unit": "kg"}, {"material_id": "MP-009", "qty": 4, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]'),

('PROD-008', 'Polia Sincronizadora PS-120',
 'Polia sincronizadora em alumínio 6061-T6 anodizado para sistemas de transmissão por correia dentada. 28 dentes, perfil HTD-5M. Processo: Corte → Usinagem CNC → Anodização → Inspeção → Embalagem.',
 120.00, 30.0,
 '[{"material_id": "MP-001", "qty": 1.0, "unit": "kg"}, {"material_id": "MP-008", "qty": 1, "unit": "pç"}, {"material_id": "MP-009", "qty": 2, "unit": "pç"}, {"material_id": "MP-003", "qty": 1, "unit": "pç"}]');

-- Materiais expandidos com classificação ABC/XYZ e gestão completa
INSERT INTO materials (id, name, unit, category, abc_class, xyz_class, stock_current, stock_min, stock_safety, stock_max, reorder_point, eoq, unit_cost_brl, last_unit_cost_brl, avg_daily_consumption, lead_time_days, location_warehouse, ncm_code, last_purchase_date, last_count_date) VALUES
('MP-001', 'Barra de Aço SAE 1045',       'kg',  'materia_prima', 'A', 'X', 850,  200, 300, 2000, 500,  800,  12.50, 12.80, 60,  3,  'ALM-A01-P1', '7228.30.00', '2024-07-10', '2024-07-01'),
('MP-002', 'Sensor de Posição Angular',   'pç',  'componente',    'A', 'Y', 120,  500, 200, 3000, 700,  1000, 45.00, 48.00, 40,  7,  'ALM-B02-P3', '9031.80.99', '2024-06-28', '2024-07-01'),
('MP-003', 'Embalagem Protetiva VCI',     'pç',  'embalagem',     'C', 'X', 5000, 1000, 500, 8000, 2000, 3000, 3.50,  3.50,  35,  5,  'ALM-C01-P1', '3923.29.90', '2024-07-05', '2024-07-01'),
('MP-004', 'Óleo Refrigerante Sintético', 'lt',  'consumivel',    'B', 'X', 180,  50,  80,  400,  130,  200,  28.00, 27.50, 8,   3,  'ALM-D01-P2', '2710.19.99', '2024-07-08', '2024-07-01'),
('MP-005', 'Inserto de Metal Duro CNMG',  'pç',  'consumivel',    'A', 'Z', 45,   20,  30,  200,  60,   80,   85.00, 82.00, 3,   10, 'ALM-B01-P1', '8209.00.19', '2024-06-20', '2024-07-01'),
('MP-006', 'Rolamento SKF 7210',          'pç',  'componente',    'B', 'Z', 8,    4,   6,   20,   10,   10,   420.00, 415.00, 0.1, 14, 'ALM-B03-P2', '8482.10.10', '2024-05-15', '2024-07-01'),
('MP-007', 'Fluido Hidráulico ISO 46',    'lt',  'consumivel',    'B', 'X', 320,  100, 150, 600,  250,  200,  18.50, 19.00, 5,   3,  'ALM-D02-P1', '2710.19.91', '2024-07-01', '2024-07-01'),
('MP-008', 'Correia Dentada HTD-5M',      'pç',  'componente',    'C', 'Z', 12,   5,   8,   30,   13,   10,   95.00, 92.00, 0.05, 15, 'ALM-B02-P1', '4010.39.00', '2024-04-10', '2024-07-01'),
('MP-009', 'Parafuso M8x30 Classe 10.9',  'pç',  'componente',    'C', 'X', 2500, 500, 800, 5000, 1300, 2000, 0.85,  0.85,  25,  2,  'ALM-A03-P1', '7318.15.00', '2024-07-12', '2024-07-01'),
('MP-010', 'Rebolo Abrasivo Grão 120',    'pç',  'consumivel',    'C', 'X', 800,  200, 300, 2000, 500,  600,  2.20,  2.20,  15,  3,  'ALM-D03-P1', '6805.30.90', '2024-07-10', '2024-07-01'),
('MP-011', 'Graxa Especial EP-2',         'kg',  'consumivel',    'C', 'X', 25,   10,  15,  50,   25,   20,   45.00, 44.00, 0.3, 5,  'ALM-D01-P3', '2710.19.99', '2024-06-25', '2024-07-01'),
('MP-012', 'Filtro de Óleo Hidráulico',   'pç',  'componente',    'C', 'Z', 15,   5,   8,   30,   13,   10,   65.00, 62.00, 0.1, 7,  'ALM-B03-P1', '8421.23.00', '2024-06-15', '2024-07-01');

-- Fornecedores expandidos com dados de gestão
INSERT INTO suppliers (id, name, cnpj, rating, lead_time_days, reliability_pct, quality_pct, price_competitiveness, location, payment_terms, min_order_value, certified_iso, last_audit_date, status) VALUES
('FORN-001', 'TechComponents Ltda',      '12.345.678/0001-01', 4.2, 7,  92.0, 97.5, 7.5, 'São Paulo, SP',      '30/60 DDL',     500,   true,  '2024-03-15', 'active'),
('FORN-002', 'GlobalParts Import',        '98.765.432/0001-02', 3.8, 21, 85.0, 94.0, 9.0, 'Shenzhen, China',    '90 DDL + carta', 5000,  true,  '2024-01-20', 'active'),
('FORN-003', 'ElectroSul Componentes',    '11.222.333/0001-03', 4.5, 5,  96.0, 99.0, 6.5, 'Caxias do Sul, RS',  '28 DDL',         200,   true,  '2024-06-10', 'active'),
('FORN-004', 'AçoBrasil Siderúrgica',     '44.555.666/0001-04', 4.7, 3,  98.0, 99.5, 7.0, 'Volta Redonda, RJ',  '30/60/90 DDL',   1000,  true,  '2024-05-22', 'active'),
('FORN-005', 'LubriTech Industrial',      '55.666.777/0001-05', 4.3, 3,  95.0, 98.0, 8.0, 'Canoas, RS',         '30 DDL',         300,   false, '2024-04-10', 'active'),
('FORN-006', 'Abrasivos Nacional SA',     '66.777.888/0001-06', 4.0, 5,  90.0, 96.0, 8.5, 'São Paulo, SP',      '30/60 DDL',      200,   false, '2023-11-15', 'active'),
('FORN-007', 'SKF do Brasil Ltda',        '77.888.999/0001-07', 4.8, 14, 99.0, 99.8, 5.0, 'Cajamar, SP',        '30 DDL',         1000,  true,  '2024-02-28', 'active'),
('FORN-008', 'FixBrasil Parafusos',       '88.999.000/0001-08', 4.1, 2,  93.0, 97.0, 9.0, 'Joinville, SC',      '28 DDL',         100,   false, '2024-05-05', 'active');

-- Relação fornecedor-material (quem fornece o quê)
INSERT INTO supplier_materials (supplier_id, material_id, unit_price_brl, lead_time_days, min_order_qty, is_preferred, last_delivery_date, delivery_rating) VALUES
('FORN-004', 'MP-001', 12.50,  3,  500,  true,  '2024-07-10', 4.8),
('FORN-001', 'MP-002', 45.00,  7,  100,  true,  '2024-06-28', 4.0),
('FORN-002', 'MP-002', 38.50,  21, 500,  false, '2024-05-10', 3.5),
('FORN-003', 'MP-002', 52.00,  5,  50,   false, '2024-06-15', 4.7),
('FORN-003', 'MP-003', 3.50,   5,  1000, true,  '2024-07-05', 4.5),
('FORN-005', 'MP-004', 28.00,  3,  50,   true,  '2024-07-08', 4.3),
('FORN-001', 'MP-005', 85.00,  10, 20,   true,  '2024-06-20', 4.2),
('FORN-007', 'MP-006', 420.00, 14, 2,    true,  '2024-05-15', 4.9),
('FORN-005', 'MP-007', 18.50,  3,  50,   true,  '2024-07-01', 4.4),
('FORN-006', 'MP-008', 95.00,  15, 5,    true,  '2024-04-10', 3.8),
('FORN-008', 'MP-009', 0.85,   2,  500,  true,  '2024-07-12', 4.1),
('FORN-006', 'MP-010', 2.20,   3,  200,  true,  '2024-07-10', 4.0),
('FORN-005', 'MP-011', 45.00,  5,  5,    true,  '2024-06-25', 4.3),
('FORN-007', 'MP-012', 65.00,  7,  5,    true,  '2024-06-15', 4.8);

-- Pedidos de compra ativos
INSERT INTO purchase_orders (id, supplier_id, material_id, quantity, unit_price_brl, total_brl, status, urgency, order_date, expected_delivery, received_qty, quality_status, notes) VALUES
('PC-2024-0201', 'FORN-004', 'MP-001', 1000, 12.50,  12500.00, 'received',   'normal',    '2024-07-05', '2024-07-08', 1000, 'approved',  'Entrega OK'),
('PC-2024-0202', 'FORN-001', 'MP-002', 500,  45.00,  22500.00, 'in_transit', 'urgent',    '2024-07-10', '2024-07-17', NULL, NULL,        'Compra urgente - estoque crítico'),
('PC-2024-0203', 'FORN-003', 'MP-002', 200,  52.00,  10400.00, 'sent',       'emergency', '2024-07-12', '2024-07-17', NULL, NULL,        'Compra emergencial via ElectroSul'),
('PC-2024-0204', 'FORN-005', 'MP-004', 200,  28.00,  5600.00,  'received',   'normal',    '2024-07-02', '2024-07-05', 200, 'approved',   NULL),
('PC-2024-0205', 'FORN-001', 'MP-005', 80,   85.00,  6800.00,  'sent',       'normal',    '2024-07-08', '2024-07-18', NULL, NULL,        'Reposição mensal de insertos'),
('PC-2024-0206', 'FORN-007', 'MP-006', 4,    420.00, 1680.00,  'approved',   'normal',    '2024-07-14', '2024-07-28', NULL, NULL,        'Rolamentos para PM-2024-156'),
('PC-2024-0207', 'FORN-008', 'MP-009', 2000, 0.85,   1700.00,  'received',   'normal',    '2024-07-08', '2024-07-10', 2000, 'approved',  NULL);

-- Movimentações de estoque (últimos 30 dias)
INSERT INTO inventory_movements (material_id, movement_type, quantity, unit_cost_brl, reference_doc, reason, created_at) VALUES
('MP-001', 'entrada',  1000, 12.50, 'PC-2024-0201', 'Recebimento de compra', NOW() - INTERVAL '5 days'),
('MP-001', 'saida',    150,  12.50, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '4 days'),
('MP-001', 'saida',    200,  12.50, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '3 days'),
('MP-001', 'saida',    175,  12.50, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '2 days'),
('MP-001', 'saida',    125,  12.50, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '1 day'),
('MP-002', 'saida',    30,   45.00, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '4 days'),
('MP-002', 'saida',    25,   45.00, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '3 days'),
('MP-002', 'saida',    20,   45.00, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '2 days'),
('MP-002', 'devolucao', 5,   45.00, 'OP-2024-0451', 'Peças com defeito devolvidas ao estoque', NOW() - INTERVAL '2 days'),
('MP-002', 'saida',    15,   45.00, 'OP-2024-0451', 'Consumo produção',       NOW() - INTERVAL '1 day'),
('MP-003', 'entrada',  3000, 3.50,  'PC-2024-0198', 'Recebimento de compra',  NOW() - INTERVAL '10 days'),
('MP-003', 'saida',    500,  3.50,  'OP-2024-0451', 'Consumo embalagem',      NOW() - INTERVAL '3 days'),
('MP-004', 'entrada',  200,  28.00, 'PC-2024-0204', 'Recebimento de compra',  NOW() - INTERVAL '8 days'),
('MP-004', 'saida',    20,   28.00, 'MAINT-CNC03',  'Consumo manutenção',     NOW() - INTERVAL '3 days'),
('MP-005', 'saida',    8,    85.00, 'OP-2024-0451', 'Troca de inserto CNC-03', NOW() - INTERVAL '5 days'),
('MP-005', 'saida',    6,    85.00, 'OP-2024-0452', 'Troca de inserto CNC-03', NOW() - INTERVAL '2 days'),
('MP-005', 'ajuste',   -2,   85.00, 'INV-2024-07',  'Ajuste inventário - quebra', NOW() - INTERVAL '1 day'),
('MP-009', 'entrada',  2000, 0.85,  'PC-2024-0207', 'Recebimento de compra',  NOW() - INTERVAL '4 days'),
('MP-009', 'saida',    150,  0.85,  'OP-2024-0451', 'Consumo montagem',       NOW() - INTERVAL '2 days'),
('MP-010', 'saida',    50,   2.20,  'OP-2024-0451', 'Consumo acabamento',     NOW() - INTERVAL '3 days');

-- Previsão de demanda (próximos 4 meses)
INSERT INTO material_forecasts (material_id, period_start, period_end, forecast_qty, actual_qty, forecast_method, mape_pct) VALUES
('MP-001', '2024-07-01', '2024-07-31', 1800, 1650, 'media_movel',     8.3),
('MP-001', '2024-08-01', '2024-08-31', 2000, NULL, 'exp_smoothing',   NULL),
('MP-001', '2024-09-01', '2024-09-30', 2200, NULL, 'exp_smoothing',   NULL),
('MP-001', '2024-10-01', '2024-10-31', 1900, NULL, 'exp_smoothing',   NULL),
('MP-002', '2024-07-01', '2024-07-31', 1200, 1050, 'media_movel',     12.5),
('MP-002', '2024-08-01', '2024-08-31', 1500, NULL, 'exp_smoothing',   NULL),
('MP-002', '2024-09-01', '2024-09-30', 1400, NULL, 'exp_smoothing',   NULL),
('MP-005', '2024-07-01', '2024-07-31', 90,   78,   'media_movel',     13.3),
('MP-005', '2024-08-01', '2024-08-31', 100,  NULL, 'manual',          NULL);

-- equipment: id, name, type, line_id, health_score, oee_pct, status, capacity_pcs_hour, shifts_per_day, hours_per_shift, planned_downtime_pct, last_maintenance
INSERT INTO equipment VALUES
('CNC-03',      'Centro de Usinagem CNC XR-500',     'usinagem_3eixos',  'LINHA-01', 62, 72.5, 'atenção',     34, 2, 8.0, 5.0, '2024-06-15 08:00:00'),
('CNC-05',      'Centro de Usinagem 5 Eixos VX-700', 'usinagem_5eixos',  'LINHA-01', 94, 91.2, 'operational', 20, 2, 8.0, 5.0, '2024-07-10 08:00:00'),
('SERRA-01',    'Serra CNC SC-300',                   'corte',            'LINHA-01', 85, 84.5, 'operational', 60, 2, 8.0, 5.0, '2024-07-05 08:00:00'),
('RETIFICA-01', 'Retífica Cilíndrica RC-100',         'acabamento',       'LINHA-01', 91, 89.0, 'operational', 40, 1, 8.0, 5.0, '2024-06-20 08:00:00'),
('FORNO-01',    'Forno de Tratamento Térmico FT-400', 'tratamento_termico','LINHA-01', 95, 92.0, 'operational', 80, 3, 8.0, 3.0, '2024-07-08 08:00:00'),
('PRENSA-01',   'Prensa Hidráulica PH-200',           'conformação',      'LINHA-02', 88, 87.3, 'operational', 50, 1, 8.0, 5.0, '2024-07-01 08:00:00'),
('BROCH-01',    'Brochadeira Vertical BV-200',        'brocheamento',     'LINHA-02', 87, 85.0, 'operational', 25, 1, 8.0, 5.0, '2024-06-28 08:00:00'),
('ANOD-01',     'Tanque de Anodização TA-100',        'anodização',       'LINHA-02', 90, 88.5, 'operational', 30, 1, 8.0, 3.0, '2024-07-03 08:00:00');

-- Histórico de manutenções realizadas
INSERT INTO maintenance_history (id, equipment_id, maintenance_type, scheduled_date, start_date, end_date, duration_hours, description, actions_performed, parts_replaced, labor_hours, cost_brl, technician, status, notes) VALUES
-- CNC-03 (equipamento em atenção, 2 manutenções recentes)
('MNT-2024-0142', 'CNC-03', 'preventiva',
 '2024-06-15 08:00:00', '2024-06-15 08:00:00', '2024-06-15 14:30:00', 6.5,
 'Manutenção preventiva semestral conforme plano PM-001. Inspeção geral do centro de usinagem.',
 ARRAY['Inspeção de guias lineares', 'Verificação de alinhamento do spindle', 'Troca de óleo do cabeçote', 'Calibração geométrica', 'Limpeza de filtros de refrigeração', 'Atualização do software CNC para v4.2.1'],
 ARRAY['Óleo hidráulico ISO 46 (20L)', 'Filtro de óleo hidráulico', 'Filtro de ar comprimido'],
 6.5, 2850.00, 'Carlos Mendes (técnico senior)', 'concluida',
 'Vibração no spindle detectada durante inspeção — agendada substituição de rolamento para próxima parada.'),

('MNT-2024-0098', 'CNC-03', 'corretiva',
 '2024-05-22 14:00:00', '2024-05-22 14:00:00', '2024-05-22 18:45:00', 4.75,
 'Intervenção corretiva por parada não planejada devido a alarme de superaquecimento no servo do eixo Z.',
 ARRAY['Diagnóstico do alarme de superaquecimento', 'Limpeza do dissipador de calor do servo', 'Verificação da ventoinha', 'Teste funcional em vazio', 'Retorno à produção'],
 ARRAY['Ventoinha 24V do servo eixo Z'],
 4.75, 1280.00, 'Rafael Souza (técnico pleno)', 'concluida',
 'Causa raiz: acúmulo de cavacos obstruindo a ventoinha. Recomendada limpeza semanal da região.'),

-- CNC-05 (equipamento novo, manutenção de rotina)
('MNT-2024-0156', 'CNC-05', 'preventiva',
 '2024-07-10 08:00:00', '2024-07-10 08:00:00', '2024-07-10 12:00:00', 4.0,
 'Manutenção preventiva mensal do Centro de Usinagem 5 Eixos VX-700.',
 ARRAY['Verificação de tensão das correias', 'Lubrificação dos eixos rotativos (A/C)', 'Check de pressão pneumática', 'Teste dos interlocks de segurança', 'Verificação do changer automático de ferramentas'],
 ARRAY['Graxa especial EP-2 (0.5kg)'],
 4.0, 680.00, 'Ana Paula Silva (técnica pleno)', 'concluida',
 'Equipamento em excelente estado. Próxima preventiva em 10/08/2024.'),

-- SERRA-01
('MNT-2024-0148', 'SERRA-01', 'preventiva',
 '2024-07-05 08:00:00', '2024-07-05 08:00:00', '2024-07-05 11:30:00', 3.5,
 'Manutenção preventiva mensal da Serra CNC SC-300.',
 ARRAY['Troca de lâmina bimetálica', 'Ajuste de tensão da lâmina', 'Lubrificação de guias', 'Calibração do sistema de refrigeração'],
 ARRAY['Lâmina bimetálica M42 (1un)', 'Fluido de corte (5L)'],
 3.5, 950.00, 'Rafael Souza (técnico pleno)', 'concluida',
 'Lâmina substituída antes do desgaste crítico. Vida útil estimada: 180 horas.'),

-- RETIFICA-01
('MNT-2024-0138', 'RETIFICA-01', 'preventiva',
 '2024-06-20 08:00:00', '2024-06-20 08:00:00', '2024-06-20 16:00:00', 8.0,
 'Manutenção preventiva trimestral com dressagem do rebolo e calibração dimensional.',
 ARRAY['Dressagem do rebolo abrasivo', 'Calibração dimensional com padrões rastreáveis', 'Verificação do alinhamento do cabeçote', 'Inspeção do sistema de refrigeração', 'Balanceamento do rebolo'],
 ARRAY['Rebolo abrasivo grão 120 (reposição preventiva)', 'Óleo lubrificante de cabeçote (2L)'],
 8.0, 1950.00, 'Carlos Mendes (técnico senior)', 'concluida',
 'Equipamento mantido dentro das especificações de precisão (±0.005mm).'),

-- FORNO-01
('MNT-2024-0152', 'FORNO-01', 'preventiva',
 '2024-07-08 06:00:00', '2024-07-08 06:00:00', '2024-07-08 18:00:00', 12.0,
 'Manutenção preventiva semestral do Forno de Tratamento Térmico FT-400. Parada programada.',
 ARRAY['Inspeção de resistências elétricas', 'Verificação de termopares e calibração', 'Limpeza da câmara de aquecimento', 'Teste de estanqueidade da atmosfera controlada', 'Verificação do sistema de controle PID', 'Auditoria de conformidade AMS2750'],
 ARRAY['Termopar tipo K (2un)', 'Junta de vedação da porta', 'Lã cerâmica isolante (5m²)'],
 12.0, 8500.00, 'Empresa terceirizada: TermoTech Ltda', 'concluida',
 'Forno aprovado em auditoria AMS2750 classe 2. Próxima calibração em 6 meses.'),

-- PRENSA-01
('MNT-2024-0145', 'PRENSA-01', 'preventiva',
 '2024-07-01 08:00:00', '2024-07-01 08:00:00', '2024-07-01 13:00:00', 5.0,
 'Manutenção preventiva mensal da Prensa Hidráulica PH-200.',
 ARRAY['Verificação de pressão do sistema hidráulico', 'Troca de filtro de retorno', 'Inspeção de mangueiras e conexões', 'Ajuste dos batentes de segurança', 'Limpeza do reservatório de óleo'],
 ARRAY['Filtro de retorno hidráulico', 'Óleo hidráulico ISO 46 (reposição 10L)'],
 5.0, 1420.00, 'Rafael Souza (técnico pleno)', 'concluida',
 'Pressão operacional estável em 180 bar.'),

-- BROCH-01
('MNT-2024-0141', 'BROCH-01', 'preventiva',
 '2024-06-28 08:00:00', '2024-06-28 08:00:00', '2024-06-28 12:30:00', 4.5,
 'Manutenção preventiva mensal da Brochadeira Vertical BV-200.',
 ARRAY['Inspeção e afiação das brochas', 'Verificação do sistema de tração hidráulica', 'Lubrificação das guias', 'Teste de força de brocheamento'],
 ARRAY['Fluido hidráulico ISO 46 (3L)', 'Graxa para guias (0.2kg)'],
 4.5, 890.00, 'Ana Paula Silva (técnica pleno)', 'concluida',
 'Brochas enviadas para afiação externa — retorno em 03/07/2024.'),

-- ANOD-01
('MNT-2024-0147', 'ANOD-01', 'preventiva',
 '2024-07-03 08:00:00', '2024-07-03 08:00:00', '2024-07-03 14:00:00', 6.0,
 'Manutenção preventiva quinzenal do Tanque de Anodização TA-100.',
 ARRAY['Análise química do banho eletrolítico', 'Ajuste de pH e concentração', 'Limpeza dos eletrodos de chumbo', 'Calibração da fonte retificadora', 'Verificação do sistema de refrigeração'],
 ARRAY['Ácido sulfúrico para reposição (20L)', 'Eletrodo de chumbo (reposição parcial)'],
 6.0, 2100.00, 'Empresa terceirizada: QuimProcess', 'concluida',
 'Banho aprovado. Concentração mantida em 180g/L.');

INSERT INTO production_orders VALUES
('OP-2024-0451', 'PROD-001', 3000, 'LINHA-01', '2024-07-15', '2024-07-19', 'em_andamento', 65, 'high'),
('OP-2024-0452', 'PROD-002', 1500, 'LINHA-02', '2024-07-16', '2024-07-18', 'em_andamento', 40, 'normal'),
('OP-2024-0453', 'PROD-003', 2000, 'LINHA-01', '2024-07-22', '2024-07-25', 'planned', 0, 'normal'),
('OP-2024-0454', 'PROD-004', 800,  'LINHA-01', '2024-07-20', '2024-07-22', 'planned', 0, 'normal'),
('OP-2024-0455', 'PROD-005', 5000, 'LINHA-01', '2024-07-25', '2024-07-30', 'planned', 0, 'normal'),
('OP-2024-0456', 'PROD-006', 500,  'LINHA-01', '2024-07-18', '2024-07-23', 'em_andamento', 25, 'high'),
('OP-2024-0457', 'PROD-007', 1200, 'LINHA-02', '2024-07-20', '2024-07-24', 'planned', 0, 'normal'),
('OP-2024-0458', 'PROD-008', 2500, 'LINHA-02', '2024-07-22', '2024-07-25', 'planned', 0, 'low');

-- ============================================
-- Registros de Qualidade (NCRs)
-- ============================================

INSERT INTO quality_records VALUES
('NCR-2024-071', 'PROD-001', 'dimensional', 'minor', 'Variação no setup matutino', 'corrigida', NOW() - INTERVAL '30 days'),
('NCR-2024-073', 'PROD-002', 'superficial', 'minor', 'Contaminação no banho químico', 'corrigida', NOW() - INTERVAL '28 days'),
('NCR-2024-075', 'PROD-001', 'dimensional', 'major', 'Desgaste progressivo da ferramenta', 'corrigida', NOW() - INTERVAL '25 days'),
('NCR-2024-076', 'PROD-003', 'cosmético', 'minor', 'Riscos na embalagem durante transporte', 'corrigida', NOW() - INTERVAL '22 days'),
('NCR-2024-078', 'PROD-001', 'dimensional', 'critical', 'Erro de setup na troca de turno', 'corrigida', NOW() - INTERVAL '18 days'),
('NCR-2024-080', 'PROD-002', 'funcional', 'major', 'Dureza fora de especificação após têmpera', 'corrigida', NOW() - INTERVAL '15 days'),
('NCR-2024-082', 'PROD-001', 'superficial', 'minor', 'Marcas de ferramenta na superfície usinada', 'corrigida', NOW() - INTERVAL '12 days'),
('NCR-2024-084', 'PROD-003', 'dimensional', 'minor', 'Furo deslocado 0.05mm', 'corrigida', NOW() - INTERVAL '10 days'),
('NCR-2024-085', 'PROD-001', 'superficial', 'minor', 'Contaminação no banho químico', 'em_análise', NOW() - INTERVAL '7 days'),
('NCR-2024-087', 'PROD-002', 'funcional', 'major', 'Rugosidade Ra 1.2 (spec: Ra 0.8)', 'em_análise', NOW() - INTERVAL '5 days'),
('NCR-2024-089', 'PROD-001', 'dimensional', 'major', 'Desgaste de ferramenta CNC-03', 'em_análise', NOW() - INTERVAL '2 days'),
('NCR-2024-090', 'PROD-001', 'cosmético', 'minor', 'Marcas de manuseio pós-usinagem', 'aberta', NOW() - INTERVAL '1 day'),
('NCR-2024-091', 'PROD-004', 'dimensional', 'minor', 'Furação fora de posição 0.08mm em 3 peças', 'em_análise', NOW() - INTERVAL '6 days'),
('NCR-2024-092', 'PROD-006', 'funcional', 'critical', 'Perfil de came fora de especificação - desvio de 0.03mm na rampa', 'aberta', NOW() - INTERVAL '4 days'),
('NCR-2024-093', 'PROD-005', 'dimensional', 'minor', 'Diâmetro 0.005mm acima do limite h6', 'corrigida', NOW() - INTERVAL '8 days'),
('NCR-2024-094', 'PROD-007', 'funcional', 'major', 'Estrias com folga excessiva no acoplamento', 'em_análise', NOW() - INTERVAL '3 days'),
('NCR-2024-095', 'PROD-008', 'superficial', 'minor', 'Anodização com manchas irregulares em lote', 'aberta', NOW() - INTERVAL '2 days');

-- ============================================
-- Decisões dos Agentes (histórico demo)
-- ============================================

INSERT INTO agent_decisions (agent_role, decision, confidence, reasoning, created_at) VALUES
('coordinator', 'Acionou agentes Planner, Supply Chain e Maintenance para análise de pedido urgente', 0.95, 'Demanda envolve capacidade, materiais e disponibilidade de equipamentos', NOW() - INTERVAL '6 hours'),
('planner', 'Capacidade disponível para 5000 unidades em 19 dias com resequenciamento da OP-0453', 0.88, 'Capacidade diária de 264 un. OP-0453 pode ser postergada sem impacto no cliente', NOW() - INTERVAL '5 hours'),
('supply_chain', 'ALERTA: Estoque crítico de MP-002. Recomenda compra emergencial de 4880 pç via ElectroSul', 0.92, 'Estoque atual 120 pç, necessidade 5000 pç. ElectroSul tem lead time 5 dias e 96% reliability', NOW() - INTERVAL '5 hours'),
('maintenance', 'CNC-03 com 34% probabilidade de falha em 18 dias. Antecipar PM-2024-156', 0.78, 'Vibração 7.2mm/s próxima do threshold 8.0. Health score 62/100', NOW() - INTERVAL '4 hours'),
('quality', 'Eixo de Transmissão ET-500 conforme ISO 9001. Atenção: NCR-2024-089 aberta para defeitos dimensionais na CNC-03', 0.90, 'Consultou RAG: requisitos ISO 9001 cláusula 8.5.1. NCR correlacionada com desgaste CNC-03', NOW() - INTERVAL '4 hours'),
('analyst', 'ROI estimado 188%. Receita adicional R$925k. Custo emergencial MP R$33.8k', 0.85, 'Margem bruta 38% sobre preço estimado. Custo emergencial +60% sobre preço normal', NOW() - INTERVAL '3 hours'),
('coordinator', 'DECISÃO: Pedido VIÁVEL com ressalvas. 3 riscos identificados. Recomenda aprovação', 0.87, 'Consolidação de 5 agentes. Prioridade: Segurança > Qualidade > Prazo > Custo', NOW() - INTERVAL '3 hours');

-- ============================================
-- Dados de Sensores IoT (séries temporais 48h)
-- Gera leituras a cada 15 min para os 4 equipamentos
-- ============================================

-- CNC-03: vibração crescente (preocupante)
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'CNC-03', 'vibration',
    ROUND((5.5 + (EXTRACT(EPOCH FROM gs) - EXTRACT(EPOCH FROM NOW() - INTERVAL '48 hours')) / 172800.0 * 2.0 + (RANDOM() * 0.4 - 0.2))::numeric, 3),
    'mm/s', 8.0,
    CASE WHEN 5.5 + (EXTRACT(EPOCH FROM gs) - EXTRACT(EPOCH FROM NOW() - INTERVAL '48 hours')) / 172800.0 * 2.0 > 7.0 THEN 'warning' ELSE 'normal' END,
    gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- CNC-03: temperatura crescente
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'CNC-03', 'temperature',
    ROUND((58 + (EXTRACT(EPOCH FROM gs) - EXTRACT(EPOCH FROM NOW() - INTERVAL '48 hours')) / 172800.0 * 12.0 + (RANDOM() * 2 - 1))::numeric, 1),
    '°C', 75,
    CASE WHEN 58 + (EXTRACT(EPOCH FROM gs) - EXTRACT(EPOCH FROM NOW() - INTERVAL '48 hours')) / 172800.0 * 12.0 > 65 THEN 'warning' ELSE 'normal' END,
    gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- CNC-03: corrente do spindle
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'CNC-03', 'spindle_current',
    ROUND((10.5 + (RANDOM() * 3 - 0.5) + SIN(EXTRACT(EPOCH FROM gs) / 3600) * 1.5)::numeric, 2),
    'A', 15,
    'normal',
    gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- CNC-03: pressão de óleo (ligeira queda)
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'CNC-03', 'oil_pressure',
    ROUND((5.2 - (EXTRACT(EPOCH FROM gs) - EXTRACT(EPOCH FROM NOW() - INTERVAL '48 hours')) / 172800.0 * 0.5 + (RANDOM() * 0.3 - 0.15))::numeric, 2),
    'bar', 4.0,
    'normal',
    gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- PRENSA-01: todos os sensores estáveis (equipamento saudável)
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'PRENSA-01', 'vibration',
    ROUND((3.0 + (RANDOM() * 0.6 - 0.3))::numeric, 3),
    'mm/s', 8.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'PRENSA-01', 'temperature',
    ROUND((42 + (RANDOM() * 4 - 2))::numeric, 1),
    '°C', 75, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'PRENSA-01', 'oil_pressure',
    ROUND((5.5 + (RANDOM() * 0.4 - 0.2))::numeric, 2),
    'bar', 4.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- RETIFICA-01: estável
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'RETIFICA-01', 'vibration',
    ROUND((2.5 + (RANDOM() * 0.4 - 0.2))::numeric, 3),
    'mm/s', 8.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'RETIFICA-01', 'temperature',
    ROUND((38 + (RANDOM() * 3 - 1.5))::numeric, 1),
    '°C', 75, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- SERRA-01: estável
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'SERRA-01', 'vibration',
    ROUND((3.5 + (RANDOM() * 0.5 - 0.25))::numeric, 3),
    'mm/s', 8.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT
    'SERRA-01', 'temperature',
    ROUND((45 + (RANDOM() * 3 - 1.5))::numeric, 1),
    '°C', 75, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- CNC-05 (5 eixos): sensores estáveis (equipamento novo)
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'CNC-05', 'vibration', ROUND((2.0 + (RANDOM() * 0.4 - 0.2))::numeric, 3), 'mm/s', 8.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'CNC-05', 'temperature', ROUND((35 + (RANDOM() * 3 - 1.5))::numeric, 1), '°C', 75, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'CNC-05', 'spindle_current', ROUND((8.0 + (RANDOM() * 2 - 1))::numeric, 2), 'A', 15, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- FORNO-01: temperatura do forno (alta por natureza, threshold 950°C)
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'FORNO-01', 'temperature', ROUND((850 + (RANDOM() * 20 - 10))::numeric, 1), '°C', 950, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'FORNO-01', 'gas_pressure', ROUND((2.5 + (RANDOM() * 0.3 - 0.15))::numeric, 2), 'bar', 3.5, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- BROCH-01: força de brocheamento e vibração
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'BROCH-01', 'vibration', ROUND((3.2 + (RANDOM() * 0.5 - 0.25))::numeric, 3), 'mm/s', 8.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'BROCH-01', 'force', ROUND((4500 + (RANDOM() * 300 - 150))::numeric, 0), 'N', 6000, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- ANOD-01: temperatura do banho e pH
INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'ANOD-01', 'temperature', ROUND((22 + (RANDOM() * 2 - 1))::numeric, 1), '°C', 30, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

INSERT INTO sensor_readings (equipment_id, sensor_type, value, unit, threshold, status, read_at)
SELECT 'ANOD-01', 'ph_level', ROUND((1.2 + (RANDOM() * 0.3 - 0.15))::numeric, 2), 'pH', 2.0, 'normal', gs
FROM generate_series(NOW() - INTERVAL '48 hours', NOW(), INTERVAL '15 minutes') AS gs;

-- ============================================
-- Logs de Automação (histórico simulado 48h)
-- ============================================

INSERT INTO automation_logs (workflow_name, trigger_type, status, summary, details, agents_involved, duration_ms, created_at) VALUES
('Monitor de Sensores', 'cron', 'success', 'Todos os sensores dentro dos limites', '{"equipment_checked": 4, "alerts": 0}', ARRAY['maintenance'], 1200, NOW() - INTERVAL '48 hours'),
('Monitor de Sensores', 'cron', 'success', 'Todos os sensores dentro dos limites', '{"equipment_checked": 4, "alerts": 0}', ARRAY['maintenance'], 980, NOW() - INTERVAL '47 hours'),
('Alerta de Estoque', 'cron', 'success', 'Estoques adequados', '{"materials_checked": 3, "critical": 0}', ARRAY['supply_chain'], 850, NOW() - INTERVAL '47 hours'),
('Monitor de Sensores', 'cron', 'success', 'Sensores normais', '{"equipment_checked": 4, "alerts": 0}', ARRAY['maintenance'], 1100, NOW() - INTERVAL '46 hours'),
('Monitor de Sensores', 'cron', 'success', 'Sensores normais', '{"equipment_checked": 4, "alerts": 0}', ARRAY['maintenance'], 1050, NOW() - INTERVAL '45 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 6.5 mm/s (tendência alta)', '{"equipment_checked": 4, "alerts": 1, "alert_equipment": "CNC-03", "sensor": "vibration", "value": 6.5}', ARRAY['maintenance'], 1500, NOW() - INTERVAL '44 hours'),
('Alerta de Estoque', 'cron', 'warning', 'MP-002 abaixo do estoque mínimo (120 vs 500)', '{"materials_checked": 3, "critical": 1, "material": "MP-002", "stock": 120, "min": 500}', ARRAY['supply_chain'], 920, NOW() - INTERVAL '43 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 6.8 mm/s (tendência alta)', '{"equipment_checked": 4, "alerts": 1, "alert_equipment": "CNC-03", "sensor": "vibration", "value": 6.8}', ARRAY['maintenance'], 1350, NOW() - INTERVAL '42 hours'),
('Relatório Diário', 'cron', 'success', 'Relatório gerado: OEE 78.5%, OTIF 91%, 3 NCRs abertas', '{"oee": 78.5, "otif": 91, "ncrs_open": 3, "critical_stock": 1}', ARRAY['analyst', 'planner', 'quality', 'supply_chain', 'maintenance'], 8500, NOW() - INTERVAL '40 hours'),
('Monitor de Sensores', 'cron', 'success', 'Sensores normais', '{"equipment_checked": 4, "alerts": 0}', ARRAY['maintenance'], 1000, NOW() - INTERVAL '38 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 7.0 mm/s — próximo do threshold', '{"equipment_checked": 4, "alerts": 1, "alert_equipment": "CNC-03", "sensor": "vibration", "value": 7.0}', ARRAY['maintenance'], 1400, NOW() - INTERVAL '36 hours'),
('Alerta de Estoque', 'cron', 'critical', 'CRÍTICO: MP-002 com apenas 3 dias de cobertura', '{"materials_checked": 3, "critical": 1, "material": "MP-002", "stock": 120, "min": 500, "days_supply": 3}', ARRAY['supply_chain', 'coordinator'], 2100, NOW() - INTERVAL '35 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 7.1 mm/s + temperatura 65°C', '{"equipment_checked": 4, "alerts": 2, "alert_equipment": "CNC-03"}', ARRAY['maintenance', 'coordinator'], 1800, NOW() - INTERVAL '30 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 7.2 mm/s — RECOMENDA ANTECIPAR MANUTENÇÃO', '{"equipment_checked": 4, "alerts": 2, "alert_equipment": "CNC-03", "sensor": "vibration", "value": 7.2, "recommendation": "antecipar_PM-2024-156"}', ARRAY['maintenance', 'coordinator', 'planner'], 2500, NOW() - INTERVAL '24 hours'),
('Relatório Diário', 'cron', 'warning', 'Relatório gerado: CNC-03 em atenção, MP-002 crítico', '{"oee": 78.5, "otif": 91, "ncrs_open": 3, "critical_stock": 1, "equipment_warning": 1}', ARRAY['analyst', 'planner', 'quality', 'supply_chain', 'maintenance'], 9200, NOW() - INTERVAL '16 hours'),
('Alerta de Estoque', 'cron', 'critical', 'CRÍTICO: MP-002 com 2 dias de cobertura. Compra emergencial recomendada', '{"materials_checked": 3, "critical": 1, "material": "MP-002", "stock": 100, "days_supply": 2}', ARRAY['supply_chain', 'coordinator'], 2300, NOW() - INTERVAL '11 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 7.2 mm/s, temperatura 68°C', '{"equipment_checked": 4, "alerts": 2}', ARRAY['maintenance'], 1300, NOW() - INTERVAL '6 hours'),
('Monitor de Sensores', 'cron', 'warning', 'CNC-03: vibração 7.3 mm/s — 91% do threshold', '{"equipment_checked": 4, "alerts": 2, "alert_equipment": "CNC-03", "sensor": "vibration", "value": 7.3, "threshold_pct": 91}', ARRAY['maintenance', 'coordinator'], 1600, NOW() - INTERVAL '1 hour');

-- ============================================
-- Índices
-- ============================================

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_decisions_conversation ON agent_decisions(conversation_id);
CREATE INDEX idx_sensor_readings_equipment ON sensor_readings(equipment_id, read_at);
CREATE INDEX idx_sensor_readings_type ON sensor_readings(equipment_id, sensor_type, read_at);
CREATE INDEX idx_production_orders_status ON production_orders(status);
CREATE INDEX idx_quality_records_product ON quality_records(product_id, created_at);
CREATE INDEX idx_quality_records_status ON quality_records(status);
CREATE INDEX idx_maintenance_history_equipment ON maintenance_history(equipment_id, end_date DESC);
CREATE INDEX idx_automation_logs_workflow ON automation_logs(workflow_name, created_at);
CREATE INDEX idx_automation_logs_status ON automation_logs(status, created_at);
CREATE INDEX idx_materials_abc ON materials(abc_class);
CREATE INDEX idx_materials_category ON materials(category);
CREATE INDEX idx_supplier_materials_supplier ON supplier_materials(supplier_id);
CREATE INDEX idx_supplier_materials_material ON supplier_materials(material_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_orders_material ON purchase_orders(material_id);
CREATE INDEX idx_inventory_movements_material ON inventory_movements(material_id, created_at);
CREATE INDEX idx_inventory_movements_type ON inventory_movements(movement_type, created_at);
CREATE INDEX idx_material_forecasts_material ON material_forecasts(material_id, period_start);
