# main.py — CLI for testing without the UI
# Usage examples:
#   python main.py ingest --pdf ./myfile.pdf
#   python main.py ingest --url https://en.wikipedia.org/wiki/Python_(programming_language)
#   python main.py ingest --csv ./data.csv
#   python main.py ingest --json ./data.json
#   python main.py query "What is Python used for?"
#   python main.py stats

import argparse
from src.retrieval.vector_store import VectorStoreManager
from src.ingestion.pipeline import IngestionPipeline
from src.generation.rag_chain import RAGChain


def main():
    parser = argparse.ArgumentParser(description="RAG System CLI")
    sub = parser.add_subparsers(dest="cmd")

    ing = sub.add_parser("ingest")
    ing.add_argument("--pdf")
    ing.add_argument("--docx")
    ing.add_argument("--txt")
    ing.add_argument("--csv")
    ing.add_argument("--json")
    ing.add_argument("--url")
    ing.add_argument("--youtube")
    ing.add_argument("--dir")

    qry = sub.add_parser("query")
    qry.add_argument("question")

    sub.add_parser("stats")

    args = parser.parse_args()

    vs = VectorStoreManager().create_or_load()
    pipeline = IngestionPipeline(vs)

    if args.cmd == "ingest":
        if args.pdf:       print(f"Indexed {pipeline.ingest_pdf(args.pdf)} chunks")
        elif args.docx:    print(f"Indexed {pipeline.ingest_docx(args.docx)} chunks")
        elif args.txt:     print(f"Indexed {pipeline.ingest_txt(args.txt)} chunks")
        elif args.csv:     print(f"Indexed {pipeline.ingest_csv(args.csv)} chunks")
        elif args.json:    print(f"Indexed {pipeline.ingest_json(args.json)} chunks")
        elif args.url:     print(f"Indexed {pipeline.ingest_url(args.url)} chunks")
        elif args.youtube: print(f"Indexed {pipeline.ingest_youtube(args.youtube)} chunks")
        elif args.dir:     print(f"Indexed {pipeline.ingest_directory(args.dir)} chunks")
        else:              print("Specify a source: --pdf, --url, --youtube, --csv, --json, etc.")

    elif args.cmd == "query":
        rag = RAGChain(vs)
        result = rag.query(args.question)
        print(f"\nANSWER:\n{result['answer']}")
        print(f"\nSources used: {result['num_sources']}")
        for i, doc in enumerate(result["sources"], 1):
            meta = doc.metadata
            print(f"  [{i}] {meta.get('source_type')} — {meta.get('file_name', meta.get('url', ''))}")

    elif args.cmd == "stats":
        s = vs.get_collection_stats()
        print(f"Collection: {s['collection']}")
        print(f"Total chunks: {s['total_chunks']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
