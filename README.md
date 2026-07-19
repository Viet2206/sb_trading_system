# SB System

SB System is a Forex trading research and signal platform based on Stacey Burke trading concepts.

The current development focus is Phase 1:

- Normalize the project direction.
- Prepare source documents for later strategy extraction.
- Build the first MT5-to-Postgres market data ingestion path.
- Keep signal detection separate from future auto-trading.

## Local Setup

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy environment settings:

```bash
cp .env.example .env
```

Start PostgreSQL with Docker:

```bash
docker compose up -d postgres
```

The default `.env.example` connection string already matches this local Docker database:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/sb_system
```

Check the database container:

```bash
docker compose ps
```

Run the notebook:

```bash
jupyter lab notebooks/01_mt5_to_postgres.ipynb
```

If the notebook shows `connection refused` on port `5432`, PostgreSQL is not running yet. Start it with `docker compose up -d postgres`, then rerun the connection/schema cell.

## MT5 Notes

The normal MT5 Python package workflow is intended to run on Windows with an installed MetaTrader 5 terminal. On macOS, use the notebook to validate PostgreSQL connectivity, schema creation, and import logic. Run the MT5 extraction cells on the Windows VPS.

Install the Windows/VPS dependencies with:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-win-mt5.txt
```

Register the project virtual environment as a Jupyter kernel:

```bat
python -m ipykernel install --user --name sb-system --display-name "SB System (.venv)"
```

Then open Jupyter Lab and select the `SB System (.venv)` kernel:

```bat
jupyter lab notebooks/01_mt5_to_postgres.ipynb
```

If the notebook says `No module named 'MetaTrader5'`, the selected Jupyter kernel is not the same Python environment where the package was installed. Inside the notebook, run:

```python
import sys
print(sys.executable)
```

Then install into that exact interpreter:

```python
import sys
!"{sys.executable}" -m pip install -r requirements-win-mt5.txt
```

Restart the kernel after installation.

You can also verify the Windows MT5 environment from the terminal:

```bat
.venv\Scripts\activate
python scripts\check_mt5_env.py
```

## Project Instructions

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for the durable architecture and development plan.
