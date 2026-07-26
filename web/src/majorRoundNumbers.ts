import { ChartSettings } from "./chartSettings";

type PriceRangePoint = {
  high: number;
  low: number;
};

export type MajorRoundNumber = {
  key: string;
  label: string;
  price: number;
};

const currencyCodes = new Set([
  "AUD",
  "CAD",
  "CHF",
  "EUR",
  "GBP",
  "JPY",
  "NZD",
  "USD",
]);

export function buildMajorRoundNumbers(
  data: PriceRangePoint[],
  symbol: string,
  settings: ChartSettings,
): MajorRoundNumber[] {
  if (!data.length) return [];

  const interval = majorRoundNumberInterval(symbol, settings);
  if (!Number.isFinite(interval) || interval <= 0) return [];

  let rangeLow = Number.POSITIVE_INFINITY;
  let rangeHigh = Number.NEGATIVE_INFINITY;
  for (const candle of data) {
    rangeLow = Math.min(rangeLow, candle.low);
    rangeHigh = Math.max(rangeHigh, candle.high);
  }
  if (!Number.isFinite(rangeLow) || !Number.isFinite(rangeHigh)) return [];

  const epsilon = interval * 1e-9;
  const firstIndex = Math.ceil((rangeLow - epsilon) / interval);
  const lastIndex = Math.floor((rangeHigh + epsilon) / interval);
  const count = lastIndex - firstIndex + 1;
  if (count <= 0 || count > 500) return [];

  const decimals = roundNumberDecimals(symbol, interval);
  return Array.from({ length: count }, (_, offset) => {
    const price = normalizedPrice((firstIndex + offset) * interval, decimals);
    return {
      key: `major-round-${price}`,
      label: `RN ${price.toFixed(decimals)}`,
      price,
    };
  });
}

export function majorRoundNumberInterval(
  symbol: string,
  settings: ChartSettings,
) {
  const normalized = normalizedSymbol(symbol);
  if (normalized.startsWith("XAUUSD")) return settings.majorRoundGoldInterval;
  if (normalized.startsWith("NAS100")) return settings.majorRoundNas100Interval;
  if (normalized.startsWith("SP500")) return settings.majorRoundSp500Interval;

  const pair = normalized.slice(0, 6);
  if (isCurrencyPair(pair)) {
    return pair.endsWith("JPY")
      ? settings.majorRoundJpyInterval
      : settings.majorRoundFxInterval;
  }

  return settings.majorRoundDefaultInterval;
}

function normalizedSymbol(symbol: string) {
  return symbol.toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function isCurrencyPair(symbol: string) {
  return symbol.length === 6
    && currencyCodes.has(symbol.slice(0, 3))
    && currencyCodes.has(symbol.slice(3, 6));
}

function roundNumberDecimals(symbol: string, interval: number) {
  const pair = normalizedSymbol(symbol).slice(0, 6);
  if (isCurrencyPair(pair)) return pair.endsWith("JPY") ? 2 : 4;
  if (interval >= 1) return 0;

  const decimalText = interval.toFixed(8).replace(/0+$/, "");
  return Math.min(8, decimalText.split(".")[1]?.length ?? 0);
}

function normalizedPrice(price: number, decimals: number) {
  return Number(price.toFixed(Math.min(10, decimals + 2)));
}
