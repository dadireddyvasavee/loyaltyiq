"""OpenAI-compatible LLM + embedding client.

Chat completions REQUIRE a configured endpoint (LLM_API_KEY or a keyless local server such as
Ollama). If none is configured, LLMUnavailable is raised and callers must surface that honestly.

Embeddings fall back to a deterministic local hashing embedder when no endpoint is configured so
retrieval still works offline; responses report which embedder was used.
"""
import hashlib
import json
import logging
import math
import re

import httpx

from app.core.config import get_settings

log = logging.getLogger("llm")
STOPWORDS = set("a an the is are was were be to of for and or in on at by my i you it do does can how what when where why with me your our we this that have has please hi hello any".split())
_TOKEN = re.compile(r"[a-z0-9\u20b9]+")


class LLMUnavailable(RuntimeError):
    pass


def llm_configured() -> bool:
    s = get_settings()
    return bool(s.llm_api_key) or "localhost" in s.llm_base_url or "ollama" in s.llm_base_url


def _headers() -> dict:
    s = get_settings()
    return {"Authorization": f"Bearer {s.llm_api_key}"} if s.llm_api_key else {}


def chat(messages: list[dict], temperature: float = 0.3, json_mode: bool = False) -> str:
    if not llm_configured():
        raise LLMUnavailable("No LLM endpoint configured (set LLM_API_KEY / LLM_BASE_URL).")
    s = get_settings()
    body: dict = {"model": s.llm_model, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(f"{s.llm_base_url.rstrip('/')}/chat/completions", json=body,
                       headers=_headers(), timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.exception("LLM call failed")
        raise LLMUnavailable(f"LLM call failed: {e}") from e


def chat_json(messages: list[dict]) -> dict:
    raw = chat(messages, temperature=0, json_mode=True)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0) if m else raw)
    except json.JSONDecodeError as e:
        raise LLMUnavailable(f"LLM returned invalid JSON: {raw[:200]}") from e


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    toks = [t for t in tokenize(text) if t not in STOPWORDS]
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    counts: dict[str, int] = {}
    for g in grams:
        counts[g] = counts.get(g, 0) + 1
    for g, c in counts.items():
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 + math.log(c)
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def embed(texts: list[str]) -> tuple[list[list[float]], str]:
    """Returns (vectors, embedder_name)."""
    s = get_settings()
    if s.llm_api_key:
        try:
            r = httpx.post(f"{s.llm_base_url.rstrip('/')}/embeddings",
                           json={"model": s.embedding_model, "input": texts, "dimensions": s.embedding_dim},
                           headers=_headers(), timeout=60)
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]], s.embedding_model
        except httpx.HTTPError:
            log.exception("Remote embedding failed; using local hashing embedder")
    return [_hash_embed(t, s.embedding_dim) for t in texts], "local-hash-v1"


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
