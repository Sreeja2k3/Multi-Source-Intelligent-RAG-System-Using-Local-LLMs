# src/ingestion/chunker.py
from typing import List
from loguru import logger
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
# NOTE: In langchain v0.2+, text splitters moved to langchain-text-splitters package.
# It is installed automatically as a dependency of langchain — no extra install needed.
# Old import was: from langchain.text_splitter import ...  ← this will raise ImportError
# Correct import:  from langchain_text_splitters import ... ← use this

from src.config import settings


class DocumentChunker:

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        if not documents:
            logger.warning("No documents passed to chunker.")
            return []

        chunks = self.splitter.split_documents(documents)

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["chunk_size"] = len(chunk.page_content)

        avg = sum(c.metadata["chunk_size"] for c in chunks) // len(chunks) if chunks else 0
        logger.success(f"Created {len(chunks)} chunks | avg size: {avg} chars")
        return chunks
