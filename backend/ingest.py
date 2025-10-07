from rag import RAG, KNOWLEDGE_DIR

if __name__ == "__main__":
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building index from {KNOWLEDGE_DIR.resolve()} ...")
    RAG.build()
    print("Done. Index ready.")
