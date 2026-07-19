CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS market.symbols (
    symbol_id BIGSERIAL PRIMARY KEY,
    broker_symbol TEXT NOT NULL UNIQUE,
    base_symbol TEXT,
    description TEXT,
    digits INTEGER,
    point NUMERIC,
    trade_contract_size NUMERIC,
    currency_base TEXT,
    currency_profit TEXT,
    currency_margin TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market.candles (
    candle_id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES market.symbols(symbol_id),
    timeframe TEXT NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(20, 10) NOT NULL,
    high NUMERIC(20, 10) NOT NULL,
    low NUMERIC(20, 10) NOT NULL,
    close NUMERIC(20, 10) NOT NULL,
    tick_volume BIGINT,
    spread INTEGER,
    real_volume BIGINT,
    source TEXT NOT NULL DEFAULT 'mt5',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT candles_symbol_timeframe_time_key UNIQUE (symbol_id, timeframe, candle_time)
);

CREATE INDEX IF NOT EXISTS candles_symbol_timeframe_time_idx
    ON market.candles (symbol_id, timeframe, candle_time DESC);

CREATE TABLE IF NOT EXISTS market.import_runs (
    import_run_id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    symbols TEXT[],
    timeframes TEXT[],
    started_from TIMESTAMPTZ,
    notes TEXT,
    rows_imported BIGINT NOT NULL DEFAULT 0
);

