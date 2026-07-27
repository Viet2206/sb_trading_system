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
  -> deterministic current-chart fingerprint
  -> ranked historical example pages
  -> user relevance feedback
  -> deterministic market-context packet
  -> retrieval-only answer or configured-provider synthesis
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
- Runs in retrieval-only mode when the selected provider has no API key.
- Supports Z.AI Chat Completions and the OpenAI Responses API.
- Uses a separately configurable vision model for rendered source-page analysis.

`web/src/ResearchPage.tsx`

- Search: query, setup filter, ranked evidence, and source-page inspector.
- Library: document inventory, categories, tags, page counts, and original PDFs.
- Analyst: market/setup context, evidence answer, source list, and tool trace.

`src/sb_system/example_matching.py`

- Builds a stable current-chart fingerprint from deterministic daily context.
- Preserves current-day versus previous-day signal timing.
- Ranks unique PDF pages using setup, direction, retrieval, and source-quality
  components.
- Alternates pages across source documents to avoid repetitive result shelves.
- Stores Relevant, Unsure, and Not Relevant feedback for the exact chart fingerprint.

`web/src/HistoricalMatches.tsx`

- Shows ranked source-page thumbnails directly beneath the active chart.
- Displays the fingerprint and transparent score components.
- Opens the cited PDF at the matched page.
- Captures user relevance feedback for later calibration.

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

Historical example feedback:

```text
data/research/historical_example_feedback.json
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
SB_AI_PROVIDER=zai
ZAI_API_KEY=
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
ZAI_MODEL=glm-4.7
ZAI_VISION_MODEL=glm-4.6v-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-terra
OPENAI_REASONING_EFFORT=low
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Keep provider API keys in `.env`; never commit them.

When AI is enabled, the selected evidence excerpts and deterministic market-context
packet are sent to the selected provider for synthesis. Visual analysis also sends
the selected rendered PDF page. Keep `SB_EMBEDDING_PROVIDER=local` if the document
corpus must not be sent for remote embedding.

## Validation Boundary

The platform can retrieve and explain source evidence now. The following claims still
require user-labelled examples before they can be considered validated:

- Correctness of FGD, FRD, Inside Day, 3DL, 3DS, CIB, and 2CIB rules
- Calibrated signal confidence
- Calibrated current-chart-to-example visual similarity
- Setup outcome statistics

Until that validation is complete, UI scores are research-ranking values, not trade
probabilities.

Historical matching currently uses method `context-v1`. It does not compare pixels
between the live chart and the PDF page. A future calibrated visual model should be
trained and evaluated from user-reviewed matches rather than introduced as an
unverified confidence score.
