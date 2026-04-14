"""
NEXUS 4.0 - RAG Ingest
Script para ingestão de documentos na base de conhecimento.
Suporta PDF, TXT, Markdown e DOCX.
"""

import logging
import os
import sys
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_openai import OpenAIEmbeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("nexus.ingest")

COLLECTION_NAME = "nexus_knowledge_base"
KNOWLEDGE_BASE_DIR = Path(__file__).parent / "knowledge_base"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))


def load_documents(directory: Path):
    """Carrega documentos de um diretório."""
    docs = []

    # PDFs
    pdf_loader = DirectoryLoader(
        str(directory), glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True
    )
    try:
        pdf_docs = pdf_loader.load()
        logger.info(f"Carregados {len(pdf_docs)} páginas de PDFs")
        docs.extend(pdf_docs)
    except Exception as e:
        logger.warning(f"Erro ao carregar PDFs: {e}")

    # Markdown
    md_loader = DirectoryLoader(
        str(directory),
        glob="**/*.md",
        loader_cls=UnstructuredMarkdownLoader,
        show_progress=True,
    )
    try:
        md_docs = md_loader.load()
        logger.info(f"Carregados {len(md_docs)} documentos Markdown")
        docs.extend(md_docs)
    except Exception as e:
        logger.warning(f"Erro ao carregar Markdown: {e}")

    # Texto
    txt_loader = DirectoryLoader(
        str(directory), glob="**/*.txt", loader_cls=TextLoader, show_progress=True
    )
    try:
        txt_docs = txt_loader.load()
        logger.info(f"Carregados {len(txt_docs)} arquivos de texto")
        docs.extend(txt_docs)
    except Exception as e:
        logger.warning(f"Erro ao carregar TXT: {e}")

    return docs


def split_documents(docs, chunk_size=1000, chunk_overlap=200):
    """Divide documentos em chunks para embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Documentos divididos em {len(chunks)} chunks")
    return chunks


def ingest(directory: Path | None = None, persist_local: str | None = None):
    """Pipeline completo de ingestão."""
    directory = directory or KNOWLEDGE_BASE_DIR

    if not directory.exists():
        logger.error(f"Diretório não encontrado: {directory}")
        sys.exit(1)

    logger.info(f"Iniciando ingestão de: {directory}")

    # Carrega e processa
    docs = load_documents(directory)
    if not docs:
        logger.warning("Nenhum documento encontrado. Criando base com dados de exemplo...")
        docs = _create_sample_knowledge_base()

    chunks = split_documents(docs)

    # Cria embeddings e persiste
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    if persist_local:
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            persist_directory=persist_local,
        )
    else:
        import chromadb

        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            client=client,
            collection_name=COLLECTION_NAME,
        )

    count = vectorstore._collection.count()
    logger.info(f"Ingestão concluída! {count} chunks indexados na coleção '{COLLECTION_NAME}'")
    return count


def _create_sample_knowledge_base():
    """Cria documentos de exemplo para demonstração."""
    from langchain_core.documents import Document

    sample_docs = [
        Document(
            page_content="""# Procedimento de Controle de Qualidade - PQ-001
## Inspeção de Recebimento de Matéria-Prima

### Objetivo
Estabelecer critérios para inspeção de matéria-prima recebida.

### Aplicação
Todas as matérias-primas críticas (Classe A e B).

### Procedimento
1. Verificar documentação do fornecedor (certificado de qualidade, nota fiscal)
2. Inspeção visual: verificar embalagem, identificação e condições de transporte
3. Amostragem conforme NBR 5426 (NQA 1.0 para itens críticos)
4. Ensaios dimensionais conforme desenho técnico
5. Ensaios de dureza (quando aplicável)
6. Registrar resultados no sistema de qualidade

### Critérios de Aceitação
- Dimensional: tolerância conforme desenho técnico
- Dureza: 58-62 HRC para aço SAE 1045 temperado
- Visual: ausência de trincas, corrosão ou deformações

### Não-Conformidade
Em caso de reprovação, segregar material e abrir NCR.""",
            metadata={"source": "PQ-001", "type": "procedimento", "area": "qualidade"},
        ),
        Document(
            page_content="""# Manual de Manutenção Preventiva - CNC-03
## Centro de Usinagem CNC Modelo XR-500

### Plano de Manutenção Preventiva

#### Diária (Operador)
- Verificar nível de óleo lubrificante
- Limpar área de trabalho e cavacos
- Verificar pressão do ar comprimido (mín. 6 bar)
- Verificar funcionamento do sistema de refrigeração

#### Semanal (Manutenção)
- Verificar tensão das correias
- Inspecionar guias lineares e fusos de esferas
- Verificar alinhamento do spindle
- Testar sistema de segurança (portas, cortinas de luz)

#### Mensal (Manutenção Especializada)
- Análise de vibração do spindle (limite: 8.0 mm/s)
- Verificação de temperatura dos rolamentos (limite: 75°C)
- Calibração do sistema de medição
- Troca de filtros (óleo, ar, refrigerante)

#### Semestral (Parada Programada)
- Troca de rolamentos do spindle (vida útil: 8000h)
- Revisão completa do sistema hidráulico
- Calibração geométrica da máquina
- Atualização de software CNC

### Indicadores
- MTBF alvo: > 500 horas
- MTTR alvo: < 4 horas
- Disponibilidade alvo: > 95%""",
            metadata={"source": "MM-CNC-03", "type": "manual_manutencao", "area": "manutencao"},
        ),
        Document(
            page_content="""# Política de Gestão de Fornecedores - PGF-001

## Classificação de Fornecedores
- Classe A (Crítico): Fornecedores de matéria-prima essencial, sem alternativa imediata
- Classe B (Importante): Fornecedores com alternativas, mas com custo de troca
- Classe C (Regular): Fornecedores facilmente substituíveis

## Critérios de Avaliação (Peso)
1. Qualidade (30%): PPM, certificações, auditorias
2. Entrega (25%): OTIF, lead time, flexibilidade
3. Custo (20%): Competitividade, estabilidade de preços
4. Gestão (15%): Comunicação, capacidade técnica
5. Sustentabilidade (10%): Práticas ESG, certificações ambientais

## Lead Times Padrão por Material
- Aço SAE 1045: 5-7 dias úteis (fornecedor local)
- Componentes Eletrônicos: 7-14 dias úteis (nacional) / 21-45 dias (importado)
- Embalagens: 3-5 dias úteis
- Químicos e Óleos: 2-3 dias úteis

## Estoque de Segurança
- Classe A: 15 dias de consumo
- Classe B: 10 dias de consumo
- Classe C: 5 dias de consumo

## Contingência
Manter pelo menos 2 fornecedores homologados para itens Classe A.
Em caso de ruptura, acionar fornecedor alternativo com pedido emergencial (custo +60%).""",
            metadata={"source": "PGF-001", "type": "politica", "area": "supply_chain"},
        ),
        Document(
            page_content="""# Especificação Técnica - Eixo de Transmissão ET-500 (PROD-001)

## Descrição
Eixo de transmissão em aço SAE 1045 temperado e retificado para aplicações automotivas.
Utilizado em sistemas de transmissão de torque em veículos comerciais e industriais.

## Bill of Materials (BOM)
| Item | Material | Qtd/Unidade | Unidade |
|------|----------|-------------|---------|
| 1 | Barra de Aço SAE 1045 (MP-001) | 2.5 | kg |
| 2 | Sensor de Posição Angular (MP-002) | 1 | pç |
| 3 | Parafuso M8x30 Cl. 10.9 (MP-009) | 4 | pç |
| 4 | Embalagem Protetiva VCI (MP-003) | 1 | pç |

## Processo de Fabricação
1. Corte de barra (Serra CNC SC-300) - 3 min
2. Torneamento e usinagem (CNC-03 XR-500) - 15 min
3. Tratamento térmico (têmpera e revenimento) - 45 min (lote)
4. Retífica cilíndrica (RC-100) - 8 min
5. Montagem sensor de posição - 5 min
6. Inspeção final dimensional e dureza - 3 min
7. Embalagem protetiva - 2 min

## Tempo de Ciclo Total: 42 min/unidade (considerando lote de 100)
## Capacidade: ~34 unidades/hora na CNC-03

## Requisitos de Qualidade
- Tolerância dimensional: ±0.02mm
- Rugosidade superficial: Ra 0.8 μm
- Dureza: 58-62 HRC (após têmpera)
- Batimento radial: máx. 0.01mm
- Normas: ISO 9001:2015, IATF 16949:2016""",
            metadata={"source": "ET-PROD-001", "type": "especificacao", "area": "engenharia"},
        ),
    ]
    return sample_docs


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NEXUS 4.0 - Ingestão de Documentos")
    parser.add_argument("--dir", type=str, help="Diretório com documentos")
    parser.add_argument("--local", type=str, help="Persistir localmente (path)")
    args = parser.parse_args()

    directory = Path(args.dir) if args.dir else None
    ingest(directory=directory, persist_local=args.local)
