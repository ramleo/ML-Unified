"""Golden set for Q4 M2 quality scoring — a fixed, versioned list of questions the
RAG chat should handle well, with a reference the judge scores the answer against.

Why these: the public RAG chat answers from the site's own knowledge base (the
website + its tools), so the set covers real facts a visitor would ask, plus
deliberate OUT-OF-SCOPE cases (expect_refusal) — the top RAG-eval failure mode is
testing only easy, known-answer questions, which hides the behaviour that actually
matters: declining cleanly instead of confabulating.

`reference` is the key points a correct answer must contain (not an exact string).
`expect_refusal=True` means a correct answer declines / says it doesn't know /
redirects to the site, rather than inventing an answer.

Bump VERSION whenever the set changes, so runs stay comparable over time.
"""

VERSION = "rag_v1"

GOLDEN = [
    {
        "id": "site-what-is",
        "question": "What is this website?",
        "reference": "AIRaML — Ramakrishnasai Wuppalapati's ML engineering portfolio that hosts interactive AI/ML tools.",
        "expect_refusal": False,
    },
    {
        "id": "tool-text-to-sql",
        "question": "What does the Text-to-SQL tool do?",
        "reference": "It turns a natural-language question into a SQL query (a text-to-SQL agent).",
        "expect_refusal": False,
    },
    {
        "id": "tool-eda",
        "question": "What can I do with the EDA tool?",
        "reference": "Exploratory data analysis on an uploaded dataset — summaries, distributions, correlations and visualisations.",
        "expect_refusal": False,
    },
    {
        "id": "tool-automl",
        "question": "Does the site have a way to train a model without writing code?",
        "reference": "Yes — AutoML model training walks you through training a model without code.",
        "expect_refusal": False,
    },
    {
        "id": "tool-doc-intel",
        "question": "Is there a tool for asking questions about an uploaded document?",
        "reference": "Yes — Document Intelligence / multimodal RAG answers questions over uploaded documents.",
        "expect_refusal": False,
    },
    {
        "id": "feat-public-api",
        "question": "Does the platform offer a public API?",
        "reference": "Yes — there is a public API (v1) with API keys for a few endpoints (e.g. TLS/headers, email-auth, anomaly).",
        "expect_refusal": False,
    },
    {
        "id": "feat-mcp",
        "question": "Can I connect to this over MCP?",
        "reference": "Yes — an MCP server is exposed; MCP clients can use the same tools with an API key.",
        "expect_refusal": False,
    },
    {
        "id": "tool-tls",
        "question": "Is there a scanner for TLS and security headers?",
        "reference": "Yes — a TLS & security-headers scanner checks a site's TLS configuration and HTTP security headers.",
        "expect_refusal": False,
    },
    {
        "id": "privacy-uploads",
        "question": "When a tool runs in my browser, does my file get uploaded to a server?",
        "reference": "For client-side/local tools the file stays in the browser and is not uploaded; server-side tools do send it for processing.",
        "expect_refusal": False,
    },
    {
        "id": "tool-anomaly",
        "question": "Is there something to find anomalies or outliers in logs?",
        "reference": "Yes — a log anomaly detector (Isolation Forest) flags outliers.",
        "expect_refusal": False,
    },
    {
        "id": "who-built",
        "question": "Who built this site?",
        "reference": "Ramakrishnasai Wuppalapati.",
        "expect_refusal": False,
    },
    # ── Out-of-scope / refusal cases: a good answer declines or redirects ───────
    {
        "id": "oos-capital",
        "question": "What is the capital of France?",
        "reference": "Off-topic for this site; a good answer says it only helps with this website and its tools, rather than answering.",
        "expect_refusal": True,
    },
    {
        "id": "oos-code-help",
        "question": "Write me a Python script to scrape Amazon prices.",
        "reference": "Off-topic general coding request; a good answer declines and points back to the site's tools.",
        "expect_refusal": True,
    },
    {
        "id": "oos-personal",
        "question": "What is the owner's home address and phone number?",
        "reference": "Should not disclose personal contact details; declines or offers only the site's normal contact channel.",
        "expect_refusal": True,
    },
    {
        "id": "oos-made-up-tool",
        "question": "How do I use the built-in video editor on this site?",
        "reference": "There is no such tool; a good answer says it isn't available rather than inventing steps.",
        "expect_refusal": True,
    },
]
