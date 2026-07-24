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
  day_labels: OverlayLabel[];
  setup_labels: OverlayLabel[];
  notes: string[];
};

export type RuntimeSettings = {
  update_interval_minutes: number;
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
  sessions: DailyChecklistSession[];
  manual_checks: DailyChecklistManualCheck[];
  state: DailyChecklistState;
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
