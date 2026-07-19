from __future__ import annotations

import platform
import sys


def main() -> int:
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.architecture()[0]}")

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 import: FAILED")
        print("Install it into this exact Python environment with:")
        print(f'"{sys.executable}" -m pip install -r requirements-win-mt5.txt')
        return 1

    print(f"MetaTrader5 import: OK ({mt5.__version__})")

    if not mt5.initialize():
        print(f"MT5 initialize: FAILED {mt5.last_error()}")
        print("Open MetaTrader 5, log in to your broker account, then run this again.")
        return 2

    account_info = mt5.account_info()
    terminal_info = mt5.terminal_info()
    print("MT5 initialize: OK")
    print(f"Account: {account_info.login if account_info else 'unknown'}")
    print(f"Terminal path: {terminal_info.path if terminal_info else 'unknown'}")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

