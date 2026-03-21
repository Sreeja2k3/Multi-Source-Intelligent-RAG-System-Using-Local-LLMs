# src/ingestion/pipeline.py
from src.ingestion.loader import MultiSourceLoader
from src.ingestion.chunker import DocumentChunker
from src.retrieval.vector_store import VectorStoreManager


class IngestionPipeline:

    def __init__(self, vector_store_manager: VectorStoreManager):
        self.loader = MultiSourceLoader()
        self.chunker = DocumentChunker()
        self.vs = vector_store_manager

    def _run(self, docs) -> int:
        chunks = self.chunker.chunk_documents(docs)
        self.vs.add_documents(chunks)
        return len(chunks)

    def ingest_pdf(self, path: str) -> int:
        return self._run(self.loader.load_pdf(path))

    def ingest_docx(self, path: str) -> int:
        return self._run(self.loader.load_docx(path))

    def ingest_txt(self, path: str) -> int:
        return self._run(self.loader.load_txt(path))

    def ingest_url(self, url: str) -> int:
        return self._run(self.loader.load_url(url))

    def ingest_youtube(self, url: str) -> int:
        return self._run(self.loader.load_youtube(url))

    def ingest_directory(self, directory: str) -> int:
        return self._run(self.loader.load_from_directory(directory))
