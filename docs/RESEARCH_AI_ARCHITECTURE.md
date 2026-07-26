# SB Trading System - Research And AI Architecture

## Scope

This subsystem turns the Stacey Burke PDFs into a searchable, cited research library
and combines those sources with deterministic market context. It does not execute
trades and it does not treat model output as a signal.

## Data Flow

```text
PDF corpus
  -> page text extraction
  -> page-aware chunks and setup tags
  -> local SQLite research index
  -> hybrid search and citations
  -> deterministic market-context packet
  -> retrieval-only answer or OpenAI Responses API synthesis
  -> Research UI with original source pages
```

## Components

`src/sb_system/research.py`

- Inventories PDFs under `docs`.
- Preserves document path, page number, category, setup tags, and extracted text.
- Builds local feature-hash vectors with no external service.
- Supports optional OpenAI embeddings through configuration.
- Ranks results with vector, sparse-term, setup, phrase, and content-quality signals.
- Renders selected source pages to PNG through PyMuPDF.

`src/sb_system/ai_research.py`

- Retrieves evidence before generating any analysis.
- Adds deterministic D1 market context when a symbol is available.
- Uses citation IDs such as `[S1]` in the evidence packet.
- Runs in retrieval-only mode when `OPENAI_API_KEY` is absent.
- Uses the Responses API for evidence synthesis and multimodal page analysis when
  configured.

`web/src/ResearchPage.tsx`

- Search: query, setup filter, ranked evidence, and source-page inspector.
- Library: document inventory, categories, tags, page counts, and original PDFs.
- Analyst: market/setup context, evidence answer, source list, and tool trace.

## Evidence Contract

Every retrieved result includes:

- Stable document ID
- Human-readable source title
- Source category
- PDF page number
- Setup tags
- Source excerpt
- Retrieval relevance score

AI instructions require the model to distinguish source evidence from inference,
identify weakening or missing evidence, state invalidation evidence, and avoid order
instructions. The deterministic engine remains responsible for signal labels.

## Storage

The runtime index is:

```text
data/research/research.sqlite3
```

Rendered page cache:

```text
data/research/pages/
```

Both are generated, ignored by Git, and rebuilt on each machine:

```bash
python scripts/index_research_library.py
```

Force a complete rebuild after changing the embedding provider:

```bash
python scripts/index_research_library.py --rebuild
```

## Configuration

```env
SB_RESEARCH_DOCS_DIR=docs
SB_RESEARCH_INDEX=data/research/research.sqlite3
SB_RESEARCH_PAGE_CACHE=data/research/pages
SB_EMBEDDING_PROVIDER=local
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-terra
OPENAI_REASONING_EFFORT=low
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Keep `OPENAI_API_KEY` in `.env`; never commit it.

When AI is enabled, the selected evidence excerpts and deterministic market-context
packet are sent to OpenAI for synthesis. Visual analysis also sends the selected
rendered PDF page. Keep `SB_EMBEDDING_PROVIDER=local` if the document corpus must not
be sent for remote embedding.

## Validation Boundary

The platform can retrieve and explain source evidence now. The following claims still
require user-labelled examples before they can be considered validated:

- Correctness of FGD, FRD, Inside Day, 3DL, 3DS, CIB, and 2CIB rules
- Calibrated signal confidence
- Calibrated current-chart-to-example visual similarity
- Setup outcome statistics

Until that validation is complete, UI scores are research-ranking values, not trade
probabilities.
