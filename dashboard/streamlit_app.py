"""
NEXUS 4.0 - Chat Interface (Streamlit)
Interface de conversação com o sistema multi-agente.
Dashboards operacionais estão no Grafana (porta 3000).
"""

import io
import os
import re

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ============================================
# Configuração
# ============================================

st.set_page_config(
    page_title="NEXUS 4.0 - Chat com Agentes",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

NEXUS_API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8080")


def api_call(method: str, endpoint: str, **kwargs):
    """Chamada à API do NEXUS."""
    try:
        with httpx.Client(timeout=120) as client:
            r = getattr(client, method)(f"{NEXUS_API_URL}{endpoint}", **kwargs)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return {"error": str(e)}


def parse_markdown_table(text: str) -> pd.DataFrame | None:
    """Extrai a primeira tabela markdown de um texto e retorna como DataFrame."""
    lines = text.strip().split("\n")
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|"):
            in_table = True
            # Ignora linha separadora (|---|---|)
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            table_lines.append(stripped)
        elif in_table:
            break  # Saiu da tabela

    if len(table_lines) < 2:  # Header + pelo menos 1 linha
        return None

    # Parse header
    headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]

    # Parse rows
    rows = []
    for line in table_lines[1:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == len(headers):
            rows.append(cells)

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=headers)

    # Tenta converter colunas numéricas
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col].str.replace(",", ".").str.replace("%", ""))
        except (ValueError, AttributeError):
            pass

    return df


_chart_counter = 0

def render_chart(df: pd.DataFrame):
    """Gera gráficos Plotly automaticamente baseado no conteúdo do DataFrame."""
    global _chart_counter

    if df is None or len(df) < 2:
        return

    label_col = df.columns[0]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
        return

    _chart_counter += 1
    chart_id = _chart_counter
    num_rows = len(df)

    # Seleciona as 3 colunas numéricas mais relevantes para o gráfico principal
    # (evita poluir com muitas colunas)
    main_cols = numeric_cols[:3]

    # Gráfico 1: Bar chart comparativo (sempre funciona bem)
    fig = go.Figure()
    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
    for i, col in enumerate(main_cols):
        fig.add_trace(go.Bar(
            name=col,
            x=df[label_col],
            y=df[col],
            marker_color=colors[i % len(colors)],
            text=df[col],
            textposition="auto",
        ))
    fig.update_layout(
        barmode="group",
        height=max(300, num_rows * 70),
        title=f"Comparativo: {', '.join(main_cols)}",
        template="plotly_white",
        font=dict(size=12),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{chart_id}_{id(fig)}")

    # Gráfico 2: Se tem coluna que parece ser "ranking" (rating, score, OEE)
    # → gráfico de indicadores (gauge-like horizontal)
    ranking_cols = [c for c in numeric_cols if any(w in c.lower() for w in
                    ["rating", "score", "oee", "health", "confiab", "reliab", "qualid"])]
    if ranking_cols and ranking_cols[0] not in main_cols[:1]:
        rank_col = ranking_cols[0]
        fig2 = px.bar(
            df.sort_values(rank_col, ascending=True),
            x=rank_col, y=label_col,
            orientation="h",
            color=rank_col,
            color_continuous_scale="RdYlGn",
            title=f"Ranking: {rank_col}",
        )
        fig2.update_layout(height=max(200, num_rows * 55), showlegend=False, template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)


def render_response(response: str):
    """Renderiza a resposta com markdown + gráficos automáticos."""
    # Renderiza o markdown completo
    st.markdown(response)

    # Tenta extrair tabela e gerar gráfico
    df = parse_markdown_table(response)
    if df is not None and len(df) >= 2:
        render_chart(df)


# ============================================
# Sidebar
# ============================================

with st.sidebar:
    st.title("🤖 NEXUS 4.0")
    st.caption("Sistema Multi-Agente para Gestão de Operações Industriais")
    st.divider()

    page = st.radio(
        "Navegação",
        ["💬 Chat com NEXUS", "🔍 Consulta Direta", "📡 Status dos Agentes"],
        index=0,
    )

    st.divider()

    st.markdown("**Dashboards Operacionais:**")
    st.markdown("[Abrir Grafana →](http://localhost:3000)")
    st.caption("Visão Geral | Manutenção | Supply Chain | Qualidade | Financeiro")

    st.divider()
    st.caption("**Sistemas Avançados em Engenharia de Produção e IA**")
    st.caption("PPGEPS/Unisinos")


# ============================================
# Chat com NEXUS (Coordinator)
# ============================================

if page == "💬 Chat com NEXUS":
    st.title("💬 Chat com NEXUS")
    st.markdown(
        "Converse com o sistema multi-agente como se fosse um gestor de operações. "
        "O **Coordinator** recebe sua mensagem e orquestra os agentes especializados."
    )

    with st.expander("💡 Exemplos de perguntas"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Produção & PCP:**
            - *"Recebi um pedido urgente de 5000 unidades do Eixo de Transmissão ET-500 para sexta-feira. É viável?"*
            - *"Qual a capacidade disponível esta semana?"*
            - *"Preciso resequenciar a produção para priorizar o Produto Y"*
            """)
            st.markdown("""
            **Manutenção:**
            - *"Qual o status da CNC-03? Devemos antecipar a manutenção?"*
            - *"Quais equipamentos estão em risco?"*
            """)
        with col2:
            st.markdown("""
            **Supply Chain:**
            - *"Estamos com estoque crítico de componentes eletrônicos. O que fazer?"*
            - *"Qual o lead time para compra emergencial de MP-002?"*
            """)
            st.markdown("""
            **Análise & Qualidade:**
            - *"Gere um relatório executivo de performance da semana"*
            - *"Quais são os maiores riscos operacionais neste momento?"*
            - *"Qual o status de qualidade do Eixo de Transmissão ET-500?"*
            """)

    # Estado do chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    # Histórico
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"] == "user" else "🤖"):
            if msg["role"] == "assistant":
                render_response(msg["content"])
            else:
                st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Digite sua mensagem para o NEXUS..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👨‍💼"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🧠 Coordinator orquestrando agentes..."):
                result = api_call(
                    "post", "/chat",
                    json={
                        "message": prompt,
                        "user_id": "dashboard",
                        "conversation_id": st.session_state.conversation_id,
                    },
                )

            if "error" in result:
                response = (
                    f"⚠️ Erro de conexão com a API: {result['error']}\n\n"
                    f"Certifique-se de que o NEXUS API está rodando em `{NEXUS_API_URL}`"
                )
            else:
                response = result.get("response", "Sem resposta")
                st.session_state.conversation_id = result.get("conversation_id")

            render_response(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})

    col1, col2 = st.columns([1, 8])
    with col1:
        if st.button("🗑️ Limpar"):
            st.session_state.chat_history = []
            st.session_state.conversation_id = None
            st.rerun()


# ============================================
# Consulta Direta a Agente
# ============================================

elif page == "🔍 Consulta Direta":
    st.title("🔍 Consulta Direta a Agente")
    st.markdown(
        "Converse diretamente com um agente específico, "
        "sem passar pelo Coordinator. Útil para debug e demonstração."
    )

    agent_info = {
        "planner": ("📋 Planner (PCP)", "Planejamento de produção, capacidade, sequenciamento, MRP"),
        "quality": ("🔍 Quality", "Qualidade, CEP, normas ISO, não-conformidades, RAG em procedimentos"),
        "supply_chain": ("📦 Supply Chain", "Estoque, fornecedores, lead times, compras"),
        "maintenance": ("🔧 Maintenance", "Manutenção preditiva, sensores IoT, health score, OEE"),
        "analyst": ("📊 Analyst", "KPIs, relatórios executivos, análise financeira, impacto"),
    }

    agent_select = st.selectbox(
        "Selecione o agente:",
        list(agent_info.keys()),
        format_func=lambda x: f"{agent_info[x][0]}",
    )

    st.info(f"**Especialidade:** {agent_info[agent_select][1]}")

    # Estado por agente
    state_key = f"direct_history_{agent_select}"
    if state_key not in st.session_state:
        st.session_state[state_key] = []

    for msg in st.session_state[state_key]:
        with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])

    if prompt := st.chat_input(f"Pergunte ao {agent_info[agent_select][0]}..."):
        st.session_state[state_key].append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👨‍💼"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner(f"Consultando {agent_info[agent_select][0]}..."):
                result = api_call(
                    "post", f"/agent/{agent_select}",
                    json={"agent": agent_select, "message": prompt},
                )

            if "error" in result:
                response = f"⚠️ Erro: {result['error']}"
            else:
                response = result.get("response", "Sem resposta")

            st.markdown(response)
            st.session_state[state_key].append({"role": "assistant", "content": response})


# ============================================
# Status dos Agentes
# ============================================

elif page == "📡 Status dos Agentes":
    st.title("📡 Status dos Agentes")

    # Tenta buscar da API
    status = api_call("get", "/agents")

    if "error" in status:
        st.warning(f"API não acessível: {status['error']}")
        st.markdown("Mostrando informações estáticas dos agentes:")

    st.markdown("### Arquitetura Multi-Agente")
    st.markdown("""
    ```
    ┌──────────────────────────────────────────────────────────────┐
    │                     👨‍💼 GESTOR                               │
    │               (WhatsApp / Chat UI)                           │
    └───────────────────────┬──────────────────────────────────────┘
                            │
    ┌───────────────────────▼──────────────────────────────────────┐
    │                  🧠 COORDINATOR                              │
    │         Analisa → Delega → Consolida → Responde              │
    │     Resolve conflitos: Segurança > Qualidade > Prazo > Custo │
    └──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │          │
    ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼──────┐
    │ 📋   │  │ 🔍   │  │ 📦   │  │ 🔧   │  │ 📊      │
    │ PCP  │  │ Qual │  │  SC  │  │ Mnt  │  │ Analyst │
    └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬──────┘
       │         │         │         │          │
    ┌──▼─────────▼─────────▼─────────▼──────────▼──────┐
    │  PostgreSQL  │  ChromaDB (RAG)  │  Sensores IoT   │
    └──────────────────────────────────────────────────┘
    ```
    """)

    st.markdown("### Agentes Registrados")

    agents_static = [
        {"Agente": "🧠 Coordinator", "Role": "Orquestrador", "Ferramentas": "delegate_to_agent, resolve_conflict"},
        {"Agente": "📋 Planner", "Role": "PCP", "Ferramentas": "check_capacity, get_schedule, simulate_plan"},
        {"Agente": "🔍 Quality", "Role": "Qualidade", "Ferramentas": "get_metrics, defect_history, compliance + RAG"},
        {"Agente": "📦 Supply Chain", "Role": "Suprimentos", "Ferramentas": "check_inventory, supplier_info, purchase_order"},
        {"Agente": "🔧 Maintenance", "Role": "Manutenção", "Ferramentas": "equipment_health, schedule, predict_failure"},
        {"Agente": "📊 Analyst", "Role": "Analytics", "Ferramentas": "get_kpis, calculate_impact, generate_report"},
    ]

    import pandas as pd
    st.dataframe(pd.DataFrame(agents_static), use_container_width=True, hide_index=True)

    # Mostra dados da API se disponível
    if "error" not in status and status:
        st.markdown("### Dados em Tempo Real (da API)")
        for name, info in status.items():
            col1, col2, col3 = st.columns(3)
            col1.metric(f"{info.get('name', name)}", "Online")
            col2.metric("Memória", f"{info.get('memory_size', 0)} msgs")
            col3.metric("Processadas", f"{info.get('messages_processed', 0)} msgs")
