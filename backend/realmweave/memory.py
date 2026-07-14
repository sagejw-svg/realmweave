"""Per-agent memory stream with lightweight retrieval (RAG-lite).

Each MemoryEntry has text, an importance score (0-10), a creation timestamp
(in world minutes), and an optional embedding. Retrieval scores entries by a
weighted blend of recency, importance and relevance -- the same recipe used in
generative-agent research -- so the LLM only ever sees the handful of memories
that matter for the current moment.

The embedding backend is pluggable: if an embedder is provided (e.g. Ollama's
embeddings endpoint) we use cosine relevance, otherwise we fall back to keyword
overlap so the system runs with zero GPU.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional
import math
import re

Embedder = Callable[[str], List[float]]

_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set:
    return set(_WORD.findall(text.lower()))


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class MemoryEntry:
    text: str
    importance: float
    created_at: int          # world minutes
    last_accessed: int
    kind: str = "observation"  # observation | reflection | dialogue | event
    embedding: Optional[List[float]] = None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "importance": self.importance,
            "created_at": self.created_at,
            "kind": self.kind,
        }


@dataclass
class MemoryStream:
    owner: str
    entries: List[MemoryEntry] = field(default_factory=list)
    embedder: Optional[Embedder] = None
    # half-life for recency decay, in world minutes (~1 day)
    recency_halflife: float = 1440.0

    def add(self, text: str, importance: float, now: int, kind: str = "observation") -> MemoryEntry:
        emb = None
        if self.embedder is not None:
            try:
                emb = self.embedder(text)
            except Exception:
                emb = None
        e = MemoryEntry(text=text, importance=float(importance), created_at=now,
                        last_accessed=now, kind=kind, embedding=emb)
        self.entries.append(e)
        return e

    def retrieve(self, query: str, now: int, k: int = 5) -> List[MemoryEntry]:
        if not self.entries:
            return []
        q_emb = None
        if self.embedder is not None:
            try:
                q_emb = self.embedder(query)
            except Exception:
                q_emb = None
        q_tokens = _tokens(query)

        scored = []
        for e in self.entries:
            # recency: exponential decay on time since last access
            age = max(0, now - e.last_accessed)
            recency = 0.5 ** (age / self.recency_halflife)
            # relevance: cosine if embeddings, else jaccard-ish keyword overlap
            if q_emb is not None and e.embedding is not None:
                relevance = _cosine(q_emb, e.embedding)
            else:
                et = _tokens(e.text)
                inter = len(q_tokens & et)
                relevance = inter / (len(q_tokens) + 1) if q_tokens else 0.0
            importance = e.importance / 10.0
            score = 1.0 * relevance + 0.8 * importance + 0.6 * recency
            scored.append((score, e))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = [e for _, e in scored[:k]]
        for e in top:
            e.last_accessed = now
        return top

    def recent(self, n: int = 5) -> List[MemoryEntry]:
        return self.entries[-n:]

    def to_dict(self) -> dict:
        return {"owner": self.owner, "entries": [e.to_dict() for e in self.entries[-200:]]}
