"""
NEXUS 4.0 - RAG Retriever
Sistema de Retrieval-Augmented Generation para consulta de normas,
procedimentos e base de conhecimento técnico.
"""

import logging
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger("nexus.rag")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "nexus_knowledge_base"


class RAGRetriever:
    """Retriever para consulta da base de conhecimento NEXUS."""

    def __init__(self, persist_directory: str | None = None):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        if persist_directory:
            self.vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            )
        else:
            import chromadb

            chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            self.vectorstore = Chroma(
                client=chroma_client,
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings,
            )

        self.retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10, "lambda_mult": 0.7},
        )
        logger.info("RAG Retriever inicializado")

    async def retrieve(self, query: str, k: int = 5):
        """Busca documentos relevantes na base de conhecimento."""
        logger.info(f"RAG query: {query[:80]}...")
        docs = await self.retriever.ainvoke(query)
        logger.info(f"RAG retornou {len(docs)} documentos")
        return docs[:k]

    async def retrieve_with_scores(self, query: str, k: int = 5):
        """Busca documentos com scores de similaridade."""
        results = await self.vectorstore.asimilarity_search_with_relevance_scores(
            query, k=k
        )
        return [(doc, score) for doc, score in results if score > 0.3]

    def get_collection_stats(self) -> dict:
        """Retorna estatísticas da coleção."""
        collection = self.vectorstore._collection
        return {
            "name": COLLECTION_NAME,
            "count": collection.count(),
        }
