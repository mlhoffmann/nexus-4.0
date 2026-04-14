"""
NEXUS 4.0 - Coordinator Agent
Orquestra todos os agentes, delega tarefas e resolve conflitos.
"""

import json
from typing import Any

from agents.base_agent import AgentDecision, AgentMessage, AgentRole, BaseAgent


class CoordinatorAgent(BaseAgent):
    """Agente Coordenador - Cérebro central do NEXUS."""

    def __init__(self, openai_client, model="gpt-4.1", **kwargs):
        super().__init__(
            role=AgentRole.COORDINATOR,
            name="Coordinator",
            openai_client=openai_client,
            model=model,
            **kwargs,
        )
        self.agent_registry: dict[AgentRole, BaseAgent] = {}
        self.active_conversations: dict[str, list[AgentMessage]] = {}

    def register_agent(self, agent: BaseAgent):
        """Registra um agente no sistema."""
        self.agent_registry[agent.role] = agent
        self.logger.info(f"Agente registrado: {agent.name} ({agent.role.value})")

    @property
    def system_prompt(self) -> str:
        available_agents = ", ".join(
            [f"{role.value} ({agent.name})" for role, agent in self.agent_registry.items()]
        )
        return f"""Você é o COORDENADOR do sistema NEXUS 4.0 — um sistema multi-agente para gestão
de operações industriais. Você é o cérebro central que orquestra todos os outros agentes.

## Agentes Disponíveis
{available_agents}

## Suas Responsabilidades
1. ANALISAR demandas recebidas e identificar quais agentes precisam ser acionados
2. DECOMPOR problemas complexos em subtarefas para cada agente especialista
3. CONSOLIDAR respostas dos agentes em uma visão unificada
4. RESOLVER CONFLITOS quando agentes têm recomendações divergentes
5. TOMAR DECISÕES finais quando necessário, priorizando segurança e eficiência
6. COMUNICAR resultados de forma clara e executiva para o gestor

## Regras de Orquestração
- Sempre acione MÚLTIPLOS agentes quando o problema envolve diferentes áreas
- Identifique DEPENDÊNCIAS entre tarefas (ex: Planner depende de Supply Chain para saber estoque)
- Em caso de conflito entre agentes, priorize: Segurança > Qualidade > Prazo > Custo
- Sempre inclua análise de RISCO na consolidação final
- SEMPRE cite dados concretos do grafo de conhecimento: IDs de equipamentos, produtos, NCRs,
  ordens de produção, fornecedores, valores de sensores, etc. NÃO seja genérico.
- Ao consolidar, mencione as CONEXÕES entre entidades (ex: "CNC-03 produz Produto X, que tem
  NCR-2024-089 aberta por desgaste de ferramenta, e manutenção PM-2024-156 agendada")

## INTEGRIDADE DE DADOS — REGRA ABSOLUTA
- NUNCA invente números, percentuais ou métricas que não vieram dos agentes ou do grafo
- Ao consolidar respostas dos agentes, preserve os valores EXATOS que eles informaram
- Se um agente disse "rating 4.2", você diz "rating 4.2" — NÃO converta para outra escala
- Se um agente disse "lead time 5 dias", você diz "lead time 5 dias" — NÃO altere
- Se um dado não existe, simplesmente OMITA o campo — NÃO escreva "dado não disponível"
- Inclua APENAS campos que possuem valores reais dos agentes
- Suas análises e recomendações podem ser interpretativas, mas os DADOS devem ser fiéis

## Formato de Resposta ao Gestor
Adapte a profundidade da resposta à complexidade da pergunta:

### Perguntas SIMPLES (lead time, preço, status, quem fornece):
Responda de forma DIRETA e CONCISA. Use tabela markdown quando comparar entidades:

| Fornecedor | Lead Time | Preço | Rating |
|------------|-----------|-------|--------|
| ElectroSul | 5 dias    | 52.00 | 4.5    |

Depois da tabela, uma recomendação em 1-2 frases. Sem seções longas.

### Perguntas COMPLEXAS (viabilidade de pedido, relatório, análise de risco):
Use formato completo com:
- Status geral (✅ Viável / ⚠️ Viável com ressalvas / ❌ Inviável)
- Tabelas comparativas com dados dos agentes
- Ações necessárias (lista curta)
- Riscos (lista curta)
- Recomendação final (1-2 frases)

### REGRAS GERAIS:
- Use TABELAS markdown para comparar entidades (fornecedores, materiais, equipamentos)
- Inclua apenas os campos RELEVANTES para a pergunta — não liste todos os campos
- Seja DIRETO — comece com a resposta, não com introdução
- Máximo 3-5 campos por entidade na tabela (os mais relevantes para a pergunta)
- Adicione detalhes extras APENAS se necessário para a decisão

Responda SEMPRE em português brasileiro.

## Formato para Delegação
Quando precisar delegar tarefas, responda em JSON:
{{
    "delegations": [
        {{
            "agent": "planner|quality|supply_chain|maintenance|analyst",
            "task": "descrição da tarefa",
            "priority": "high|medium|low",
            "depends_on": ["agent_name"]
        }}
    ],
    "reasoning": "por que esses agentes foram escolhidos"
}}"""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "delegate_to_agent",
                    "description": "Delega uma tarefa para um agente especialista",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_role": {
                                "type": "string",
                                "enum": ["planner", "quality", "supply_chain", "maintenance", "analyst"],
                                "description": "O papel do agente que receberá a tarefa",
                            },
                            "task": {
                                "type": "string",
                                "description": "Descrição da tarefa a ser delegada",
                            },
                            "context": {
                                "type": "object",
                                "description": "Contexto adicional para o agente",
                            },
                        },
                        "required": ["agent_role", "task"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_conflict",
                    "description": "Resolve um conflito entre recomendações de diferentes agentes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "positions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "agent": {"type": "string"},
                                        "recommendation": {"type": "string"},
                                        "reasoning": {"type": "string"},
                                    },
                                },
                                "description": "Posições conflitantes dos agentes",
                            },
                        },
                        "required": ["positions"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        if tool_name == "delegate_to_agent":
            return await self._delegate(arguments)
        elif tool_name == "resolve_conflict":
            return await self._resolve_conflict(arguments)
        return {"error": f"Tool '{tool_name}' desconhecida"}

    async def _delegate(self, args: dict) -> dict:
        """Delega tarefa para um agente específico."""
        role_str = args["agent_role"]
        task = args["task"]
        context = args.get("context", {})

        try:
            role = AgentRole(role_str)
        except ValueError:
            return {"error": f"Agente '{role_str}' não existe"}

        agent = self.agent_registry.get(role)
        if not agent:
            return {"error": f"Agente '{role_str}' não registrado"}

        self.logger.info(f"Delegando para {role_str}: {task[:60]}...")
        response = await agent.think(task, context)
        return {"agent": role_str, "response": response}

    async def _resolve_conflict(self, args: dict) -> dict:
        """Resolve conflito entre agentes usando critérios de prioridade."""
        positions = args["positions"]
        conflict_summary = json.dumps(positions, ensure_ascii=False)

        resolution_prompt = f"""Resolva este conflito entre agentes usando a prioridade:
Segurança > Qualidade > Prazo > Custo

Posições:
{conflict_summary}

Forneça uma resolução fundamentada."""

        resolution = await self.think(resolution_prompt)
        return {"resolution": resolution, "positions_analyzed": len(positions)}

    async def orchestrate(
        self, user_request: str, conversation_id: str, context: dict[str, Any] | None = None
    ) -> str:
        """Fluxo principal: recebe demanda do usuário e orquestra agentes."""
        self.logger.info(f"Nova demanda: {user_request[:80]}...")

        # Fase 1: Delega diretamente para agentes relevantes e coleta respostas
        agent_responses = {}
        agents_to_query = self._determine_agents(user_request)

        for agent_role in agents_to_query:
            agent = self.agent_registry.get(agent_role)
            if agent:
                task = f"""Responda a seguinte demanda do gestor com TODOS os dados disponíveis
nas suas ferramentas. Use suas tools obrigatoriamente. Inclua TODOS os campos retornados
(preço, lead time, rating, confiabilidade, qualidade, localização, IDs, etc.).
Liste cada entidade individualmente com seus dados específicos.

DEMANDA: {user_request}"""
                self.logger.info(f"Delegando para {agent_role.value}: {user_request[:60]}...")
                response = await agent.think(task, context)
                agent_responses[agent_role.value] = response

        # Fase 2: Consolida as respostas dos agentes
        responses_text = "\n\n".join(
            [f"=== AGENTE {name.upper()} ===\n{resp}" for name, resp in agent_responses.items()]
        )

        consolidation_prompt = f"""Consolide as respostas abaixo numa resposta final para o gestor.

DEMANDA ORIGINAL: {user_request}

RESPOSTAS DOS AGENTES (dados REAIS — preserve os valores exatamente):
{responses_text}

REGRAS DE DADOS:
1. Preserve todos os valores numéricos EXATAMENTE como os agentes informaram
2. NUNCA escreva "dado não disponível" — omita campos sem valor
3. NUNCA invente dados que não vieram dos agentes
4. Ao citar equipamentos, materiais ou fornecedores, use SEMPRE o formato "Nome (ID)"
   Ex: "Centro de Usinagem CNC XR-500 (CNC-03)", "Barra de Aço SAE 1045 (MP-001)"
   NUNCA use só o ID ou só o nome — sempre os dois juntos para evitar confusão

REGRAS DE FORMATO:
1. Seja DIRETO — comece com a resposta principal, sem introdução longa
2. Use TABELAS markdown para comparar entidades (fornecedores, materiais, equipamentos):
   | Coluna1 | Coluna2 | Coluna3 |
   |---------|---------|---------|
   | dado1   | dado2   | dado3   |
3. Inclua apenas 3-5 campos RELEVANTES para a pergunta nas tabelas
4. Para perguntas simples: tabela + recomendação em 1-2 frases
5. Para perguntas complexas: tabela + ações + riscos + recomendação
6. Não repita os mesmos dados em seções diferentes"""

        # Consolidação sem tools (apenas síntese)
        final_response = await self._consolidate(consolidation_prompt)
        return final_response

    async def _consolidate(self, prompt: str) -> str:
        """Consolida sem usar tools — apenas síntese de texto."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _determine_agents(self, request: str) -> list:
        """Determina quais agentes acionar baseado na demanda."""
        from agents.base_agent import AgentRole

        request_lower = request.lower()
        agents = []

        # Sempre aciona Supply Chain para questões de fornecedores/materiais
        if any(w in request_lower for w in ["fornecedor", "material", "estoque", "compra", "supply", "mp-"]):
            agents.append(AgentRole.SUPPLY_CHAIN)

        # Qualidade
        if any(w in request_lower for w in ["qualidade", "ncr", "defeito", "norma", "iso", "conformidade"]):
            agents.append(AgentRole.QUALITY)

        # Manutenção
        if any(w in request_lower for w in ["manutenção", "manuten", "sensor", "falha", "health", "vibração", "temperatura"]):
            agents.append(AgentRole.MAINTENANCE)

        # Planejamento (inclui equipamentos, capacidade, disponibilidade)
        if any(w in request_lower for w in ["produção", "capacidade", "pedido", "ordem", "plano", "sequenci",
                                             "equipamento", "disponibilidade", "disponível", "cnc", "serra",
                                             "prensa", "retífica", "retifica", "turno", "oee"]):
            agents.append(AgentRole.PLANNER)

        # Analyst
        if any(w in request_lower for w in ["relatório", "kpi", "custo", "impacto", "financ", "roi", "melhor"]):
            agents.append(AgentRole.ANALYST)

        # Se nenhum match, aciona todos
        if not agents:
            agents = list(self.agent_registry.keys())

        # Se pergunta "qual o melhor", adiciona analyst para comparação
        if "melhor" in request_lower and AgentRole.ANALYST not in agents:
            agents.append(AgentRole.ANALYST)

        return agents
