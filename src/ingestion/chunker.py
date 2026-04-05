# src/ingestion/chunker.py
import re
from typing import List
from loguru import logger
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import settings


class DocumentChunker:

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )

    def _clean_text(self, text: str) -> str:
        """Clean up text before chunking — remove excessive whitespace."""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        if not documents:
            logger.warning("No documents passed to chunker.")
            return []

        # Clean text before splitting
        for doc in documents:
            doc.page_content = self._clean_text(doc.page_content)

        chunks = self.splitter.split_documents(documents)

        # Filter out very small chunks (likely noise)
        min_chunk_size = 50
        chunks = [c for c in chunks if len(c.page_content.strip()) >= min_chunk_size]

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["chunk_size"] = len(chunk.page_content)

        avg = sum(c.metadata["chunk_size"] for c in chunks) // len(chunks) if chunks else 0
        logger.success(f"Created {len(chunks)} chunks | avg size: {avg} chars")
        return chunks
