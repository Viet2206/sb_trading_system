import { useEffect, useState } from "react";
import { RefreshCw, RotateCcw, Send } from "lucide-react";
import type { TelegramStatus } from "./api";
import {
  fetchTelegramStatus,
  sendTelegramTest,
} from "./api";
import {
  ChartSettings,
  LineStyle,
  defaultChartSettings,
} from "./chartSettings";

type SettingsPageProps = {
  settings: ChartSettings;
  onChange: (settings: ChartSettings) => void;
};

type ColorField = {
  key: keyof Pick<
    ChartSettings,
    | "horizontalLevelColor"
    | "previousCloseColor"
    | "previousRangePipeColor"
    | "asiaSessionFillColor"
    | "londonSessionFillColor"
    | "newYorkSessionFillColor"
    | "daySeparatorColor"
    | "monthSeparatorColor"
    | "weekdayLabelColor"
    | "signalLabelColor"
    | "cibBullishColor"
    | "cibBearishColor"
    | "ema9Color"
    | "ema21Color"
    | "ema50Color"
    | "ema100Color"
    | "ema200Color"
    | "sonicDragonHighColor"
    | "sonicDragonCloseColor"
    | "sonicDragonLowColor"
    | "sonicTrendColor"
    | "majorRoundNumberColor"
  >;
  label: string;
};

type StyleField = {
  key: keyof Pick<
    ChartSettings,
    | "horizontalLevelStyle"
    | "previousCloseStyle"
    | "previousRangePipeStyle"
    | "majorRoundNumberStyle"
  >;
  label: string;
};

const colorFields: ColorField[] = [
  { key: "horizontalLevelColor", label: "Context Levels (PWH/PWL/Mon/Fri)" },
  { key: "previousCloseColor", label: "Previous Day Close Segments" },
  { key: "previousRangePipeColor", label: "Previous Day High/Low Pipe" },
  { key: "asiaSessionFillColor", label: "Asia Session" },
  { key: "londonSessionFillColor", label: "London Session" },
  { key: "newYorkSessionFillColor", label: "New York Session" },
  { key: "daySeparatorColor", label: "Day Separators" },
  { key: "monthSeparatorColor", label: "Month Separators" },
  { key: "weekdayLabelColor", label: "Weekday Labels" },
  { key: "signalLabelColor", label: "Signal Labels" },
  { key: "cibBullishColor", label: "CIB Bullish Marker" },
  { key: "cibBearishColor", label: "CIB Bearish Marker" },
  { key: "ema9Color", label: "EMA 9" },
  { key: "ema21Color", label: "EMA 21" },
  { key: "ema50Color", label: "EMA 50" },
  { key: "ema100Color", label: "EMA 100" },
  { key: "ema200Color", label: "EMA 200" },
  { key: "sonicDragonHighColor", label: "Sonic R Dragon High (EMA 34)" },
  { key: "sonicDragonCloseColor", label: "Sonic R Dragon Close (EMA 34)" },
  { key: "sonicDragonLowColor", label: "Sonic R Dragon Low (EMA 34)" },
  { key: "sonicTrendColor", label: "Sonic R Trend (EMA 89)" },
  { key: "majorRoundNumberColor", label: "Major Round Numbers" },
];

const styleFields: StyleField[] = [
  { key: "horizontalLevelStyle", label: "Context Levels (PWH/PWL/Mon/Fri)" },
  { key: "previousCloseStyle", label: "Previous Day Close Segments" },
  { key: "previousRangePipeStyle", label: "Previous Day High/Low Pipe" },
  { key: "majorRoundNumberStyle", label: "Major Round Numbers" },
];

const lineStyles: LineStyle[] = ["solid", "dashed", "dotted"];

export function SettingsPage({ settings, onChange }: SettingsPageProps) {
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramBusy, setTelegramBusy] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState<string | null>(null);

  useEffect(() => {
    void refreshTelegramStatus();
  }, []);

  function update<K extends keyof ChartSettings>(key: K, value: ChartSettings[K]) {
    onChange({ ...settings, [key]: value });
  }

  function updatePositiveNumber(
    key: keyof Pick<
      ChartSettings,
      | "majorRoundFxInterval"
      | "majorRoundJpyInterval"
      | "majorRoundGoldInterval"
      | "majorRoundNas100Interval"
      | "majorRoundSp500Interval"
      | "majorRoundDefaultInterval"
    >,
    value: number,
  ) {
    if (Number.isFinite(value) && value > 0) {
      update(key, value);
    }
  }

  async function refreshTelegramStatus() {
    setTelegramBusy(true);
    setTelegramMessage(null);
    try {
      setTelegramStatus(await fetchTelegramStatus());
    } catch (error) {
      setTelegramMessage(
        error instanceof Error ? error.message : "Unable to load Telegram status.",
      );
    } finally {
      setTelegramBusy(false);
    }
  }

  async function testTelegramDelivery() {
    setTelegramBusy(true);
    setTelegramMessage(null);
    try {
      const status = await sendTelegramTest();
      setTelegramStatus(status);
      setTelegramMessage("Test message sent.");
    } catch (error) {
      setTelegramMessage(
        error instanceof Error ? error.message : "Unable to send Telegram test.",
      );
    } finally {
      setTelegramBusy(false);
    }
  }

  return (
    <div className="settings-page">
      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Overlay Colors</h3>
        </div>
        <div className="settings-grid">
          {colorFields.map((field) => (
            <label key={field.key} className="setting-row">
              <span>{field.label}</span>
              <div className="color-control">
                <input
                  type="color"
                  aria-label={`${field.label} color picker`}
                  value={settings[field.key]}
                  onInput={(event) =>
                    update(field.key, (event.target as HTMLInputElement).value)
                  }
                  onChange={(event) => update(field.key, event.target.value)}
                />
                <input
                  data-testid={`setting-${field.key}`}
                  value={settings[field.key]}
                  onChange={(event) => update(field.key, event.target.value)}
                  spellCheck={false}
                />
              </div>
            </label>
          ))}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Major Round Number Intervals</h3>
        </div>
        <div className="settings-grid compact">
          <RoundNumberInterval
            label="Non-JPY FX"
            testId="setting-majorRoundFxInterval"
            value={settings.majorRoundFxInterval}
            onChange={(value) => updatePositiveNumber("majorRoundFxInterval", value)}
          />
          <RoundNumberInterval
            label="JPY FX"
            testId="setting-majorRoundJpyInterval"
            value={settings.majorRoundJpyInterval}
            onChange={(value) => updatePositiveNumber("majorRoundJpyInterval", value)}
          />
          <RoundNumberInterval
            label="Gold"
            testId="setting-majorRoundGoldInterval"
            value={settings.majorRoundGoldInterval}
            onChange={(value) => updatePositiveNumber("majorRoundGoldInterval", value)}
          />
          <RoundNumberInterval
            label="NAS100"
            testId="setting-majorRoundNas100Interval"
            value={settings.majorRoundNas100Interval}
            onChange={(value) => updatePositiveNumber("majorRoundNas100Interval", value)}
          />
          <RoundNumberInterval
            label="SP500"
            testId="setting-majorRoundSp500Interval"
            value={settings.majorRoundSp500Interval}
            onChange={(value) => updatePositiveNumber("majorRoundSp500Interval", value)}
          />
          <RoundNumberInterval
            label="Other Markets"
            testId="setting-majorRoundDefaultInterval"
            value={settings.majorRoundDefaultInterval}
            onChange={(value) => updatePositiveNumber("majorRoundDefaultInterval", value)}
          />
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Line Styles</h3>
        </div>
        <div className="settings-grid compact">
          {styleFields.map((field) => (
            <label key={field.key} className="setting-row">
              <span>{field.label}</span>
              <select
                data-testid={`setting-${field.key}`}
                value={settings[field.key]}
                onChange={(event) => update(field.key, event.target.value as LineStyle)}
              >
                {lineStyles.map((style) => (
                  <option key={style} value={style}>
                    {style}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <label className="setting-row range-row">
          <span>Previous Day Pipe Corner Radius</span>
          <input
            data-testid="setting-previousRangePipeCornerRadius"
            type="number"
            min={0}
            max={16}
            step={1}
            value={settings.previousRangePipeCornerRadius}
            onChange={(event) =>
              update("previousRangePipeCornerRadius", Number(event.target.value))
            }
          />
        </label>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Chart Updates</h3>
        </div>
        <label className="setting-row range-row">
          <span>Update Interval Minutes</span>
          <input
            data-testid="setting-updateIntervalMinutes"
            type="number"
            min={1}
            max={60}
            step={1}
            value={settings.updateIntervalMinutes}
            onChange={(event) => update("updateIntervalMinutes", Number(event.target.value))}
          />
        </label>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Telegram Notifications</h3>
        </div>
        <div className="telegram-status-grid">
          <TelegramStatusItem
            label="Bot Token"
            active={telegramStatus?.token_configured ?? false}
          />
          <TelegramStatusItem
            label="Chat ID"
            active={telegramStatus?.chat_id_configured ?? false}
          />
          <TelegramStatusItem
            label="Delivery"
            active={telegramStatus?.ready ?? false}
            activeText="Ready"
            inactiveText={telegramStatus?.enabled ? "Incomplete" : "Disabled"}
          />
        </div>
        <div className="telegram-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void refreshTelegramStatus()}
            disabled={telegramBusy}
            title="Refresh Telegram configuration status"
          >
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void testTelegramDelivery()}
            disabled={telegramBusy || !telegramStatus?.configured}
            title="Send a fixed Telegram test message"
          >
            <Send size={16} />
            <span>Send Test</span>
          </button>
          {telegramMessage ? (
            <span className="telegram-feedback" role="status">
              {telegramMessage}
            </span>
          ) : null}
        </div>
      </section>

      <section className="settings-section">
        <div className="settings-section-title">
          <h3>Chart Space</h3>
        </div>
        <label className="setting-row range-row">
          <span>Right Offset Bars</span>
          <input
            data-testid="setting-rightOffsetBars"
            type="number"
            min={0}
            max={40}
            step={1}
            value={settings.rightOffsetBars}
            onChange={(event) => update("rightOffsetBars", Number(event.target.value))}
          />
        </label>
      </section>

      <button
        className="reset-button"
        onClick={() => onChange(defaultChartSettings)}
        title="Restore default chart settings"
      >
        <RotateCcw size={17} />
        <span>Reset Defaults</span>
      </button>
    </div>
  );
}

type RoundNumberIntervalProps = {
  label: string;
  testId: string;
  value: number;
  onChange: (value: number) => void;
};

function RoundNumberInterval({
  label,
  testId,
  value,
  onChange,
}: RoundNumberIntervalProps) {
  return (
    <label className="setting-row">
      <span>{label}</span>
      <input
        data-testid={testId}
        type="number"
        min="0.00001"
        step="any"
        value={value}
        onChange={(event) => onChange(event.target.valueAsNumber)}
      />
    </label>
  );
}

type TelegramStatusItemProps = {
  label: string;
  active: boolean;
  activeText?: string;
  inactiveText?: string;
};

function TelegramStatusItem({
  label,
  active,
  activeText = "Configured",
  inactiveText = "Missing",
}: TelegramStatusItemProps) {
  return (
    <div className="telegram-status-item">
      <span>{label}</span>
      <strong className={active ? "ready" : "not-ready"}>
        {active ? activeText : inactiveText}
      </strong>
    </div>
  );
}
