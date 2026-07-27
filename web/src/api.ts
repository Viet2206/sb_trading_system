export type CandleSummary = {
  broker_symbol: string;
  timeframe: string;
  first_candle: string;
  last_candle: string;
  candles: number;
};

export type Candle = {
  broker_symbol: string;
  timeframe: string;
  candle_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number | null;
  spread: number | null;
  real_volume: number | null;
};

export type CandleResponse = {
  symbol: string;
  timeframe: string;
  count: number;
  candles: Candle[];
};

export type OverlayLevel = {
  key: string;
  label: string;
  price: number;
  color: string;
  style: "solid" | "dashed" | "dotted";
  start_time?: string;
};

export type OverlaySession = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
  high: number;
  low: number;
  color: string;
};

export type OverlayDayPeriod = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
  kind: string;
  variant: "even" | "odd";
};

export type OverlayMonthSeparator = {
  id: string;
  time: string;
  label: string;
};

export type OverlayDayCloseSegment = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
  price: number;
  color: string;
  style: "solid" | "dashed" | "dotted";
};

export type OverlayDayRangePipe = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
  high: number;
  low: number;
  color: string;
};

export type OverlayCibMarker = {
  id: string;
  time: string;
  open: number;
  close: number;
  direction: "green" | "red";
  color: string;
};

export type OverlayLabel = {
  time: string;
  price?: number;
  label: string;
  kind: string;
};

export type OverlayResponse = {
  symbol: string;
  timeframe: string;
  levels: OverlayLevel[];
  sessions: OverlaySession[];
  day_periods: OverlayDayPeriod[];
  month_separators: OverlayMonthSeparator[];
  day_range_pipes: OverlayDayRangePipe[];
  day_close_segments: OverlayDayCloseSegment[];
  cib_markers: OverlayCibMarker[];
  day_labels: OverlayLabel[];
  setup_labels: OverlayLabel[];
  notes: string[];
};

export type RuntimeSettings = {
  update_interval_minutes: number;
};

export type TelegramStatus = {
  enabled: boolean;
  configured: boolean;
  ready: boolean;
  token_configured: boolean;
  chat_id_configured: boolean;
  sent?: boolean;
  message_id?: number | null;
};

export type DailyChecklistRow = {
  symbol: string;
  last_candle_time: string;
  day_of_week: string;
  direction: string;
  day_count: number;
  signal_days: string[];
  previous_signal_days: string[];
  weekly_template_state: string;
  price_location: string[];
  candidate_direction: string;
  quality_score: number;
  no_trade_reasons: string[];
  context: Record<string, number | null>;
  setup_checklist: string[];
};

export type WeeklyMatrixColumn = {
  key: string;
  label: string;
  date: string;
};

export type WeeklyMatrixCell = {
  date: string;
  text: string;
  labels: string[];
  direction: string;
  tone: "bullish" | "bearish" | "inside" | "neutral" | "empty";
  strength: "none" | "normal" | "signal" | "strong";
};

export type WeeklyMatrixRow = {
  symbol: string;
  highlight: boolean;
  cells: WeeklyMatrixCell[];
};

export type WeeklyMatrix = {
  columns: WeeklyMatrixColumn[];
  rows: WeeklyMatrixRow[];
};

export type DailyChecklistSession = {
  id: string;
  label: string;
  time: string;
  focus: string;
};

export type DailyChecklistManualCheck = {
  id: string;
  label: string;
};

export type DailyChecklistState = {
  date: string;
  symbol: string | null;
  checks: Record<string, boolean>;
  journal: {
    did_trade?: string;
    setup_grade?: string;
    result?: string;
    mistake_tag?: string;
    notes?: string;
  };
};

export type DailyChecklistResponse = {
  date: string | null;
  generated_at: string;
  rows: DailyChecklistRow[];
  weekly_matrix: WeeklyMatrix;
  sessions: DailyChecklistSession[];
  manual_checks: DailyChecklistManualCheck[];
  state: DailyChecklistState;
};

export type ResearchAIStatus = {
  configured: boolean;
  mode: "ai" | "retrieval";
  model: string;
  message: string;
};

export type ResearchStatus = {
  ready: boolean;
  documents: number;
  pages: number;
  chunks: number;
  indexed_at: string | null;
  embedding_provider: string;
  embedding_model: string;
  docs_dir: string;
  setup_types: string[];
  ai: ResearchAIStatus;
};

export type ResearchDocument = {
  id: string;
  path: string;
  title: string;
  category: string;
  pages: number;
  setup_types: string[];
  indexed_at: string;
};

export type ResearchResult = {
  citation: string;
  score: number;
  document_id: string;
  document_title: string;
  category: string;
  page: number;
  setup_types: string[];
  excerpt: string;
  visual_only: boolean;
};

export type ResearchSearchResponse = {
  query: string;
  count: number;
  results: ResearchResult[];
};

export type ChartImageIndexStatus = {
  ready: boolean;
  documents: number;
  images: number;
  indexed_at: string | null;
  vectorizer: string;
  docs_dir: string;
};

export type ChartImageMatch = {
  rank: number;
  similarity: number;
  similarity_percent: number;
  example_id: string;
  document_id: string;
  document_title: string;
  source_path: string;
  page: number;
  chart_index: number;
  width: number;
  height: number;
  setup_types: string[];
};

export type ChartImageMatchResponse = {
  method: "visual-structure-v1";
  count: number;
  corpus_images: number;
  matches: ChartImageMatch[];
};

export type ResearchToolTrace = {
  name: string;
  status: string;
  detail: string;
};

export type ResearchAnalysisResponse = {
  mode: "ai" | "retrieval";
  model: string | null;
  answer: string;
  sources: ResearchResult[];
  tools: ResearchToolTrace[];
  warning: string | null;
};

export type VisionAnalysisResponse = {
  mode: "ai" | "preview";
  model: string | null;
  answer: string;
  document: ResearchDocument;
  page: number;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? defaultApiBaseUrl();

export async function fetchSummary(): Promise<CandleSummary[]> {
  return fetchJson<CandleSummary[]>("/candles/summary");
}

export async function fetchCandles(
  symbol: string,
  timeframe: string,
  options: { start?: string; end?: string; limit?: number } = {},
): Promise<CandleResponse> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
  });
  if (options.start) params.set("start", options.start);
  if (options.end) params.set("end", options.end);
  if (options.limit) params.set("limit", String(options.limit));
  return fetchJson<CandleResponse>(`/candles?${params.toString()}`);
}

export async function fetchOverlays(
  symbol: string,
  timeframe: string,
  options: { start?: string; end?: string; limit?: number } = {},
): Promise<OverlayResponse> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
  });
  if (options.start) params.set("start", options.start);
  if (options.end) params.set("end", options.end);
  if (options.limit) params.set("limit", String(options.limit));
  return fetchJson<OverlayResponse>(`/context/overlays?${params.toString()}`);
}

export async function fetchRuntimeSettings(): Promise<RuntimeSettings> {
  return fetchJson<RuntimeSettings>("/runtime/settings");
}

export async function updateRuntimeSettings(settings: RuntimeSettings): Promise<RuntimeSettings> {
  return fetchJson<RuntimeSettings>("/runtime/settings", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });
}

export async function fetchTelegramStatus(): Promise<TelegramStatus> {
  return fetchJson<TelegramStatus>("/notifications/telegram/status");
}

export async function sendTelegramTest(): Promise<TelegramStatus> {
  return fetchJson<TelegramStatus>("/notifications/telegram/test", {
    method: "POST",
  });
}

export async function fetchDailyChecklist(date?: string): Promise<DailyChecklistResponse> {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<DailyChecklistResponse>(`/daily-checklist${suffix}`);
}

export async function updateDailyChecklistState(
  state: DailyChecklistState,
): Promise<DailyChecklistState> {
  return fetchJson<DailyChecklistState>("/daily-checklist/state", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(state),
  });
}

export async function fetchResearchStatus(): Promise<ResearchStatus> {
  return fetchJson<ResearchStatus>("/research/status");
}

export async function indexResearchLibrary(rebuild = false): Promise<ResearchStatus> {
  return fetchJson<ResearchStatus>("/research/index", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ rebuild }),
  });
}

export async function fetchResearchDocuments(
  options: { category?: string; setup?: string } = {},
): Promise<ResearchDocument[]> {
  const params = new URLSearchParams();
  if (options.category) params.set("category", options.category);
  if (options.setup) params.set("setup", options.setup);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<ResearchDocument[]>(`/research/documents${suffix}`);
}

export async function searchResearch(
  query: string,
  options: { category?: string; setup?: string; limit?: number } = {},
): Promise<ResearchSearchResponse> {
  const params = new URLSearchParams({ query });
  if (options.category) params.set("category", options.category);
  if (options.setup) params.set("setup", options.setup);
  if (options.limit) params.set("limit", String(options.limit));
  return fetchJson<ResearchSearchResponse>(`/research/search?${params.toString()}`);
}

export async function fetchChartImageIndexStatus(): Promise<ChartImageIndexStatus> {
  return fetchJson<ChartImageIndexStatus>("/research/image-matches/status");
}

export async function buildChartImageIndex(
  rebuild = false,
): Promise<ChartImageIndexStatus> {
  return fetchJson<ChartImageIndexStatus>("/research/image-matches/index", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ rebuild }),
  });
}

export async function searchChartImages(
  imageData: string,
  limit = 5,
): Promise<ChartImageMatchResponse> {
  return fetchJson<ChartImageMatchResponse>("/research/image-matches", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ image_data: imageData, limit }),
  });
}

export function chartImageUrl(exampleId: string): string {
  return `${API_BASE_URL}/research/chart-images/${encodeURIComponent(exampleId)}`;
}

export async function analyzeResearch(payload: {
  question: string;
  symbol?: string;
  timeframe?: string;
  setup?: string;
}): Promise<ResearchAnalysisResponse> {
  return fetchJson<ResearchAnalysisResponse>("/research/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function analyzeResearchPage(payload: {
  document_id: string;
  page: number;
  question?: string;
}): Promise<VisionAnalysisResponse> {
  return fetchJson<VisionAnalysisResponse>("/research/vision", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function researchDocumentUrl(documentId: string, page?: number) {
  const suffix = page ? `#page=${page}` : "";
  return `${API_BASE_URL}/research/documents/${encodeURIComponent(documentId)}/file${suffix}`;
}

export function researchPageImageUrl(documentId: string, page: number) {
  return `${API_BASE_URL}/research/documents/${encodeURIComponent(documentId)}/pages/${page}.png`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function defaultApiBaseUrl() {
  return `${window.location.protocol}//${window.location.hostname}:8010`;
}
