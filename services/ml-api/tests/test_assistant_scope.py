"""The assistant must decline what it is not for — and only that.

F1: for a long time nothing in the system prompt told the model to refuse
anything. Asked "what is mastercard?" inside the EDA assistant it wrote a page
on payment networks, because it had been given a description of the tool, some
retrieved text, and an instruction to answer. Nothing was bypassed; there was
no rule.

These are wiring tests. They prove the rule reaches the prompt in each mode,
which is the part that breaks silently when someone reorders build_system_prompt
or adds a caller. Whether a given model then obeys it is a question for a live
check against the deployed service, not for a unit test with no model in it.

The second test is the one that matters. Every page except Multimodal RAG lets
the user upload a document into the same chat, so a Mastercard annual report in
the EDA assistant makes "what is mastercard?" a legitimate question. A scope
rule that cannot express that exception would be a worse bug than the one it
fixes.
"""
from __future__ import annotations

import pytest

from routers.rag.citations import build_system_prompt

EDA_CONTEXT = "Tool: Exploratory Data Analysis\nColumns: age numeric, city text"


def test_the_scope_rule_is_in_the_prompt():
    prompt = build_system_prompt(EDA_CONTEXT, chunks=[])
    assert "not a general-purpose chatbot" in prompt
    assert "out of scope" in prompt
    assert "outside what this assistant covers" in prompt


def test_retrieved_content_decides_scope_not_the_subject():
    """The exception that keeps uploads working, stated in the prompt itself."""
    prompt = build_system_prompt(EDA_CONTEXT, chunks=[])
    assert "The retrieved content decides scope, not the subject" in prompt
    assert "whatever it is about" in prompt


def test_the_rule_survives_alongside_retrieved_chunks():
    chunks = [{"source": "notes.pdf", "text": "Payment networks connect banks."}]
    prompt = build_system_prompt(EDA_CONTEXT, chunks)
    assert "out of scope" in prompt
    assert "Payment networks connect banks." in prompt


@pytest.mark.parametrize("length", ["concise", "detailed", "normal"])
def test_the_rule_is_not_dropped_by_an_answer_length(length):
    prompt = build_system_prompt(EDA_CONTEXT, chunks=[], answer_length=length)
    assert "out of scope" in prompt


def test_restrict_to_uploads_supersedes_it_rather_than_stacking():
    """Multimodal RAG's own rule is stricter; two rules would contradict."""
    prompt = build_system_prompt(EDA_CONTEXT, chunks=[], restrict_to_uploads=True)
    assert "not a general-purpose chatbot" not in prompt
    assert "Answer ONLY using the retrieved content below" in prompt


def test_deep_search_gets_it_too():
    """agent.py calls the builder positionally with no restrict flag."""
    from routers.rag.agent import _build_system_prompt
    assert "out of scope" in _build_system_prompt(EDA_CONTEXT, [])


def test_an_empty_context_still_gets_the_rule():
    """A page that sends no tool_context must not end up unscoped."""
    assert "out of scope" in build_system_prompt("", chunks=[])
