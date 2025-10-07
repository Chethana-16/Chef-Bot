import json
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

from rag import RAG, DATA_DIR

# ==============================================================
#  Chef CTS Backend – FastAPI Service
#  --------------------------------------------------------------
#  This backend powers the Chef CTS chatbot. It connects the
#  front-end chat UI to a local Ollama model (Llama 3.1 8B) and
#  augments responses with context retrieved from a local
#  RAG (Retrieval-Augmented Generation) knowledge base.
# ==============================================================


# === Ollama & Model Configuration ===
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"  # Local Ollama REST endpoint
MODEL_NAME = "phi3:mini"                           # Model used for inference

# === Thread Storage Configuration ===
# Each conversation is persisted as a JSON file under /data/threads.
# This allows continuity across multiple user messages.
THREADS_DIR = DATA_DIR / "threads"
THREADS_DIR.mkdir(parents=True, exist_ok=True)

# === Initialize FastAPI Application ===
app = FastAPI(title="Chef CTS Backend")

# === Cross-Origin Resource Sharing (CORS) ===
# Enables requests from the static front-end served at a different origin.
# For local development, all origins are allowed; can be restricted later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Load or Build RAG Index ===
# The RAG index (FAISS vector store) is built once and kept in memory
# for fast semantic retrieval of relevant text chunks.
RAG.load()

# === System Prompt ===
# Defines the chef's personality, tone, and behavioral rules.
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


# ==============================================================
#  Thread Management Helpers
# ==============================================================

def load_thread(thread_id: str) -> List[Dict[str, str]]:
    """
    Load a saved conversation thread from disk.

    Args:
        thread_id (str): Unique conversation identifier.

    Returns:
        List[Dict[str, str]]: The stored conversation history (list of message dicts).
    """
    p = THREADS_DIR / f"{thread_id}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_thread(thread_id: str, messages: List[Dict[str, str]]):
    """
    Save a conversation thread to disk as a JSON file.

    Args:
        thread_id (str): Conversation identifier.
        messages (List[Dict[str, str]]): Full chat history.
    """
    p = THREADS_DIR / f"{thread_id}.json"
    p.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


# ==============================================================
#  Prompt & Model Invocation
# ==============================================================

def chef_prompt_with_context(user_msg: str) -> List[Dict[str, str]]:
    """
    Construct the full prompt for the model using:
    - The base system prompt
    - Retrieved RAG context (relevant knowledge chunks)
    - The latest user message

    Args:
        user_msg (str): The user’s latest message.

    Returns:
        List[Dict[str, str]]: List of role-content dicts representing conversation context.
    """
    # Retrieve top-K relevant text chunks from RAG index
    ctx_chunks = RAG.search(user_msg, k=5)
    context_block = "\n\n".join(f"- {c}" for c in ctx_chunks) if ctx_chunks else "None."

    # Compose multi-role message set
    sys = {"role": "system", "content": CHEF_SYSTEM}
    ctx = {"role": "system", "content": f"Context from local knowledge:\n{context_block}"}
    usr = {"role": "user", "content": user_msg}

    return [sys, ctx, usr]


def chat_llama(messages: List[Dict[str, str]]) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    print("\n=== Sending to Ollama ===")
    print(json.dumps(payload, indent=2))

    r = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()

    print("\n=== Ollama Response ===")
    print(json.dumps(data, indent=2))

    content = data.get("message", {}).get("content", "")
    return content or "Sorry, I couldn't draft a reply."


# ==============================================================
#  API Endpoint – /chef_bot.php
# ==============================================================

@app.post("/chef_bot.php")
async def chef_bot(request: Request):
    """
    Primary API endpoint for chat interaction.

    Receives:
        {
            "message": str,      # user input text
            "threadId": str|None # conversation id
        }

    Returns:
        {
            "threadId": str,     # id (created if new)
            "message": str       # model-generated reply
        }

    Workflow:
        1. Parse incoming JSON payload.
        2. Create or load thread history.
        3. Retrieve RAG context relevant to the user message.
        4. Send composed prompt to the Llama model.
        5. Save updated conversation and return assistant reply.
    """
    body = await request.json()
    user_msg = (body.get("message") or "").strip()
    thread_id = body.get("threadId")

    # Validate input
    if not user_msg:
        return {"threadId": thread_id or "", "message": "Please type a message."}

    # Generate a lightweight unique ID for new conversations
    if not thread_id:
        thread_id = f"t_{abs(hash(user_msg))}_{len(user_msg)}"

    # Load existing chat history from disk
    history = load_thread(thread_id)

    # Build complete model input with contextual RAG knowledge
    messages = chef_prompt_with_context(user_msg)

    # Query local Llama model for a response
    reply = chat_llama(messages)

    # Append the new turn to history and persist to disk
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": reply})
    save_thread(thread_id, history)

    # Return formatted JSON response to front-end
    return {"threadId": thread_id, "message": reply}


# ==============================================================
#  Application Entry Point
# ==============================================================

if __name__ == "__main__":
    # Run the FastAPI app with Uvicorn development server
    uvicorn.run(app, host="127.0.0.1", port=8000)
