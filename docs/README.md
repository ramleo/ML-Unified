# Documentation map

Where to look to understand the AIRaML platform (ml-portfolio frontend +
ML-Unified backend). Start with the **core** docs; the rest are per-subsystem
reference.

## Core — read these to understand the whole site

| Doc | Location | What it tells you |
|---|---|---|
| **PRD 00–05** | `ML-Unified/docs/prd/` *(local-only)* | Authoritative spec: 00 overview · 01 architecture · 02 cross-cutting systems · 03 tool catalog · 04 doc-intelligence deep-dive · 05 roadmap (Q1–Q5) |
| **Handbook** | `ml-portfolio/public/handbook.md` | Every user-facing feature/tool in plain language (incl. Public API & MCP) |
| **TECH_STACK.md** | `ML-Unified/TECH_STACK.md` | Full technology stack |
| **README.md** | both repos | Entry point + how to run each repo |

**Fastest path:** PRD 00 → 01 → 05, then the handbook. Covers what the site is,
how it's built, where it's going, and what users get.

## Access & security *(local-only)*

| Doc | Location | What it tells you |
|---|---|---|
| **ACCESS_AND_AUTH.md** | `ml-portfolio/docs/` | Auth model: owner vs recruiters vs users, share-links, API keys |
| **SECURITY_REFERENCE.md** | `ML-Unified/docs/` | Security boundaries, gates, and threat model |

## Subsystem reference (only when working on that area)

| Area | Doc |
|---|---|
| Logging | `LOGGING_SPEC.md`, `LOGGING_COVERAGE.md`, `LOGGING_OVERVIEW.md` |
| Errors | `ERROR_TRACKING.md` |
| Observability | `OBSERVABILITY_PLAN.md`, `FEATURE_TRACKING_SPEC.md` |
| QA / Testwright | `QA_*_PLAN.md`, `TESTWRIGHT_*.md` |
| RAG | `RAG_Implementation_Roadmap.md` |
| Click audit | `CLICK_AUDIT.md` |
| EDA rebuild | `EDA_REBUILD_SPEC.md` |
| Open issues | `OPEN_ISSUES.md` |
| Licenses | `ML-Unified/THIRD_PARTY.md` |
| Website guidelines | `WEBSITE_GUIDELINES.md` |

> Docs marked *local-only* are gitignored (PRD, access & security) — they live on
> the maintainer's machine, not in the public repos.
