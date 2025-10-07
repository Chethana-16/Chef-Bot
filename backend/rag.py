from pathlib import Path
from typing import List, Tuple
import faiss
import json
import re

from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

# Paths
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
INDEX_DIR = DATA_DIR / "index"
KNOWLEDGE_DIR = ROOT / "knowledge"

EMB_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # small, fast, local

def read_texts_from_knowledge() -> List[Tuple[str, str]]:
    """Return list of (doc_id, text) from .md/.txt/.pdf in knowledge/."""
    docs = []
    for p in KNOWLEDGE_DIR.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in [".md", ".txt"]:
                docs.append((p.name, p.read_text(encoding="utf-8", errors="ignore")))
            elif p.suffix.lower() == ".pdf":
                text = []
                try:
                    reader = PdfReader(str(p))
                    for page in reader.pages:
                        text.append(page.extract_text() or "")
                except Exception:
                    pass
                if text:
                    docs.append((p.name, "\n".join(text)))
    return docs

def chunk(text: str, max_tokens: int = 350) -> List[str]:
    """Naive chunker by sentences; ~350 tokens ≈ short paragraphs."""
    # quick normalization
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[\.\!\?])\s", text)
    chunks, cur = [], ""
    for s in sents:
        if len((cur + " " + s).split()) > max_tokens:
            if cur:
                chunks.append(cur.strip())
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur.strip())
    return [c for c in chunks if len(c.split()) > 5]

class RAGIndex:
    def __init__(self):
        self.model = SentenceTransformer(EMB_MODEL_NAME)
        self.index = None
        self.chunks = []
        self.ids = []

    def build(self):
        docs = read_texts_from_knowledge()
        all_chunks = []
        for doc_id, text in docs:
            for i, c in enumerate(chunk(text)):
                all_chunks.append((f"{doc_id}#{i}", c))
        if not all_chunks:
            self.index = None
            self.chunks, self.ids = [], []
            return

        texts = [c for _, c in all_chunks]
        emb = self.model.encode(texts, normalize_embeddings=True)
        dim = emb.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(emb)
        self.chunks = texts
        self.ids = [i for i, _ in all_chunks]

        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(INDEX_DIR / "index.faiss"))
        (INDEX_DIR / "chunks.json").write_text(json.dumps(self.chunks), encoding="utf-8")
        (INDEX_DIR / "ids.json").write_text(json.dumps(self.ids), encoding="utf-8")

    def load(self):
        path = INDEX_DIR / "index.faiss"
        if not path.exists():
            self.build()
            return
        self.index = faiss.read_index(str(path))
        self.chunks = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
        self.ids = json.loads((INDEX_DIR / "ids.json").read_text(encoding="utf-8"))

    def search(self, query: str, k: int = 5) -> List[str]:
        if self.index is None:
            return []
        q = self.model.encode([query], normalize_embeddings=True)
        D, I = self.index.search(q, k)
        out = []
        for idx in I[0]:
            if 0 <= idx < len(self.chunks):
                out.append(self.chunks[idx])
        return out

RAG = RAGIndex()
