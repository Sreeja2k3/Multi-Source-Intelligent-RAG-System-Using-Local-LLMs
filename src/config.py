# src/config.py
from pydantic_settings import BaseSettings  # requires: pip install pydantic-settings
from typing import Literal


class Settings(BaseSettings):
    # LLM — runs locally via Ollama (ollama.com)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.2"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024

    # Embeddings — downloads ~80MB model on first run
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # Vector store
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    COLLECTION_NAME: str = "rag_collection"

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_STRATEGY: Literal["mmr", "similarity"] = "mmr"

    # Re-ranking
    USE_RERANKER: bool = True
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Conversation memory
    MEMORY_WINDOW: int = 6  # number of past messages to include

    # Evaluation
    JUDGE_MODEL: str = "llama3.2"  # change to a different model for independent judging

    model_config = {"env_file": ".env"}
    # NOTE: In pydantic-settings v2, use model_config dict, NOT inner class Config.
    # The old `class Config: env_file = ".env"` pattern causes a warning in v2.


settings = Settings()
