# src/retrieval/vector_store.py
import hashlib
from typing import List, Optional
from loguru import logger
from langchain_core.documents import Document
from langchain_chroma import Chroma
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
        self._reranker = None

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

    def _hash_content(self, text: str) -> str:
        """Generate a hash ID from document content to detect duplicates."""
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def add_documents(self, chunks: List[Document]) -> int:
        """Add documents with duplicate detection. Returns number of new chunks added."""
        if not self.vector_store:
            self.create_or_load()
        if not chunks:
            logger.warning("No chunks to add.")
            return 0

        # Deduplicate: generate IDs from content hash, ChromaDB skips existing IDs
        new_chunks = []
        new_ids = []
        existing_ids = set()

        # Get all existing IDs from the collection
        collection = self.vector_store._collection
        if collection.count() > 0:
            result = collection.get()
            existing_ids = set(result["ids"])

        for chunk in chunks:
            chunk_id = self._hash_content(chunk.page_content)
            if chunk_id not in existing_ids and chunk_id not in new_ids:
                new_chunks.append(chunk)
                new_ids.append(chunk_id)

        skipped = len(chunks) - len(new_chunks)
        if skipped > 0:
            logger.info(f"Skipped {skipped} duplicate chunks")

        if not new_chunks:
            logger.info("All chunks already exist in the database.")
            return 0

        logger.info(f"Embedding and storing {len(new_chunks)} new chunks...")
        self.vector_store.add_documents(new_chunks, ids=new_ids)
        logger.success(f"Stored {len(new_chunks)} chunks in ChromaDB")
        return len(new_chunks)

    def rerank(self, query: str, docs: List[Document], top_k: int = 5) -> List[Document]:
        """Re-rank documents using a cross-encoder model for better relevance."""
        if not docs:
            return docs

        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading re-ranker: {settings.RERANKER_MODEL}")
            self._reranker = CrossEncoder(settings.RERANKER_MODEL)

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self._reranker.predict(pairs)

        scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        reranked = [doc for doc, score in scored_docs[:top_k]]
        logger.info(f"Re-ranked: top score={scored_docs[0][1]:.3f}, bottom={scored_docs[-1][1]:.3f}")
        return reranked

    def get_retriever(self, filter_dict: dict = None):
        if not self.vector_store:
            raise RuntimeError("Call create_or_load() before get_retriever().")

        search_kwargs = {"k": settings.RETRIEVAL_TOP_K}

        if settings.RETRIEVAL_STRATEGY == "mmr":
            search_kwargs["fetch_k"] = settings.RETRIEVAL_TOP_K * 3
            search_kwargs["lambda_mult"] = 0.7
            search_type = "mmr"
        else:
            search_type = "similarity"

        if filter_dict:
            search_kwargs["filter"] = filter_dict

        return self.vector_store.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs,
        )

    def similarity_search(self, query: str, k: int = None) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k or settings.RETRIEVAL_TOP_K)

    def get_collection_stats(self) -> dict:
        count = self.vector_store._collection.count() if self.vector_store else 0
        return {"total_chunks": count, "collection": settings.COLLECTION_NAME}

    def clear_collection(self) -> int:
        """Delete all documents from the collection. Returns number of chunks deleted."""
        if not self.vector_store:
            return 0
        count = self.vector_store._collection.count()
        if count == 0:
            return 0
        # Get all IDs and delete them
        all_ids = self.vector_store._collection.get()["ids"]
        self.vector_store._collection.delete(ids=all_ids)
        logger.success(f"Cleared {count} chunks from collection")
        return count

    def delete_by_source(self, source_name: str) -> int:
        """Delete all chunks from a specific source. Returns number deleted."""
        if not self.vector_store or self.vector_store._collection.count() == 0:
            return 0
        result = self.vector_store._collection.get()
        ids_to_delete = []
        for doc_id, meta in zip(result["ids"], result["metadatas"]):
            name = meta.get("file_name") or meta.get("url") or ""
            if name == source_name:
                ids_to_delete.append(doc_id)
        if ids_to_delete:
            self.vector_store._collection.delete(ids=ids_to_delete)
            logger.success(f"Deleted {len(ids_to_delete)} chunks from source: {source_name}")
        return len(ids_to_delete)

    def get_source_list(self) -> List[str]:
        """Get list of unique source file names/URLs in the collection."""
        if not self.vector_store or self.vector_store._collection.count() == 0:
            return []
        result = self.vector_store._collection.get()
        sources = set()
        for meta in result["metadatas"]:
            name = meta.get("file_name") or meta.get("url") or "unknown"
            sources.add(name)
        return sorted(sources)
