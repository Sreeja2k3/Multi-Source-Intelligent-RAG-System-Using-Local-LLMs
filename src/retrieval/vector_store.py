# src/retrieval/vector_store.py
from typing import List, Optional
from loguru import logger
from langchain_core.documents import Document

# IMPORTANT: Do NOT import from langchain_community.vectorstores.Chroma anymore.
# That class is deprecated. Use langchain-chroma package instead:
from langchain_chroma import Chroma

# langchain-huggingface is a separate package (langchain_huggingface).
# Do NOT use langchain_community.embeddings.HuggingFaceEmbeddings — deprecated.
from langchain_huggingface import HuggingFaceEmbeddings

from src.config import settings


class VectorStoreManager:

    def __init__(self):
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.vector_store: Optional[Chroma] = None

    def create_or_load(self) -> "VectorStoreManager":
        logger.info(f"Initializing ChromaDB at: {settings.CHROMA_PERSIST_DIR}")
        self.vector_store = Chroma(
            collection_name=settings.COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
        count = self.vector_store._collection.count()
        logger.success(f"ChromaDB ready — {count} chunks indexed")
        return self

    def add_documents(self, chunks: List[Document]) -> None:
        if not self.vector_store:
            self.create_or_load()
        if not chunks:
            logger.warning("No chunks to add.")
            return
        logger.info(f"Embedding and storing {len(chunks)} chunks...")
        self.vector_store.add_documents(chunks)
        logger.success(f"Stored {len(chunks)} chunks in ChromaDB")

    def get_retriever(self):
        if not self.vector_store:
            raise RuntimeError("Call create_or_load() before get_retriever().")

        if settings.RETRIEVAL_STRATEGY == "mmr":
            return self.vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": settings.RETRIEVAL_TOP_K,
                    "fetch_k": settings.RETRIEVAL_TOP_K * 3,
                    "lambda_mult": 0.7,
                },
            )
        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.RETRIEVAL_TOP_K},
        )

    def similarity_search(self, query: str, k: int = None) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k or settings.RETRIEVAL_TOP_K)

    def get_collection_stats(self) -> dict:
        count = self.vector_store._collection.count() if self.vector_store else 0
        return {"total_chunks": count, "collection": settings.COLLECTION_NAME}
