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

export type OverlayDayCloseSegment = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
  price: number;
  color: string;
  style: "solid" | "dashed" | "dotted";
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
  day_close_segments: OverlayDayCloseSegment[];
  day_labels: OverlayLabel[];
  setup_labels: OverlayLabel[];
  notes: string[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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
    limit: String(options.limit ?? 1000),
  });
  if (options.start) params.set("start", options.start);
  if (options.end) params.set("end", options.end);
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
    limit: String(options.limit ?? 1500),
  });
  if (options.start) params.set("start", options.start);
  if (options.end) params.set("end", options.end);
  return fetchJson<OverlayResponse>(`/context/overlays?${params.toString()}`);
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}
