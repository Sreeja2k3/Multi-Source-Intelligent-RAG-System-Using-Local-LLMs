# evaluate.py — Run this to score your RAG system
# Usage: python evaluate.py
#
# This runs 5 test questions through your RAG system and scores:
# - Faithfulness (does the answer stick to the retrieved context?)
# - Answer relevance (does the answer address the question?)
# - Context relevance (were the right chunks retrieved?)
#
# Results are saved to evaluation_report.json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.vector_store import VectorStoreManager
from src.evaluation.evaluator import RAGEvaluator
from loguru import logger

if __name__ == "__main__":
    logger.info("Initializing RAG system for evaluation...")
    vs = VectorStoreManager().create_or_load()

    stats = vs.get_collection_stats()
    if stats["total_chunks"] == 0:
        print("ERROR: No documents indexed. Run ingest first.")
        print("Example: python main.py ingest --pdf papers/2005.11401v4.pdf")
        sys.exit(1)

    print(f"Evaluating against {stats['total_chunks']} indexed chunks...")
    print("This will take 3-5 minutes. Each question runs through the full RAG pipeline.\n")

    evaluator = RAGEvaluator(vs)
    report = evaluator.evaluate_all()
