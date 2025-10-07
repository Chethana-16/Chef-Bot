import json
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

from rag import RAG, DATA_DIR

# === Config ===
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

THREADS_DIR = DATA_DIR / "threads"
THREADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Chef CTS Backend")

# CORS: allow your static site (file:// during dev, or GitHub Pages later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load / build RAG index once
RAG.load()

CHEF_SYSTEM = """You are Chef CTS — a playful, precise, safety-first cooking coach.
Keep replies concise and structured with clear steps and bullet points.
Always:
- Offer both US + metric measures when helpful.
- Give doneness temps and timing ranges (and remind about food safety).
- Suggest 1–2 smart substitutions with a short why-it-works.
- When users list ingredients, suggest 1–2 recipe ideas and a 20–40 min plan.
- For disasters: cause → fastest fix → prevention tip.
If context (RAG) provided, prefer it for factual details and short history notes. If a fact isn't in context, say so.
Avoid medical advice. Be friendly and encouraging :)
"""

def load_thread(thread_id: str) -> List[Dict[str, str]]:
    p = THREADS_DIR / f"{thread_id}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_thread(thread_id: str, messages: List[Dict[str, str]]):
    p = THREADS_DIR / f"{thread_id}.json"
    p.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")

def chef_prompt_with_context(user_msg: str) -> List[Dict[str, str]]:
    # Retrieve top chunks from local knowledge base
    ctx_chunks = RAG.search(user_msg, k=5)
    context_block = "\n\n".join(f"- {c}" for c in ctx_chunks) if ctx_chunks else "None."
    sys = {"role": "system", "content": CHEF_SYSTEM}
    ctx = {"role": "system", "content": f"Context from local knowledge:\n{context_block}"}
    usr = {"role": "user", "content": user_msg}
    return [sys, ctx, usr]

def chat_llama(messages: List[Dict[str, str]]) -> str:
    # Use Ollama's local chat API
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
        },
    }
    r = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    # Ollama returns {"message":{"role":"assistant","content":"..."}}
    content = data.get("message", {}).get("content", "")
    return content or "Sorry, I couldn't draft a reply."

@app.post("/chef_bot.php")  # keep the same path your JS calls
async def chef_bot(request: Request):
    """
    Accepts: { "message": str, "threadId": str|None }
    Returns: { "threadId": str, "message": str }
    """
    body = await request.json()
    user_msg = (body.get("message") or "").strip()
    thread_id = body.get("threadId")
    if not user_msg:
        return {"threadId": thread_id or "", "message": "Please type a message."}

    if not thread_id:
        # lightweight unique id
        thread_id = f"t_{abs(hash(user_msg))}_{len(user_msg)}"

    history = load_thread(thread_id)
    # Build prompt with RAG context each turn (simple & effective)
    messages = chef_prompt_with_context(user_msg)

    # If you want to include running history for style continuity, you can add it:
    # messages = [{"role":m["role"],"content":m["content"]} for m in history[-6:]] + messages

    reply = chat_llama(messages)

    # Persist this turn
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": reply})
    save_thread(thread_id, history)

    return {"threadId": thread_id, "message": reply}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
