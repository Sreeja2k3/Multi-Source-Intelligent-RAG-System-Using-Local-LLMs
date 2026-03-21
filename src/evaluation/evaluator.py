# src/evaluation/evaluator.py
#
# WHAT IS RAGAS?
# RAGAS (Retrieval Augmented Generation Assessment) is a framework
# that automatically scores your RAG system's answer quality.
#
# WHY THIS MATTERS FOR YOUR RESUME:
# Most RAG projects just "work" — they return answers.
# This project MEASURES how good those answers are.
# That's the difference between a junior project and a serious one.
#
# METRICS THIS MEASURES:
# 1. Faithfulness — does the answer stick to the retrieved context?
#    (detects hallucination)
# 2. Answer relevance — does the answer actually address the question?
# 3. Context relevance — were the right chunks retrieved?
#
# Interview Q: "How do you know your RAG system works well?"
# Answer: "I built an evaluation pipeline using RAGAS that measures
# faithfulness, answer relevance, and context relevance automatically."

import json
from datetime import datetime
from typing import List
from loguru import logger
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import settings
from src.retrieval.vector_store import VectorStoreManager
from src.generation.rag_chain import RAGChain, format_context


# ── Test questions for the research papers ───────────────────────────────────
# These are questions where we KNOW the papers contain the answer.
# Good evaluation needs questions with known answers.

TEST_QUESTIONS = [
    {
        "question": "What is the attention mechanism in the Transformer?",
        "expected_topic": "attention",
    },
    {
        "question": "What does RAG stand for and what problem does it solve?",
        "expected_topic": "retrieval augmented generation",
    },
    {
        "question": "What is BERT and what tasks was it designed for?",
        "expected_topic": "bert pre-training",
    },
    {
        "question": "How does scaled dot-product attention work?",
        "expected_topic": "dot product attention softmax",
    },
    {
        "question": "What is the difference between seq2seq models and RAG?",
        "expected_topic": "sequence to sequence retrieval",
    },
]


class RAGEvaluator:
    """
    Evaluates RAG system quality using LLM-as-judge approach.

    Since we're running locally without the full RAGAS library
    (which requires OpenAI API), we implement the same metrics
    using our local Ollama LLM as the judge.

    This is actually a valid approach used in production systems —
    "LLM-as-judge" is a well-established evaluation technique.
    Interview Q: "What is LLM-as-judge?" → Using an LLM to score
    another LLM's output on defined criteria.
    """

    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vs = vector_store_manager
        self.rag = RAGChain(vector_store_manager)
        self.judge_llm = ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,  # zero temperature for consistent scoring
            num_predict=200,
        )

    def score_faithfulness(self, answer: str, context: str) -> float:
        """
        Faithfulness: Does the answer only use information from the context?
        Score 0.0 to 1.0.
        1.0 = answer is fully supported by context (no hallucination)
        0.0 = answer contains claims not in the context
        """
        prompt = f"""You are an evaluator. Score whether the ANSWER is faithful to the CONTEXT.
Faithful means every claim in the answer can be found in the context.

CONTEXT:
{context[:1500]}

ANSWER:
{answer}

Respond with ONLY a number between 0.0 and 1.0.
1.0 = completely faithful, every claim is in the context
0.5 = partially faithful, some claims are in the context
0.0 = not faithful, answer contains claims not in the context

Score:"""

        response = self.judge_llm.invoke([HumanMessage(content=prompt)])
        try:
            score = float(response.content.strip().split()[0])
            return min(max(score, 0.0), 1.0)
        except:
            return 0.5

    def score_answer_relevance(self, question: str, answer: str) -> float:
        """
        Answer Relevance: Does the answer actually address the question?
        Score 0.0 to 1.0.
        """
        prompt = f"""You are an evaluator. Score whether the ANSWER addresses the QUESTION.

QUESTION: {question}

ANSWER: {answer}

Respond with ONLY a number between 0.0 and 1.0.
1.0 = answer directly and completely addresses the question
0.5 = answer partially addresses the question
0.0 = answer does not address the question at all

Score:"""

        response = self.judge_llm.invoke([HumanMessage(content=prompt)])
        try:
            score = float(response.content.strip().split()[0])
            return min(max(score, 0.0), 1.0)
        except:
            return 0.5

    def score_context_relevance(self, question: str, context: str) -> float:
        """
        Context Relevance: Were the right chunks retrieved for this question?
        Score 0.0 to 1.0.
        """
        prompt = f"""You are an evaluator. Score whether the CONTEXT contains information relevant to answering the QUESTION.

QUESTION: {question}

CONTEXT:
{context[:1500]}

Respond with ONLY a number between 0.0 and 1.0.
1.0 = context is highly relevant and contains the answer
0.5 = context is somewhat relevant
0.0 = context is not relevant to the question

Score:"""

        response = self.judge_llm.invoke([HumanMessage(content=prompt)])
        try:
            score = float(response.content.strip().split()[0])
            return min(max(score, 0.0), 1.0)
        except:
            return 0.5

    def evaluate_single(self, question: str) -> dict:
        """Run all 3 metrics on a single question."""
        logger.info(f"Evaluating: {question}")

        result = self.rag.query(question)
        answer = result["answer"]
        context = format_context(result["sources"])

        faithfulness = self.score_faithfulness(answer, context)
        answer_relevance = self.score_answer_relevance(question, answer)
        context_relevance = self.score_context_relevance(question, context)

        overall = round((faithfulness + answer_relevance + context_relevance) / 3, 3)

        return {
            "question": question,
            "answer": answer,
            "faithfulness": round(faithfulness, 3),
            "answer_relevance": round(answer_relevance, 3),
            "context_relevance": round(context_relevance, 3),
            "overall_score": overall,
            "num_sources": result["num_sources"],
        }

    def evaluate_all(self, questions: List[dict] = None) -> dict:
        """Run full evaluation suite and save results to JSON."""
        questions = questions or TEST_QUESTIONS
        results = []

        logger.info(f"Running evaluation on {len(questions)} questions...")

        for i, q in enumerate(questions, 1):
            logger.info(f"Question {i}/{len(questions)}")
            result = self.evaluate_single(q["question"])
            results.append(result)
            logger.success(f"Overall score: {result['overall_score']}")

        # Calculate averages
        avg_faithfulness = round(sum(r["faithfulness"] for r in results) / len(results), 3)
        avg_relevance = round(sum(r["answer_relevance"] for r in results) / len(results), 3)
        avg_context = round(sum(r["context_relevance"] for r in results) / len(results), 3)
        avg_overall = round(sum(r["overall_score"] for r in results) / len(results), 3)

        report = {
            "timestamp": datetime.now().isoformat(),
            "model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "retrieval_strategy": settings.RETRIEVAL_STRATEGY,
            "summary": {
                "avg_faithfulness": avg_faithfulness,
                "avg_answer_relevance": avg_relevance,
                "avg_context_relevance": avg_context,
                "avg_overall": avg_overall,
                "total_questions": len(results),
            },
            "results": results,
        }

        # Save to file
        output_path = "evaluation_report.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.success(f"Evaluation complete. Report saved to {output_path}")
        self._print_summary(report)
        return report

    def _print_summary(self, report: dict):
        s = report["summary"]
        print("\n" + "="*50)
        print("EVALUATION REPORT")
        print("="*50)
        print(f"Model:               {report['model']}")
        print(f"Questions tested:    {s['total_questions']}")
        print(f"Faithfulness:        {s['avg_faithfulness']} / 1.0")
        print(f"Answer relevance:    {s['avg_answer_relevance']} / 1.0")
        print(f"Context relevance:   {s['avg_context_relevance']} / 1.0")
        print(f"Overall score:       {s['avg_overall']} / 1.0")
        print("="*50)
        print(f"Full report: evaluation_report.json")
