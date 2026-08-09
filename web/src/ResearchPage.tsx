import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BookOpen,
  BrainCircuit,
  ExternalLink,
  FileSearch,
  Image,
  Library,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import {
  ResearchAnalysisResponse,
  ResearchDocument,
  ResearchResult,
  ResearchSearchResponse,
  ResearchStatus,
  VisionAnalysisResponse,
  analyzeResearch,
  analyzeResearchPage,
  fetchResearchDocuments,
  fetchResearchStatus,
  indexResearchLibrary,
  researchDocumentUrl,
  researchPageImageUrl,
  searchResearch,
} from "./api";

type ResearchTab = "search" | "library";
type ResearchPageMode = "browse" | "analyst";

type ResearchPageProps = {
  mode: ResearchPageMode;
  currentSymbol: string;
  currentTimeframe: string;
};

const suggestedQuestions = [
  "Compare the current market setup with the most relevant historical SB examples. Identify similarities, differences, invalidation, and what to wait for.",
  "What evidence defines a First Green Day setup?",
  "Compare Inside Day false break and continuation.",
  "What should I observe during each session hour?",
  "Find Day 3 breakout trader examples and invalidation evidence.",
];

export function ResearchPage({
  mode,
  currentSymbol,
  currentTimeframe,
}: ResearchPageProps) {
  const [tab, setTab] = useState<ResearchTab>("search");
  const [status, setStatus] = useState<ResearchStatus | null>(null);
  const [documents, setDocuments] = useState<ResearchDocument[]>([]);
  const [query, setQuery] = useState("first green day setup");
  const [setup, setSetup] = useState("");
  const [searchData, setSearchData] = useState<ResearchSearchResponse | null>(null);
  const [selectedSource, setSelectedSource] = useState<ResearchResult | null>(null);
  const [question, setQuestion] = useState(suggestedQuestions[0]);
  const [analysis, setAnalysis] = useState<ResearchAnalysisResponse | null>(null);
  const [vision, setVision] = useState<VisionAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const categories = useMemo(
    () => Array.from(new Set(documents.map((item) => item.category))).sort(),
    [documents],
  );

  useEffect(() => {
    void loadWorkspace();
  }, []);

  async function loadWorkspace() {
    setLoading(true);
    setError(null);
    try {
      const nextStatus = await fetchResearchStatus();
      setStatus(nextStatus);
      if (nextStatus.ready && mode !== "analyst") {
        const nextDocuments = await fetchResearchDocuments();
        setDocuments(nextDocuments);
      }
    } catch (err) {
      setError(messageFrom(err, "Failed to load research workspace"));
    } finally {
      setLoading(false);
    }
  }

  async function buildIndex(rebuild = false) {
    setIndexing(true);
    setError(null);
    try {
      await indexResearchLibrary(rebuild);
      await loadWorkspace();
    } catch (err) {
      setError(messageFrom(err, "Failed to index the document library"));
    } finally {
      setIndexing(false);
    }
  }

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    setWorking(true);
    setError(null);
    try {
      const result = await searchResearch(query, { setup: setup || undefined, limit: 18 });
      setSearchData(result);
      setSelectedSource(result.results[0] ?? null);
      setVision(null);
    } catch (err) {
      setError(messageFrom(err, "Search failed"));
    } finally {
      setWorking(false);
    }
  }

  async function runAnalysis(nextQuestion = question) {
    if (!nextQuestion.trim()) return;
    setQuestion(nextQuestion);
    setWorking(true);
    setError(null);
    try {
      const result = await analyzeResearch({
        question: nextQuestion,
        symbol: currentSymbol || undefined,
        timeframe: currentTimeframe || undefined,
        setup: setup || undefined,
      });
      setAnalysis(result);
      setSelectedSource(result.sources[0] ?? null);
      setVision(null);
    } catch (err) {
      setError(messageFrom(err, "Analysis failed"));
    } finally {
      setWorking(false);
    }
  }

  async function runVision(source: ResearchResult) {
    setSelectedSource(source);
    setWorking(true);
    setError(null);
    try {
      const result = await analyzeResearchPage({
        document_id: source.document_id,
        page: source.page,
        question: "Identify the visible setup, annotations, session structure, and supporting evidence.",
      });
      setVision(result);
    } catch (err) {
      setError(messageFrom(err, "Page analysis failed"));
    } finally {
      setWorking(false);
    }
  }

  if (loading && !status) {
    return <div className="research-page"><EmptyState text="Loading research workspace" /></div>;
  }

  if (!status?.ready) {
    return (
      <div className="research-page">
        {error ? <div className="inline-error">{error}</div> : null}
        <section className="research-onboarding">
          <div className="research-onboarding-icon"><Library size={24} /></div>
          <h3>Build the SB Research Index</h3>
          <p>
            Index the PDFs in <code>docs</code> for local search, source citations,
            pattern retrieval, page previews, and AI analysis.
          </p>
          <button
            className="small-action-button primary"
            onClick={() => void buildIndex(false)}
            disabled={indexing}
          >
            <FileSearch size={17} />
            <span>{indexing ? "Indexing documents" : "Build Index"}</span>
          </button>
        </section>
      </div>
    );
  }

  return (
    <div
      className={
        mode === "analyst"
          ? "research-page analyst-panel-mode"
          : "research-page"
      }
    >
      {mode !== "analyst" ? (
        <div className="research-commandbar">
          <div className="research-tabs" role="tablist" aria-label="Research workspace">
            <TabButton active={tab === "search"} onClick={() => setTab("search")} icon={<Search size={16} />}>
              Search
            </TabButton>
            <TabButton active={tab === "library"} onClick={() => setTab("library")} icon={<BookOpen size={16} />}>
              Library
            </TabButton>
          </div>
          <div className="research-status-strip">
            <span>{status.documents} documents</span>
            <span>{status.pages.toLocaleString()} pages</span>
            <span>{status.chunks.toLocaleString()} passages</span>
            <span className={status.ai.configured ? "status-dot ready" : "status-dot local"}>
              {status.ai.configured ? status.ai.model : "Local mode"}
            </span>
            <button
              className="icon-action"
              title="Refresh research status"
              onClick={() => void loadWorkspace()}
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
      ) : (
        <div className="analyst-panel-statusbar">
          <span className={status.ai.configured ? "status-dot ready" : "status-dot local"}>
            {status.ai.configured ? status.ai.model : "Retrieval only"}
          </span>
          <button
            className="icon-action"
            title="Refresh research status"
            onClick={() => void loadWorkspace()}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      )}

      {error ? <div className="inline-error">{error}</div> : null}

      {mode !== "analyst" && tab === "search" ? (
        <SearchWorkspace
          query={query}
          setup={setup}
          status={status}
          searchData={searchData}
          selectedSource={selectedSource}
          vision={vision}
          working={working}
          onQuery={setQuery}
          onSetup={setSetup}
          onSearch={runSearch}
          onSelectSource={(source) => {
            setSelectedSource(source);
            setVision(null);
          }}
          onVision={runVision}
        />
      ) : null}

      {mode !== "analyst" && tab === "library" ? (
        <LibraryWorkspace documents={documents} categories={categories} />
      ) : null}

      {mode === "analyst" ? (
        <AnalystWorkspace
          compact={mode === "analyst"}
          status={status}
          question={question}
          setup={setup}
          analysis={analysis}
          selectedSource={selectedSource}
          vision={vision}
          working={working}
          onQuestion={setQuestion}
          onSetup={setSetup}
          onAnalyze={runAnalysis}
          onSelectSource={(source) => {
            setSelectedSource(source);
            setVision(null);
          }}
          onVision={runVision}
        />
      ) : null}
    </div>
  );
}

function SearchWorkspace({
  query,
  setup,
  status,
  searchData,
  selectedSource,
  vision,
  working,
  onQuery,
  onSetup,
  onSearch,
  onSelectSource,
  onVision,
}: {
  query: string;
  setup: string;
  status: ResearchStatus;
  searchData: ResearchSearchResponse | null;
  selectedSource: ResearchResult | null;
  vision: VisionAnalysisResponse | null;
  working: boolean;
  onQuery: (value: string) => void;
  onSetup: (value: string) => void;
  onSearch: (event?: FormEvent) => void;
  onSelectSource: (source: ResearchResult) => void;
  onVision: (source: ResearchResult) => void;
}) {
  return (
    <div className="research-workspace">
      <section className="research-main">
        <form className="research-searchbar" onSubmit={onSearch}>
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Search SB concepts, setups, sessions, and examples"
          />
          <SetupSelect value={setup} options={status.setup_types} onChange={onSetup} />
          <button type="submit" disabled={working}>
            {working ? "Searching" : "Search"}
          </button>
        </form>

        <div className="research-result-heading">
          <div>
            <h3>Evidence Results</h3>
            <p>
              {searchData
                ? `${searchData.count} ranked passages for "${searchData.query}"`
                : "Search across extracted text and chart-example pages"}
            </p>
          </div>
        </div>

        <div className="research-results">
          {searchData?.results.map((result) => (
            <SourceResult
              key={`${result.document_id}-${result.page}-${result.citation}`}
              source={result}
              selected={
                selectedSource?.document_id === result.document_id
                && selectedSource.page === result.page
              }
              onSelect={() => onSelectSource(result)}
            />
          ))}
          {!searchData ? <EmptyState text="Run a search to inspect cited SB evidence." /> : null}
          {searchData?.count === 0 ? <EmptyState text="No evidence matched this search." /> : null}
        </div>
      </section>

      <SourceInspector
        source={selectedSource}
        vision={vision}
        working={working}
        aiConfigured={status.ai.configured}
        onVision={onVision}
      />
    </div>
  );
}

function LibraryWorkspace({
  documents,
  categories,
}: {
  documents: ResearchDocument[];
  categories: string[];
}) {
  const [category, setCategory] = useState("");
  const visible = category
    ? documents.filter((item) => item.category === category)
    : documents;
  return (
    <section className="library-workspace">
      <div className="library-toolbar">
        <div>
          <h3>Source Library</h3>
          <p>Authoritative notes and historical chart-example collections</p>
        </div>
        <label>
          <span>Category</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">All sources</option>
            {categories.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
      </div>
      <div className="document-table-wrap">
        <table className="document-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Category</th>
              <th>Tags</th>
              <th>Pages</th>
              <th aria-label="Open document" />
            </tr>
          </thead>
          <tbody>
            {visible.map((document) => (
              <tr key={document.id}>
                <td>
                  <strong>{document.title}</strong>
                  <span>{document.path}</span>
                </td>
                <td>{document.category}</td>
                <td><TagList values={document.setup_types} /></td>
                <td>{document.pages}</td>
                <td>
                  <a
                    className="icon-action"
                    href={researchDocumentUrl(document.id)}
                    target="_blank"
                    rel="noreferrer"
                    title="Open PDF"
                  >
                    <ExternalLink size={15} />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AnalystWorkspace({
  compact = false,
  status,
  question,
  setup,
  analysis,
  selectedSource,
  vision,
  working,
  onQuestion,
  onSetup,
  onAnalyze,
  onSelectSource,
  onVision,
}: {
  compact?: boolean;
  status: ResearchStatus;
  question: string;
  setup: string;
  analysis: ResearchAnalysisResponse | null;
  selectedSource: ResearchResult | null;
  vision: VisionAnalysisResponse | null;
  working: boolean;
  onQuestion: (value: string) => void;
  onSetup: (value: string) => void;
  onAnalyze: (value?: string) => void;
  onSelectSource: (source: ResearchResult) => void;
  onVision: (source: ResearchResult) => void;
}) {
  return (
    <div className={compact ? "analyst-workspace compact" : "analyst-workspace"}>
      <section className="analyst-column">
        <div className="analyst-contextbar">
          <label>
            <span>Setup</span>
            <SetupSelect value={setup} options={status.setup_types} onChange={onSetup} />
          </label>
        </div>

        <form
          className="analyst-prompt"
          onSubmit={(event) => {
            event.preventDefault();
            onAnalyze();
          }}
        >
          <textarea
            value={question}
            onChange={(event) => onQuestion(event.target.value)}
            rows={4}
            placeholder="Ask about the selected market, a setup rule, or source evidence"
          />
          <div>
            <span className={status.ai.configured ? "agent-mode ai" : "agent-mode local"}>
              <Sparkles size={14} />
              {status.ai.configured ? status.ai.model : "Retrieval only"}
            </span>
            <button type="submit" disabled={working}>
              <BrainCircuit size={17} />
              {working ? "Analyzing" : "Analyze Evidence"}
            </button>
          </div>
        </form>

        <div className="suggested-prompts">
          {suggestedQuestions.map((item) => (
            <button key={item} onClick={() => onAnalyze(item)}>{item}</button>
          ))}
        </div>

        <section className="analysis-output">
          <div className="analysis-output-heading">
            <h3>Research Analysis</h3>
            {analysis?.warning ? <span>{analysis.warning}</span> : null}
          </div>
          {analysis ? (
            <>
              <MarkdownAnswer className="analysis-answer">
                {analysis.answer}
              </MarkdownAnswer>
              <div className="tool-trace">
                {analysis.tools.map((tool) => (
                  <div key={tool.name}>
                    <span />
                    <div><strong>{humanize(tool.name)}</strong><p>{tool.detail}</p></div>
                  </div>
                ))}
              </div>
              <div className="analysis-sources">
                <h4>Evidence Sources</h4>
                {analysis.sources.map((source) => (
                  <SourceResult
                    key={`${source.document_id}-${source.page}-${source.citation}`}
                    source={source}
                    selected={
                      selectedSource?.document_id === source.document_id
                      && selectedSource.page === source.page
                    }
                    onSelect={() => onSelectSource(source)}
                  />
                ))}
              </div>
            </>
          ) : (
            <EmptyState text="Ask a question to combine market context with cited SB evidence." />
          )}
        </section>
      </section>

      {!compact || selectedSource ? (
        <SourceInspector
          source={selectedSource}
          vision={vision}
          working={working}
          aiConfigured={status.ai.configured}
          onVision={onVision}
        />
      ) : null}
    </div>
  );
}

function SourceInspector({
  source,
  vision,
  working,
  aiConfigured,
  onVision,
}: {
  source: ResearchResult | null;
  vision: VisionAnalysisResponse | null;
  working: boolean;
  aiConfigured: boolean;
  onVision: (source: ResearchResult) => void;
}) {
  return (
    <aside className="source-inspector">
      <div className="source-inspector-heading">
        <div>
          <h3>Source Page</h3>
          <p>{source ? `${source.document_title} / page ${source.page}` : "Select a result"}</p>
        </div>
        {source ? (
          <a
            className="icon-action"
            href={researchDocumentUrl(source.document_id, source.page)}
            target="_blank"
            rel="noreferrer"
            title="Open source PDF"
          >
            <ExternalLink size={16} />
          </a>
        ) : null}
      </div>
      {source ? (
        <>
          <div className="source-page-preview">
            <img
              src={researchPageImageUrl(source.document_id, source.page)}
              alt={`${source.document_title} page ${source.page}`}
            />
          </div>
          <button
            className="vision-button"
            onClick={() => onVision(source)}
            disabled={working}
            title={aiConfigured ? "Analyze this page with vision" : "Prepare page preview"}
          >
            <Image size={16} />
            {working ? "Working" : aiConfigured ? "Analyze Visual Page" : "Check Vision Setup"}
          </button>
          {vision ? (
            <div className="vision-output">
              <strong>{vision.mode === "ai" ? "Visual Analysis" : "Vision Status"}</strong>
              <MarkdownAnswer className="vision-answer">
                {vision.answer}
              </MarkdownAnswer>
            </div>
          ) : null}
        </>
      ) : (
        <EmptyState text="Choose evidence to inspect the original page." />
      )}
    </aside>
  );
}

function MarkdownAnswer({
  children,
  className,
}: {
  children: string;
  className: string;
}) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: linkChildren }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {linkChildren}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function SourceResult({
  source,
  selected,
  onSelect,
}: {
  source: ResearchResult;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={selected ? "source-result selected" : "source-result"}
      onClick={onSelect}
    >
      <div className="source-result-topline">
        <span className="citation-label">[{source.citation}]</span>
        <strong>{source.document_title}</strong>
        <span>p. {source.page}</span>
        <span
          className="relevance"
          title="Research retrieval relevance, not signal confidence"
        >
          {Math.round(source.score * 100)}%
        </span>
      </div>
      <p>{source.excerpt}</p>
      <TagList values={source.setup_types} />
    </button>
  );
}

function SetupSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">All setups</option>
      {options.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}
    </select>
  );
}

function TagList({ values }: { values: string[] }) {
  if (values.length === 0) return <span className="no-tags">General SB</span>;
  return (
    <div className="research-tags">
      {values.slice(0, 4).map((value) => <span key={value}>{humanize(value)}</span>)}
    </div>
  );
}

function TabButton({
  active,
  icon,
  children,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className={active ? "active" : ""} onClick={onClick} role="tab">
      {icon}
      <span>{children}</span>
    </button>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="research-empty">
      <FileSearch size={20} />
      <span>{text}</span>
    </div>
  );
}

function humanize(value: string) {
  if (value === "closing-inside-breakout") return "Close In Breakout";
  return value
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
