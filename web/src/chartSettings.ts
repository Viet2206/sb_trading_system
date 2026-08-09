export type LineStyle = "solid" | "dashed" | "dotted";

export type ChartSettings = {
  horizontalLevelColor: string;
  horizontalLevelStyle: LineStyle;
  previousCloseColor: string;
  previousCloseStyle: LineStyle;
  previousRangePipeColor: string;
  previousRangePipeStyle: LineStyle;
  previousRangePipeCornerRadius: number;
  asiaSessionFillColor: string;
  londonSessionFillColor: string;
  newYorkSessionFillColor: string;
  daySeparatorColor: string;
  monthSeparatorColor: string;
  weekdayLabelColor: string;
  signalLabelColor: string;
  cibBullishColor: string;
  cibBearishColor: string;
  ema9Color: string;
  ema21Color: string;
  ema50Color: string;
  ema100Color: string;
  ema200Color: string;
  sonicDragonHighColor: string;
  sonicDragonCloseColor: string;
  sonicDragonLowColor: string;
  sonicTrendColor: string;
  sonicRsiColor: string;
  sonicRsiPeriod: number;
  majorRoundNumberColor: string;
  majorRoundNumberStyle: LineStyle;
  majorRoundFxInterval: number;
  majorRoundJpyInterval: number;
  majorRoundGoldInterval: number;
  majorRoundNas100Interval: number;
  majorRoundSp500Interval: number;
  majorRoundDefaultInterval: number;
  rightOffsetBars: number;
  updateIntervalMinutes: number;
};

const STORAGE_KEY = "sb-system-chart-settings-v1";

export const defaultChartSettings: ChartSettings = {
  horizontalLevelColor: "#8e8f90",
  horizontalLevelStyle: "solid",
  previousCloseColor: "#16a34a",
  previousCloseStyle: "solid",
  previousRangePipeColor: "#64748b",
  previousRangePipeStyle: "dashed",
  previousRangePipeCornerRadius: 7,
  asiaSessionFillColor: "#bae6fd",
  londonSessionFillColor: "#bbf7d0",
  newYorkSessionFillColor: "#fed7aa",
  daySeparatorColor: "#cbd5e1",
  monthSeparatorColor: "#64748b",
  weekdayLabelColor: "#b30000",
  signalLabelColor: "#ff0000",
  cibBullishColor: "#16a34a",
  cibBearishColor: "#ef4444",
  ema9Color: "#dc2626",
  ema21Color: "#2563eb",
  ema50Color: "#16a34a",
  ema100Color: "#9333ea",
  ema200Color: "#d97706",
  sonicDragonHighColor: "#0f766e",
  sonicDragonCloseColor: "#14b8a6",
  sonicDragonLowColor: "#0f766e",
  sonicTrendColor: "#dc2626",
  sonicRsiColor: "#2563eb",
  sonicRsiPeriod: 14,
  majorRoundNumberColor: "#64748b",
  majorRoundNumberStyle: "solid",
  majorRoundFxInterval: 0.01,
  majorRoundJpyInterval: 1,
  majorRoundGoldInterval: 100,
  majorRoundNas100Interval: 100,
  majorRoundSp500Interval: 100,
  majorRoundDefaultInterval: 100,
  rightOffsetBars: 20,
  updateIntervalMinutes: 5,
};

export function loadChartSettings(): ChartSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultChartSettings;
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return defaultChartSettings;
  }
}

export function saveChartSettings(settings: ChartSettings) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function lineDashArray(style: LineStyle) {
  if (style === "dashed") return "5 4";
  if (style === "dotted") return "1 4";
  return undefined;
}

function sanitizeSettings(value: Partial<ChartSettings>): ChartSettings {
  return {
    ...defaultChartSettings,
    ...value,
    horizontalLevelStyle: sanitizeLineStyle(value.horizontalLevelStyle),
    previousCloseStyle: sanitizeLineStyle(value.previousCloseStyle),
    previousRangePipeStyle: sanitizeLineStyle(value.previousRangePipeStyle),
    majorRoundNumberStyle: sanitizeLineStyle(value.majorRoundNumberStyle),
    previousRangePipeCornerRadius: sanitizeCornerRadius(
      value.previousRangePipeCornerRadius,
    ),
    majorRoundFxInterval: sanitizePositiveNumber(
      value.majorRoundFxInterval,
      defaultChartSettings.majorRoundFxInterval,
    ),
    majorRoundJpyInterval: sanitizePositiveNumber(
      value.majorRoundJpyInterval,
      defaultChartSettings.majorRoundJpyInterval,
    ),
    majorRoundGoldInterval: sanitizePositiveNumber(
      value.majorRoundGoldInterval,
      defaultChartSettings.majorRoundGoldInterval,
    ),
    majorRoundNas100Interval: sanitizePositiveNumber(
      value.majorRoundNas100Interval,
      defaultChartSettings.majorRoundNas100Interval,
    ),
    majorRoundSp500Interval: sanitizePositiveNumber(
      value.majorRoundSp500Interval,
      defaultChartSettings.majorRoundSp500Interval,
    ),
    majorRoundDefaultInterval: sanitizePositiveNumber(
      value.majorRoundDefaultInterval,
      defaultChartSettings.majorRoundDefaultInterval,
    ),
    sonicRsiPeriod: sanitizeRsiPeriod(value.sonicRsiPeriod),
    rightOffsetBars: sanitizeOffset(value.rightOffsetBars),
    updateIntervalMinutes: sanitizeInterval(value.updateIntervalMinutes),
  };
}

function sanitizeLineStyle(value: unknown): LineStyle {
  return value === "solid" || value === "dashed" || value === "dotted"
    ? value
    : "solid";
}

function sanitizeOffset(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(40, Math.max(0, Math.round(value)))
    : defaultChartSettings.rightOffsetBars;
}

function sanitizeCornerRadius(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(16, Math.max(0, Math.round(value)))
    : defaultChartSettings.previousRangePipeCornerRadius;
}

function sanitizeInterval(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(60, Math.max(1, Math.round(value)))
    : defaultChartSettings.updateIntervalMinutes;
}

function sanitizeRsiPeriod(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(100, Math.max(2, Math.round(value)))
    : defaultChartSettings.sonicRsiPeriod;
}

function sanitizePositiveNumber(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : fallback;
}
