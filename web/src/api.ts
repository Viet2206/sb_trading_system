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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchSummary(): Promise<CandleSummary[]> {
  return fetchJson<CandleSummary[]>("/candles/summary");
}

export async function fetchCandles(
  symbol: string,
  timeframe: string,
  limit = 1000,
): Promise<CandleResponse> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
    limit: String(limit),
  });
  return fetchJson<CandleResponse>(`/candles?${params.toString()}`);
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}
