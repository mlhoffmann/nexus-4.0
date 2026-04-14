"""
NEXUS 4.0 - Base Agent
Classe base para todos os agentes do sistema multi-agente.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger("nexus")


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    QUALITY = "quality"
    SUPPLY_CHAIN = "supply_chain"
    MAINTENANCE = "maintenance"
    ANALYST = "analyst"


class AgentMessage(BaseModel):
    """Mensagem trocada entre agentes."""

    sender: AgentRole
    receiver: AgentRole | str
    content: str
    message_type: str = "request"  # request, response, alert, report
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    conversation_id: str | None = None


class AgentDecision(BaseModel):
    """Decisão estruturada de um agente."""

    agent: AgentRole
    decision: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class BaseAgent(ABC):
    """Classe base abstrata para todos os agentes NEXUS."""

    def __init__(
        self,
        role: AgentRole,
        name: str,
        openai_client: AsyncOpenAI,
        model: str = "gpt-4.1",
        rag_retriever=None,
        graph_retriever=None,
        db_session=None,
    ):
        self.role = role
        self.name = name
        self.client = openai_client
        self.model = model
        self.rag_retriever = rag_retriever
        self.graph_retriever = graph_retriever
        self.db_session = db_session
        self.memory: list[dict] = []
        self.message_history: list[AgentMessage] = []
        self._force_tools = False
        self.logger = logging.getLogger(f"nexus.{role.value}")

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt de sistema específico do agente."""
        ...

    @property
    def tools(self) -> list[dict]:
        """Ferramentas (functions) disponíveis para o agente. Override nas subclasses."""
        return []

    async def think(self, input_message: str, context: dict[str, Any] | None = None) -> str:
        """Processa uma entrada e retorna a resposta do agente."""
        from datetime import datetime
        now = datetime.now()
        weekday_names = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
        current_weekday = weekday_names[now.weekday()]

        data_integrity_prompt = f"""## DATA E CONTEXTO TEMPORAL
Hoje é {now.strftime('%d/%m/%Y')} ({current_weekday}), {now.strftime('%H:%M')}.
Quando o gestor mencionar datas relativas (ex: "para sexta", "esta semana", "amanhã"),
calcule os dias úteis restantes a partir de HOJE e use esse número na tool get_capacity_report.
Ex: se hoje é quarta e o prazo é sexta → 2 dias úteis (use days=2).

## REGRA CRÍTICA DE INTEGRIDADE DE DADOS

### Princípio fundamental
Você tem DUAS fontes de verdade: (1) dados retornados pelas ferramentas (tools) e
(2) dados do grafo de conhecimento (GraphRAG). AMBAS são confiáveis e complementares.
Se uma tool retorna um campo (ex: preço, localização), esse dado é REAL mesmo que o grafo
não o contenha. Sua função é ANALISAR e RECOMENDAR com base nesses dados, NUNCA inventar.
Diga "dado não disponível" APENAS quando NENHUMA das fontes forneceu aquele dado.

### O que você DEVE fazer
1. Citar valores EXATAMENTE como aparecem nos dados — sem arredondar, converter ou aproximar
2. Quando múltiplas entidades têm valores DIFERENTES, citar CADA valor individualmente
   (ex: se 3 fornecedores têm preços diferentes, mostrar o preço de CADA UM — nunca dizer
   "todos praticam o mesmo preço" se os valores são distintos)
3. Usar IDs e nomes EXATOS dos dados (fornecedores, materiais, equipamentos, etc.)
4. Manter a escala original dos dados (se rating é 0-5, usar 0-5 — nunca converter)
5. Diferenciar dados entre entidades — se cada fornecedor tem preço, lead time e rating
   próprios, listar os dados ESPECÍFICOS de cada um

### Nomenclatura de entidades
Ao citar equipamentos, materiais ou fornecedores, use SEMPRE o formato "Nome (ID)".
Exemplos: "Centro de Usinagem CNC XR-500 (CNC-03)", "Barra de Aço SAE 1045 (MP-001)",
"ElectroSul Componentes (FORN-003)". NUNCA use só o ID ou só parte do nome.

### O que você NUNCA deve fazer
1. Inventar valores numéricos que não existem nos dados
2. Generalizar dados individuais (ex: dizer "todos têm rating X" quando são diferentes)
3. Converter escalas (ex: rating 4.2/5.0 virar 8.4/10)
4. Arredondar valores (ex: 96.0% virar "quase 100%")
5. Preencher dados ausentes com estimativas
6. Criar métricas derivadas sem base nos dados originais
7. Listar campos como "dado não disponível" — simplesmente OMITA campos que não existem

### Regra de campos ausentes
Se um dado não está disponível, NÃO o mencione. Inclua APENAS campos que têm valor real.
NÃO escreva "dado não disponível", "não informado" ou similar — simplesmente não liste o campo.

### Formato ao apresentar comparações
Ao comparar entidades (fornecedores, materiais, equipamentos), liste APENAS os campos
que possuem dados reais:
- [Nome/ID]: [dado1], [dado2], [dado3] (somente campos com valor)"""

        messages = [{"role": "system", "content": self.system_prompt + "\n\n" + data_integrity_prompt}]

        # Adiciona contexto GraphRAG (grafo de conhecimento)
        if self.graph_retriever:
            try:
                graph_docs = await self.graph_retriever.retrieve(input_message)
                if graph_docs:
                    graph_context = "\n\n".join(
                        [f"[Grafo {i+1}]: {doc.page_content}" for i, doc in enumerate(graph_docs)]
                    )
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "## Conhecimento do Grafo (GraphRAG)\n"
                                "Os dados abaixo vêm do grafo de conhecimento (relações entre entidades). "
                                "Use-os como COMPLEMENTO, mas SEMPRE chame suas ferramentas (tools) para obter "
                                "dados detalhados (preços, confiabilidade, qualidade, localização, etc.) que o grafo "
                                "pode não conter. O grafo mostra CONEXÕES, as tools mostram DETALHES.\n\n"
                                f"{graph_context}"
                            ),
                        }
                    )
                    self.logger.debug(f"GraphRAG retornou {len(graph_docs)} contextos")
            except Exception as e:
                self.logger.warning(f"GraphRAG indisponível: {e}")

        # Adiciona contexto RAG vetorial se disponível
        if self.rag_retriever and context and context.get("use_rag", False):
            rag_query = context.get("rag_query", input_message)
            rag_docs = await self.rag_retriever.retrieve(rag_query)
            if rag_docs:
                rag_context = "\n\n".join(
                    [f"[Doc {i+1}]: {doc.page_content}" for i, doc in enumerate(rag_docs)]
                )
                messages.append(
                    {
                        "role": "system",
                        "content": f"## Base de Conhecimento (RAG Vetorial)\n{rag_context}",
                    }
                )

        # Adiciona contexto operacional
        if context:
            ctx_str = json.dumps(context, ensure_ascii=False, default=str)
            messages.append(
                {
                    "role": "system",
                    "content": f"## Contexto Operacional\n{ctx_str}",
                }
            )

        # Histórico de memória recente
        messages.extend(self.memory[-10:])

        # Mensagem do usuário/agente
        messages.append({"role": "user", "content": input_message})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if self.tools:
            # Verifica se o agente está em modo de forçar tools (ex: Coordinator na fase de delegação)
            force = getattr(self, "_force_tools", False)
            kwargs["tools"] = self.tools
            if self.role == AgentRole.COORDINATOR:
                kwargs["tool_choice"] = "required" if force else "auto"
            else:
                # Agentes especialistas sempre usam "required" para buscar dados reais
                kwargs["tool_choice"] = "required"

        response = await self.client.chat.completions.create(**kwargs)
        assistant_msg = response.choices[0].message

        # Processa tool calls se houver
        if assistant_msg.tool_calls:
            result = await self._handle_tool_calls(assistant_msg, messages)
        else:
            result = assistant_msg.content or ""

        # Salva na memória
        self.memory.append({"role": "user", "content": input_message})
        self.memory.append({"role": "assistant", "content": result})

        self.logger.info(f"[{self.name}] Processou: {input_message[:80]}...")
        return result

    async def _handle_tool_calls(self, assistant_msg, messages: list) -> str:
        """Processa chamadas de ferramentas do agente."""
        messages.append(assistant_msg.model_dump())

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            self.logger.info(f"[{self.name}] Tool call: {fn_name}({fn_args})")
            result = await self.execute_tool(fn_name, fn_args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

        follow_up = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
        )
        return follow_up.choices[0].message.content or ""

    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Executa uma ferramenta. Override nas subclasses."""
        return {"error": f"Tool '{tool_name}' não implementada"}

    async def process_message(self, message: AgentMessage) -> AgentMessage:
        """Processa uma mensagem de outro agente e retorna resposta."""
        self.message_history.append(message)

        context = message.context.copy()
        context["sender"] = message.sender.value
        context["message_type"] = message.message_type
        context["conversation_id"] = message.conversation_id

        response_content = await self.think(message.content, context)

        return AgentMessage(
            sender=self.role,
            receiver=message.sender,
            content=response_content,
            message_type="response",
            context={"original_request": message.content},
            conversation_id=message.conversation_id,
        )

    async def make_decision(
        self, problem: str, context: dict[str, Any] | None = None
    ) -> AgentDecision:
        """Toma uma decisão estruturada sobre um problema."""
        decision_prompt = f"""Analise o seguinte problema e tome uma decisão estruturada.

PROBLEMA: {problem}

Responda EXATAMENTE neste formato JSON:
{{
    "decision": "sua decisão clara e objetiva",
    "confidence": 0.85,
    "reasoning": "raciocínio detalhado",
    "actions": ["ação 1", "ação 2"],
    "risks": ["risco 1", "risco 2"],
    "data": {{}}
}}"""

        result = await self.think(decision_prompt, context)

        try:
            parsed = json.loads(result)
            return AgentDecision(agent=self.role, **parsed)
        except (json.JSONDecodeError, ValueError):
            return AgentDecision(
                agent=self.role,
                decision=result,
                confidence=0.5,
                reasoning="Resposta não estruturada do agente",
            )

    def reset_memory(self):
        """Limpa a memória de curto prazo do agente."""
        self.memory.clear()
        self.message_history.clear()
