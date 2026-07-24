import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  RefreshCw,
  Save,
} from "lucide-react";
import {
  DailyChecklistResponse,
  DailyChecklistRow,
  DailyChecklistState,
  WeeklyMatrix,
  fetchDailyChecklist,
  updateDailyChecklistState,
} from "./api";

const emptyState: DailyChecklistState = {
  date: "",
  symbol: null,
  checks: {},
  journal: {
    did_trade: "no",
    setup_grade: "",
    result: "",
    mistake_tag: "",
    notes: "",
  },
};

export function DailyChecklistPage() {
  const [data, setData] = useState<DailyChecklistResponse | null>(null);
  const [state, setState] = useState<DailyChecklistState>(emptyState);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRow = useMemo(() => {
    if (!data) return null;
    return data.rows.find((row) => row.symbol === selectedSymbol) ?? data.rows[0] ?? null;
  }, [data, selectedSymbol]);

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!data) return;
    const savedSymbol = data.state.symbol;
    const nextSymbol = savedSymbol && data.rows.some((row) => row.symbol === savedSymbol)
      ? savedSymbol
      : data.rows[0]?.symbol ?? "";
    setSelectedSymbol(nextSymbol);
    setState({
      ...emptyState,
      ...data.state,
      date: data.date ?? data.state.date,
      symbol: nextSymbol || data.state.symbol,
      checks: { ...emptyState.checks, ...data.state.checks },
      journal: { ...emptyState.journal, ...data.state.journal },
    });
  }, [data]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const nextData = await fetchDailyChecklist();
      setData(nextData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load daily checklist");
    } finally {
      setLoading(false);
    }
  }

  async function save(nextState = state) {
    if (!nextState.date) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await updateDailyChecklistState(nextState);
      setState(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save checklist");
    } finally {
      setSaving(false);
    }
  }

  function chooseSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    setState((current) => ({ ...current, symbol }));
  }

  function updateCheck(id: string, value: boolean) {
    setState((current) => ({
      ...current,
      checks: { ...current.checks, [id]: value },
    }));
  }

  function updateJournal(key: keyof DailyChecklistState["journal"], value: string) {
    setState((current) => ({
      ...current,
      journal: { ...current.journal, [key]: value },
    }));
  }

  if (loading && !data) {
    return <div className="checklist-page"><div className="checklist-empty">Loading checklist</div></div>;
  }

  if (!data || data.rows.length === 0) {
    return (
      <div className="checklist-page">
        {error ? <div className="inline-error">{error}</div> : null}
        <div className="checklist-empty">No D1 candles available for checklist scan.</div>
      </div>
    );
  }

  return (
    <div className="checklist-page">
      <div className="checklist-actions">
        <div>
          <h3>{formatDate(data.date)}</h3>
          <p>{data.rows.length} markets scanned</p>
        </div>
        <div className="checklist-action-buttons">
          <button className="small-action-button" onClick={() => void load()} title="Refresh checklist">
            <RefreshCw size={16} />
            <span>{loading ? "Loading" : "Refresh"}</span>
          </button>
          <button className="small-action-button primary" onClick={() => void save()} title="Save checklist">
            <Save size={16} />
            <span>{saving ? "Saving" : "Save"}</span>
          </button>
        </div>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <section className="weekly-matrix-section">
        <div className="weekly-matrix-title">
          <span />
          <strong>Day Signal</strong>
        </div>
        <WeeklyTemplateMatrix
          matrix={data.weekly_matrix}
          selectedSymbol={selectedSymbol}
          onSelectSymbol={chooseSymbol}
        />
      </section>

      <section className="scan-section">
        <div className="section-heading">
          <h3>Market Scan</h3>
        </div>
        <div className="scan-table-wrap">
          <table className="scan-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Signal</th>
                <th>Direction</th>
                <th>Weekly</th>
                <th>Location</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr
                  key={row.symbol}
                  className={row.symbol === selectedSymbol ? "selected" : ""}
                  onClick={() => chooseSymbol(row.symbol)}
                >
                  <td>
                    <button className="symbol-pick-button" onClick={() => chooseSymbol(row.symbol)}>
                      {row.symbol}
                    </button>
                  </td>
                  <td>{tagList([...row.signal_days, ...row.previous_signal_days])}</td>
                  <td>{row.candidate_direction}</td>
                  <td>{row.weekly_template_state}</td>
                  <td>{compactList(row.price_location)}</td>
                  <td>
                    <Score value={row.quality_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedRow ? (
        <div className="checklist-grid">
          <section className="checklist-panel context-panel">
            <PanelTitle icon={<ClipboardCheck size={17} />} title={`${selectedRow.symbol} Context`} />
            <div className="context-grid">
              <Metric label="Day" value={`${selectedRow.day_of_week} / ${selectedRow.direction} ${selectedRow.day_count}`} />
              <Metric label="Close" value={formatPrice(selectedRow.context.close)} />
              <Metric label="PDH" value={formatPrice(selectedRow.context.previous_day_high)} />
              <Metric label="PDL" value={formatPrice(selectedRow.context.previous_day_low)} />
              <Metric label="PDC" value={formatPrice(selectedRow.context.previous_day_close)} />
              <Metric label="PWH" value={formatPrice(selectedRow.context.previous_week_high)} />
              <Metric label="PWL" value={formatPrice(selectedRow.context.previous_week_low)} />
              <Metric label="Mon High" value={formatPrice(selectedRow.context.monday_high)} />
              <Metric label="Mon Low" value={formatPrice(selectedRow.context.monday_low)} />
              <Metric label="Fri Close" value={formatPrice(selectedRow.context.friday_close)} />
            </div>
          </section>

          <section className="checklist-panel">
            <PanelTitle icon={<CheckCircle2 size={17} />} title="Signal Day" />
            <div className="auto-checks">
              {selectedRow.setup_checklist.map((item) => (
                <div key={item} className="auto-check-row">
                  <Circle size={13} />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="checklist-panel">
            <PanelTitle icon={<Circle size={17} />} title="Session Plan" />
            <div className="session-plan-list">
              {data.sessions.map((session) => (
                <div key={session.id} className="session-plan-row">
                  <div>
                    <strong>{session.label}</strong>
                    <span>{session.time}</span>
                  </div>
                  <p>{session.focus}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="checklist-panel">
            <PanelTitle icon={<CheckCircle2 size={17} />} title="Entry Readiness" />
            <div className="manual-checks">
              {data.manual_checks.map((item) => (
                <label key={item.id} className="manual-check-row">
                  <input
                    type="checkbox"
                    checked={Boolean(state.checks[item.id])}
                    onChange={(event) => updateCheck(item.id, event.target.checked)}
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="checklist-panel">
            <PanelTitle icon={<AlertTriangle size={17} />} title="No-Trade Reasons" />
            <div className="reason-list">
              {(selectedRow.no_trade_reasons.length ? selectedRow.no_trade_reasons : ["No automatic block"]).map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
          </section>

          <section className="checklist-panel journal-panel">
            <PanelTitle icon={<ClipboardCheck size={17} />} title="Daily Journal" />
            <div className="journal-grid">
              <label>
                <span>Did Trade</span>
                <select
                  value={state.journal.did_trade ?? "no"}
                  onChange={(event) => updateJournal("did_trade", event.target.value)}
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </label>
              <label>
                <span>Setup Grade</span>
                <select
                  value={state.journal.setup_grade ?? ""}
                  onChange={(event) => updateJournal("setup_grade", event.target.value)}
                >
                  <option value="">Unrated</option>
                  <option value="A+">A+</option>
                  <option value="A">A</option>
                  <option value="B">B</option>
                  <option value="C">C</option>
                  <option value="Garbage">Garbage</option>
                </select>
              </label>
              <label>
                <span>Result</span>
                <input
                  value={state.journal.result ?? ""}
                  onChange={(event) => updateJournal("result", event.target.value)}
                  placeholder="No trade / +50 / -15"
                />
              </label>
              <label>
                <span>Mistake Tag</span>
                <input
                  value={state.journal.mistake_tag ?? ""}
                  onChange={(event) => updateJournal("mistake_tag", event.target.value)}
                  placeholder="FOMO, early, news, late"
                />
              </label>
              <label className="journal-notes">
                <span>Notes</span>
                <textarea
                  value={state.journal.notes ?? ""}
                  onChange={(event) => updateJournal("notes", event.target.value)}
                  rows={4}
                />
              </label>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function WeeklyTemplateMatrix({
  matrix,
  selectedSymbol,
  onSelectSymbol,
}: {
  matrix: WeeklyMatrix;
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
}) {
  if (matrix.rows.length === 0) {
    return <div className="checklist-empty">No weekly matrix data available.</div>;
  }

  return (
    <div className="weekly-matrix-wrap">
      <table className="weekly-matrix-table">
        <thead>
          <tr>
            <th>Symbol</th>
            {matrix.columns.map((column) => (
              <th key={column.key} title={column.date}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row) => (
            <tr
              key={row.symbol}
              className={row.symbol === selectedSymbol ? "selected" : ""}
              onClick={() => onSelectSymbol(row.symbol)}
            >
              <td className={row.highlight ? "matrix-symbol highlighted" : "matrix-symbol"}>
                <button onClick={() => onSelectSymbol(row.symbol)}>{row.symbol}</button>
              </td>
              {row.cells.map((cell) => (
                <td
                  key={`${row.symbol}-${cell.date}`}
                  className={`matrix-cell tone-${cell.tone} strength-${cell.strength}`}
                  title={`${cell.date}${cell.labels.length ? ` / ${cell.labels.join(", ")}` : ""}`}
                >
                  {cell.text}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="panel-title">
      {icon}
      <h3>{title}</h3>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Score({ value }: { value: number }) {
  return (
    <div className="score-pill">
      <span style={{ width: `${value}%` }} />
      <strong>{value}</strong>
    </div>
  );
}

function tagList(values: string[]) {
  const unique = Array.from(new Set(values));
  if (unique.length === 0) return <span className="muted-cell">None</span>;
  return (
    <div className="tag-list">
      {unique.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </div>
  );
}

function compactList(values: string[]) {
  return values.length ? values.slice(0, 2).join(", ") : "None";
}

function formatDate(value: string | null) {
  if (!value) return "Daily Checklist";
  return new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function formatPrice(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: value >= 10 ? 2 : 5,
    maximumFractionDigits: value >= 10 ? 2 : 5,
  });
}
