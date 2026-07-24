from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REDIRECT_URI = "http://localhost"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create cTrader OAuth tokens and list cTrader account IDs for SB Trading System."
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with cTrader application credentials.",
    )
    parser.add_argument(
        "--redirect-uri",
        help="OAuth redirect URI. Must match the redirect URI configured in the cTrader Open API app.",
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help="Print the cTrader authorization URL to open in your browser.",
    )
    parser.add_argument(
        "--code",
        help="Authorization code from the cTrader redirect URL.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh CTRADER_ACCESS_TOKEN using CTRADER_REFRESH_TOKEN.",
    )
    parser.add_argument(
        "--accounts",
        action="store_true",
        help="List account IDs available to CTRADER_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--account-id",
        type=int,
        help="When used with --accounts --write-env, write this specific account ID to CTRADER_ACCOUNT_ID.",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Write returned token/account values into the .env file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = Path(args.env)
    load_dotenv(env_path, override=True)

    if args.write_env:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch(exist_ok=True)

    redirect_uri = args.redirect_uri or os.getenv("CTRADER_REDIRECT_URI") or DEFAULT_REDIRECT_URI

    if args.print_url:
        auth = _make_auth(redirect_uri)
        print(auth.getAuthUri())
        if args.write_env:
            _set_env(env_path, "CTRADER_REDIRECT_URI", redirect_uri)

    if args.code:
        auth = _make_auth(redirect_uri)
        token_payload = auth.getToken(args.code)
        _handle_token_payload(token_payload, env_path, args.write_env, redirect_uri)

    if args.refresh:
        refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
        if not refresh_token:
            print("Missing CTRADER_REFRESH_TOKEN. Run --code first, then save the refresh token.")
            return 1
        auth = _make_auth(redirect_uri)
        token_payload = auth.refreshToken(refresh_token)
        _handle_token_payload(token_payload, env_path, args.write_env, redirect_uri)

    if args.accounts:
        return _list_accounts(env_path, args.write_env, args.account_id)

    if not any([args.print_url, args.code, args.refresh, args.accounts]):
        print("Choose at least one action: --print-url, --code, --refresh, or --accounts.")
        return 1

    return 0


def _make_auth(redirect_uri: str):
    try:
        from ctrader_open_api import Auth
    except ImportError as exc:
        raise SystemExit(
            f"cTrader Open API package is not installed. Run: {sys.executable} -m pip install -r requirements-ctrader.txt"
        ) from exc

    client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    missing = []
    if not client_id:
        missing.append("CTRADER_CLIENT_ID")
    if not client_secret:
        missing.append("CTRADER_CLIENT_SECRET")
    if missing:
        raise SystemExit("Missing cTrader application settings: " + ", ".join(missing))

    return Auth(client_id, client_secret, redirect_uri)


def _handle_token_payload(payload: dict, env_path: Path, write_env: bool, redirect_uri: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))

    access_token = _first_present(payload, "accessToken", "access_token")
    refresh_token = _first_present(payload, "refreshToken", "refresh_token")
    expires_in = _first_present(payload, "expiresIn", "expires_in")

    if not access_token:
        print("No access token found in cTrader response.")
        return

    print("\n.env values:")
    print(f"CTRADER_ACCESS_TOKEN={access_token}")
    if refresh_token:
        print(f"CTRADER_REFRESH_TOKEN={refresh_token}")
    if expires_in:
        print(f"CTRADER_TOKEN_EXPIRES_IN={expires_in}")
    print(f"CTRADER_REDIRECT_URI={redirect_uri}")

    if write_env:
        _set_env(env_path, "CTRADER_ACCESS_TOKEN", access_token)
        if refresh_token:
            _set_env(env_path, "CTRADER_REFRESH_TOKEN", refresh_token)
        if expires_in:
            _set_env(env_path, "CTRADER_TOKEN_EXPIRES_IN", str(expires_in))
        _set_env(env_path, "CTRADER_REDIRECT_URI", redirect_uri)
        print(f"\nUpdated {env_path}")


def _list_accounts(env_path: Path, write_env: bool, selected_account_id: int | None) -> int:
    try:
        from ctrader_open_api import Client, EndPoints, TcpProtocol
        from ctrader_open_api.messages.OpenApiMessages_pb2 import (
            ProtoOAApplicationAuthReq,
            ProtoOAGetAccountListByAccessTokenReq,
        )
        from twisted.internet import defer, reactor
    except ImportError as exc:
        print("cTrader Open API package is not installed in this Python environment.")
        print(f"Run: {sys.executable} -m pip install -r requirements-ctrader.txt")
        print(f"Import error: {exc}")
        return 1

    client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    access_token = os.getenv("CTRADER_ACCESS_TOKEN")
    host_type = os.getenv("CTRADER_HOST_TYPE", "demo").strip().lower()
    if host_type not in {"demo", "live"}:
        print("CTRADER_HOST_TYPE must be either 'demo' or 'live'.")
        return 1

    missing = []
    if not client_id:
        missing.append("CTRADER_CLIENT_ID")
    if not client_secret:
        missing.append("CTRADER_CLIENT_SECRET")
    if not access_token:
        missing.append("CTRADER_ACCESS_TOKEN")
    if missing:
        print("Missing cTrader settings: " + ", ".join(missing))
        return 1

    host = EndPoints.PROTOBUF_LIVE_HOST if host_type == "live" else EndPoints.PROTOBUF_DEMO_HOST
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    exit_code = {"value": 0}

    @defer.inlineCallbacks
    def run():
        try:
            yield client.whenConnected(failAfterFailures=1)

            app_request = ProtoOAApplicationAuthReq()
            app_request.clientId = client_id
            app_request.clientSecret = client_secret
            yield client.send(app_request, responseTimeoutInSeconds=20)

            request = ProtoOAGetAccountListByAccessTokenReq()
            request.accessToken = access_token
            response = yield client.send(request, responseTimeoutInSeconds=20)

            accounts = list(response.ctidTraderAccount)
            if not accounts:
                print("No cTrader accounts returned for this access token.")
                exit_code["value"] = 1
                return

            print("Available cTrader accounts:")
            for index, account in enumerate(accounts, start=1):
                account_type = "live" if account.isLive else "demo"
                print(
                    f"{index}. CTRADER_ACCOUNT_ID={account.ctidTraderAccountId} "
                    f"login={account.traderLogin} type={account_type}"
                )

            if write_env:
                account_id = selected_account_id
                if account_id is None and len(accounts) == 1:
                    account_id = accounts[0].ctidTraderAccountId
                if account_id is None:
                    print("\nMultiple accounts found. Re-run with --account-id <id> --write-env.")
                elif account_id not in {account.ctidTraderAccountId for account in accounts}:
                    print(f"\nAccount ID {account_id} was not returned by cTrader.")
                    exit_code["value"] = 1
                else:
                    _set_env(env_path, "CTRADER_ACCOUNT_ID", str(account_id))
                    print(f"\nUpdated {env_path} with CTRADER_ACCOUNT_ID={account_id}")
        except Exception as exc:
            exit_code["value"] = 1
            print(f"cTrader account lookup failed: {exc}")
        finally:
            client.stopService()
            reactor.stop()

    client.startService()
    reactor.callWhenRunning(run)
    reactor.run()
    return exit_code["value"]


def _first_present(payload: dict, *keys: str):
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return None


def _set_env(env_path: Path, key: str, value: str) -> None:
    set_key(env_path, key, value, quote_mode="never")


if __name__ == "__main__":
    raise SystemExit(main())
