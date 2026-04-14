"""
NEXUS 4.0 - WhatsApp Handler
Integração com Meta WhatsApp Cloud API.
"""

import logging
import os

import httpx

logger = logging.getLogger("nexus.whatsapp")

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


class WhatsAppHandler:
    """Gerencia comunicação via Meta WhatsApp Cloud API."""

    def __init__(self):
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "nexus40")

        if not self.access_token or not self.phone_number_id:
            raise ValueError("WHATSAPP_ACCESS_TOKEN e WHATSAPP_PHONE_NUMBER_ID são obrigatórios")

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def verify_webhook(self, mode: str, token: str, challenge: str) -> str | None:
        """Verifica o webhook do Meta (GET request)."""
        if mode == "subscribe" and token == self.verify_token:
            logger.info("Webhook verificado com sucesso")
            return challenge
        logger.warning(f"Verificação de webhook falhou: mode={mode}")
        return None

    def parse_incoming(self, payload: dict) -> dict | None:
        """Extrai mensagem de texto do payload do webhook Meta."""
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            message = messages[0]

            # Só processa mensagens de texto
            if message.get("type") != "text":
                return None

            phone = message.get("from", "")
            text = message.get("text", {}).get("body", "")

            if not text:
                return None

            logger.info(f"WhatsApp recebido de {phone}: {text[:50]}...")
            return {"phone": phone, "text": text, "raw": payload}

        except Exception as e:
            logger.error(f"Erro ao parsear webhook: {e}")
            return None

    async def send_message(self, phone: str, text: str):
        """Envia mensagem de texto via WhatsApp Cloud API."""
        # WhatsApp tem limite de 4096 caracteres por mensagem
        if len(text) > 4000:
            chunks = self._split_message(text, 4000)
            for chunk in chunks:
                await self._send_single(phone, chunk)
        else:
            await self._send_single(phone, text)

    async def _send_single(self, phone: str, text: str):
        """Envia uma única mensagem."""
        url = f"{GRAPH_API_URL}/{self.phone_number_id}/messages"

        # Formata texto para WhatsApp (remove markdown que não funciona)
        text = self._format_for_whatsapp(text)

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"WhatsApp enviado para {phone}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao enviar WhatsApp: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.ConnectError:
            logger.warning("Meta Graph API não acessível")

    def _format_for_whatsapp(self, text: str) -> str:
        """Converte markdown para formato WhatsApp-friendly."""
        import re

        lines = text.split("\n")
        result = []
        in_table = False
        headers = []

        for line in lines:
            stripped = line.strip()

            # Detecta tabela markdown
            if "|" in stripped and stripped.startswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue  # Pula separador

                cells = [c.strip() for c in stripped.split("|")[1:-1]]

                if not in_table:
                    headers = cells
                    in_table = True
                    table_row_num = 0
                else:
                    table_row_num += 1
                    # Primeira coluna como título do bloco
                    title = cells[0] if cells else ""
                    result.append(f"*{table_row_num}. {title}*")
                    # Demais colunas como linhas indentadas
                    for h, c in zip(headers[1:], cells[1:]):
                        if c and c.strip():
                            result.append(f"   {h}: {c}")
                    result.append("")  # Linha em branco entre blocos
            else:
                if in_table:
                    in_table = False
                    result.append("")

                # Headers markdown → *bold* no WhatsApp
                # #### Título → *Título*
                # ### Título → *Título*
                # ## Título → *Título*
                match = re.match(r"^#{1,6}\s+(.*)", stripped)
                if match:
                    stripped = f"*{match.group(1)}*"

                # **bold** → *bold* (WhatsApp usa asterisco simples)
                stripped = re.sub(r"\*\*(.*?)\*\*", r"*\1*", stripped)

                # Remove --- (linhas separadoras)
                if re.match(r"^-{3,}$", stripped):
                    continue

                result.append(stripped)

        # Remove linhas em branco consecutivas
        cleaned = []
        prev_empty = False
        for line in result:
            if line.strip() == "":
                if not prev_empty:
                    cleaned.append("")
                prev_empty = True
            else:
                cleaned.append(line)
                prev_empty = False

        return "\n".join(cleaned).strip()

    def _split_message(self, text: str, max_length: int) -> list[str]:
        """Divide mensagem longa em chunks respeitando parágrafos."""
        chunks = []
        current = ""

        for paragraph in text.split("\n\n"):
            if len(current) + len(paragraph) + 2 <= max_length:
                current += ("" if not current else "\n\n") + paragraph
            else:
                if current:
                    chunks.append(current)
                current = paragraph

        if current:
            chunks.append(current)

        return chunks
