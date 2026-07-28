"""Answer groundedness scoring (MMRAG-04) — a mini Self-RAG check.

Splits the generated answer into sentences and, for each one, finds its best
cosine-similarity match against the retrieved chunks (using the SAME
embedding model already loaded for retrieval — no extra model, no extra LLM
call). A sentence with no well-matching chunk is flagged as "ungrounded" —
a heuristic signal that it may not be supported by what was actually
retrieved, not a certainty (semantically distant paraphrase of a real fact
would also score low; this trades some false positives for zero added
latency/cost).

Thresholds calibrated against real all-MiniLM-L6-v2 embeddings, not guessed:
sentences paraphrasing their source chunk scored 0.44-0.94 max similarity;
fabricated, unrelated sentences scored 0.10-0.36 (see Part 210 session
notes). 0.40 sits just above the observed hallucination ceiling.

Kept as a standalone module (SRP) so `query.py` depends only on this
function's signature, not on how the score is computed — a future swap to
an LLM-judge implementation only needs to preserve `score_groundedness`'s
signature, not touch any caller.
"""
from __future__ import annotations

import re
from typing import Callable

from routers.rag.cache import cosine_sim

_UNGROUNDED_THRESHOLD = 0.40
_HIGH_THRESHOLD = 0.55
_MEDIUM_THRESHOLD = 0.35

# Devanagari danda (।), Arabic question mark (؟), and full-width CJK
# terminators (。！？) alongside the original ASCII ones — a non-English
# answer (MMRAG-12) that only ever gets split on ".!?" collapses into ONE
# giant "sentence" for scoring, the same dilution bug already fixed for the
# source-chunk side (see score_groundedness's docstring below). \s* (not
# \s+) because CJK text often has no space after its terminator at all.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।؟。！？])\s*")


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip())]
    return [s for s in sentences if len(s) >= 8]  # drop stray fragments/whitespace


# MiniLM (all-MiniLM-L6-v2, this project's retrieval embedder — see
# score_groundedness's docstring) is English-centric; its cross-lingual
# similarity between a correct non-English answer and its true English
# source is unreliably low, not just "somewhat lower." Observed live
# (2026-07-28): a Hindi answer ("दीवार हरे रंग की है...", correctly
# translated and grounded in the English source caption) scored 0.185 —
# "low" / flagged unsupported — despite being accurate. Rather than show a
# confidently wrong badge, detect a script mismatch between answer and
# source and skip scoring entirely (None — the frontend already renders
# nothing for that) instead of asserting a number this embedder can't
# actually back up.
_SCRIPT_MISMATCH_RATIO = 0.3


def _non_ascii_letter_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return (sum(1 for c in letters if ord(c) > 127) / len(letters)) if letters else 0.0


def score_groundedness(answer: str, chunks: list[dict], embed_fn: Callable[[list[str]], list]) -> dict | None:
    """Returns {"score": float, "level": "high"|"medium"|"low",
    "ungrounded_sentences": list[str]}, or None if there's nothing to score
    (no answer text, or no chunks were retrieved to check against).

    Matches the answer side's sentence-level granularity on the SOURCE side
    too — each chunk is split into sentences and embedded individually,
    not embedded whole. Real bug found live: a car photo's chunk mixed a
    long appearance description ("teal-colored SUV... reads 'DATSUN'") with
    one short trailing spatial fact ("Car — spans most of the frame").
    Embedding that whole chunk as ONE vector averaged the spatial fact away
    under the longer, unrelated appearance text, so the correct answer "The
    car spans most of the frame" scored well below a bicycle photo whose
    chunk was mostly spatial content already (multiple detected objects,
    most naming a side) and so diluted much less. Splitting the chunk into
    sentences lets a short factual answer match its one relevant source
    sentence directly, instead of an entire diluted paragraph."""
    sentences = _split_sentences(answer)
    if not sentences or not chunks:
        return None

    chunk_sentences: list[str] = []
    for c in chunks:
        text = c.get("text", "").strip()
        if text:
            chunk_sentences.extend(_split_sentences(text) or [text])
    if not chunk_sentences:
        return None

    # MMRAG-12 — see _SCRIPT_MISMATCH_RATIO above.
    if (_non_ascii_letter_ratio(answer) > _SCRIPT_MISMATCH_RATIO
            and _non_ascii_letter_ratio(" ".join(chunk_sentences)) <= _SCRIPT_MISMATCH_RATIO):
        return None

    sentence_embs = embed_fn(sentences)
    chunk_embs = embed_fn(chunk_sentences)

    ungrounded: list[str] = []
    per_sentence_max: list[float] = []
    for sentence, s_emb in zip(sentences, sentence_embs):
        best = max(cosine_sim(s_emb, c_emb) for c_emb in chunk_embs)
        per_sentence_max.append(best)
        if best < _UNGROUNDED_THRESHOLD:
            ungrounded.append(sentence)

    score = sum(per_sentence_max) / len(per_sentence_max)
    level = "high" if score >= _HIGH_THRESHOLD else "medium" if score >= _MEDIUM_THRESHOLD else "low"

    return {
        "score": round(score, 3),
        "level": level,
        "ungrounded_sentences": ungrounded,
    }
