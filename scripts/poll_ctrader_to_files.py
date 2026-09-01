from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.ctrader import (
    CTRADER_TIMEFRAME_PERIODS,
    CTraderConfig,
    chunk_ranges,
    load_ctrader_config,
    normalize_trendbars,
    timeframe_overlap,
    utc_datetime_from_date,
    validate_ctrader_config,
)
from sb_system.file_store import latest_file_candle_time, upsert_file_candles
from sb_system.market_data import load_config
from sb_system.runtime_settings import (
    RuntimeSettings,
    load_runtime_settings,
    save_runtime_settings,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll cTrader Open API trendbars into local SB Trading System files."
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with cTrader credentials and SB storage settings.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cTrader update cycle, then exit.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        help="Set the shared update interval used by this script and the UI.",
    )
    parser.add_argument(
        "--lookback-candles",
        type=int,
        default=10,
        help="Re-request this many candles before the latest saved candle to update the active candle safely.",
    )
    parser.add_argument(
        "--max-bars-per-request",
        type=int,
        default=20_000,
        help="Maximum trendbars requested per cTrader API request.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval_minutes is not None:
        save_runtime_settings(RuntimeSettings(update_interval_minutes=args.interval_minutes))

    storage_config = load_config(args.env, require_database_url=False)
    ctrader_config = load_ctrader_config(args.env)
    try:
        validate_ctrader_config(ctrader_config)
    except ValueError as exc:
        print(exc)
        print("Docs: https://help.ctrader.com/open-api/")
        return 1

    try:
        return run_twisted_poller(args, storage_config, ctrader_config)
    except ImportError as exc:
        print("cTrader Open API package is not installed in this Python environment.")
        print(f'Run: "{sys.executable}" -m pip install -r requirements-ctrader.txt')
        print(f"Import error: {exc}")
        return 1


def run_twisted_poller(args: argparse.Namespace, storage_config, ctrader_config: CTraderConfig) -> int:
    from ctrader_open_api import Client, EndPoints, TcpProtocol
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAAccountAuthReq,
        ProtoOAApplicationAuthReq,
        ProtoOAGetTrendbarsReq,
        ProtoOASymbolByIdReq,
        ProtoOASymbolsListReq,
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
    from twisted.internet import defer, reactor, task

    host = (
        EndPoints.PROTOBUF_LIVE_HOST
        if ctrader_config.host_type == "live"
        else EndPoints.PROTOBUF_DEMO_HOST
    )
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    exit_code = {"value": 0}

    @defer.inlineCallbacks
    def poll_loop():
        try:
            yield client.whenConnected(failAfterFailures=1)
            yield _authenticate(client, ctrader_config, ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq)
            symbol_index = yield _load_symbol_index(
                client,
                ctrader_config,
                ProtoOASymbolsListReq,
                ProtoOASymbolByIdReq,
            )
            _print_startup(storage_config, ctrader_config)

            while True:
                rows = yield _poll_once(
                    client,
                    storage_config,
                    ctrader_config,
                    symbol_index,
                    ProtoOAGetTrendbarsReq,
                    ProtoOATrendbarPeriod,
                    lookback_candles=args.lookback_candles,
                    max_bars_per_request=args.max_bars_per_request,
                )
                print(f"{datetime.now(timezone.utc).isoformat()} updated {rows} candles from cTrader")

                if args.once:
                    break

                interval_minutes = load_runtime_settings().update_interval_minutes
                print(f"Next cTrader update in {interval_minutes} minute(s)")
                yield task.deferLater(reactor, interval_minutes * 60, lambda: None)
        except Exception as exc:
            exit_code["value"] = 1
            print(f"cTrader polling failed: {exc}")
        finally:
            client.stopService()
            reactor.stop()

    client.startService()
    reactor.callWhenRunning(poll_loop)
    reactor.run()
    return exit_code["value"]


def _authenticate(client, config: CTraderConfig, application_auth_cls, account_auth_cls):
    from twisted.internet import defer

    @defer.inlineCallbacks
    def _inner():
        app_request = application_auth_cls()
        app_request.clientId = config.client_id or ""
        app_request.clientSecret = config.client_secret or ""
        yield client.send(app_request, responseTimeoutInSeconds=20)

        account_request = account_auth_cls()
        account_request.ctidTraderAccountId = config.account_id
        account_request.accessToken = config.access_token or ""
        yield client.send(account_request, responseTimeoutInSeconds=20)

    return _inner()


def _load_symbol_index(client, config: CTraderConfig, symbols_list_cls, symbol_by_id_cls):
    from twisted.internet import defer

    @defer.inlineCallbacks
    def _inner():
        request = symbols_list_cls()
        request.ctidTraderAccountId = config.account_id
        symbols_response = yield client.send(request, responseTimeoutInSeconds=30)

        light_symbols = {symbol.symbolName: symbol for symbol in symbols_response.symbol}
        casefold_symbols = {name.casefold(): symbol for name, symbol in light_symbols.items()}
        selected = {}
        for symbol_name in config.symbols:
            light_symbol = light_symbols.get(symbol_name) or casefold_symbols.get(symbol_name.casefold())
            if light_symbol is None:
                print(f"SKIP {symbol_name}: cTrader symbol not found for this account")
                continue
            selected[symbol_name] = light_symbol

        if not selected:
            raise RuntimeError("None of the configured CTRADER_SYMBOLS were found in this cTrader account.")

        details_request = symbol_by_id_cls()
        details_request.ctidTraderAccountId = config.account_id
        details_request.symbolId.extend([symbol.symbolId for symbol in selected.values()])
        details_response = yield client.send(details_request, responseTimeoutInSeconds=30)
        details_by_id = {symbol.symbolId: symbol for symbol in details_response.symbol}

        return {
            requested_name: {
                "symbol_id": light_symbol.symbolId,
                "symbol_name": light_symbol.symbolName,
                "digits": details_by_id.get(light_symbol.symbolId).digits if light_symbol.symbolId in details_by_id else 5,
            }
            for requested_name, light_symbol in selected.items()
        }

    return _inner()


def _poll_once(
    client,
    storage_config,
    ctrader_config: CTraderConfig,
    symbol_index: dict,
    trendbars_req_cls,
    trendbar_period,
    *,
    lookback_candles: int,
    max_bars_per_request: int,
):
    from twisted.internet import defer

    @defer.inlineCallbacks
    def _inner():
        date_to = datetime.now(timezone.utc)
        import_start = max(
            utc_datetime_from_date(ctrader_config.import_start),
            utc_datetime_from_date(storage_config.import_start),
        )
        total_rows = 0

        for symbol_info in symbol_index.values():
            symbol_name = symbol_info["symbol_name"]
            for timeframe in ctrader_config.timeframes:
                period_name = CTRADER_TIMEFRAME_PERIODS.get(timeframe)
                if period_name is None:
                    print(f"SKIP {symbol_name} {timeframe}: unsupported cTrader timeframe")
                    continue

                date_from = _next_fetch_start(
                    storage_config.data_dir,
                    symbol=symbol_name,
                    timeframe=timeframe,
                    file_format=storage_config.file_format,
                    import_start=import_start,
                    lookback_candles=lookback_candles,
                )
                rows_for_pair = 0
                for chunk_start, chunk_end in chunk_ranges(
                    date_from,
                    date_to,
                    timeframe=timeframe,
                    chunk_days=ctrader_config.chunk_days,
                ):
                    request = trendbars_req_cls()
                    request.ctidTraderAccountId = ctrader_config.account_id
                    request.symbolId = symbol_info["symbol_id"]
                    request.period = trendbar_period.Value(period_name)
                    request.fromTimestamp = int(chunk_start.timestamp() * 1000)
                    request.toTimestamp = int(chunk_end.timestamp() * 1000)
                    request.count = max_bars_per_request
                    response = yield client.send(request, responseTimeoutInSeconds=60)
                    trendbars = getattr(response, "trendbar", getattr(response, "trendbars", []))
                    candles = normalize_trendbars(
                        trendbars,
                        symbol=symbol_name,
                        timeframe=timeframe,
                        digits=symbol_info["digits"],
                    )
                    rows_for_pair += upsert_file_candles(
                        storage_config.data_dir,
                        candles,
                        file_format=storage_config.file_format,
                        retain_from=import_start,
                    )

                total_rows += rows_for_pair
                print(f"{symbol_name:14} {timeframe:4} {rows_for_pair:8} candles from {date_from.isoformat()}")

        return total_rows

    return _inner()


def _next_fetch_start(
    data_dir: Path,
    *,
    symbol: str,
    timeframe: str,
    file_format: str,
    import_start: datetime,
    lookback_candles: int,
) -> datetime:
    latest = latest_file_candle_time(
        data_dir,
        symbol=symbol,
        timeframe=timeframe,
        file_format=file_format,
    )
    if latest is None:
        return import_start
    return max(import_start, latest.to_pydatetime() - timeframe_overlap(timeframe, lookback_candles))


def _print_startup(storage_config, ctrader_config: CTraderConfig) -> None:
    print(f"cTrader host: {ctrader_config.host_type}")
    print(f"Storage: {storage_config.storage}")
    print(f"Data dir: {storage_config.data_dir}")
    print(f"File format: {storage_config.file_format}")
    print(f"Symbols: {', '.join(ctrader_config.symbols)}")
    print(f"Timeframes: {', '.join(ctrader_config.timeframes)}")
    print("Press Ctrl+C to stop.")


if __name__ == "__main__":
    raise SystemExit(main())
