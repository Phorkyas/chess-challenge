# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Website to interactively solve chess puzzles with spaced repetition (Anki-style). Users register with email, create puzzles with FEN positions and solution moves, then solve them. Harder puzzles appear more often via the SM-2 algorithm. MIT licensed.

## Commands

```bash
# Use the venv
source .venv/bin/activate

# Run dev server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run all tests
pytest tests/ -v

# Lint
ruff check app/ tests/
ruff check app/ tests/ --fix   # auto-fix
```

## Architecture

**Stack:** FastAPI + SQLAlchemy (async, aiosqlite) + Jinja2 + chessboard.js CDN + python-chess

**Entry point:** `app/main.py` — FastAPI app with all routes defined inline
**Database:** SQLite at `app.db`, auto-created on startup via `lifespan`

### Data Model (`app/models/`)
- **User** — email, password_hash, created_at. Has puzzles + reviews.
- **Puzzle** — title, fen, solution_moves (UCI space-separated). Belongs to creator.
- **Review** — per-user-per-puzzle tracking: ease_factor, interval, repetitions (SM-2 state), total_attempts/failures/time_ms, next_review scheduling.

### Routes
| Route | Purpose |
|-------|---------|
| `GET /` | Dashboard (stats, due items) for authenticated users; landing page otherwise |
| `GET/POST /register`, `/login`, `/logout` | Email + password auth via bcrypt + itsdangerous cookies |
| `GET /puzzles` | List user's puzzles with review stats |
| `GET/POST /puzzles/new` | Create puzzle — interactive chessboard for FEN preview, UCI solution validation |
| `POST /puzzles/{id}/delete` | Delete own puzzle |
| `GET /review` | Show next due puzzle (oldest `next_review` first) or a never-reviewed puzzle |
| `POST /review/{puzzle_id}` | Submit grade (0-5) and time — SM-2 reschedules |

### Spaced Repetition (`app/spaced_repetition.py`)
Pure SM-2 algorithm. `ReviewState` dataclass → `sm2(state, grade)` → new `ReviewState`. Grades: 0=blackout, 5=perfect. Minimum ease factor 1.3.

### Auth (`app/auth.py`)
Session via itsdangerous-signed cookie (`chess_session`). `current_user` dependency (401 if not logged in), `current_user_optional` (returns None).

### Templates
Jinja2 in `app/templates/`. Base layout in `base.html` with nav bar. Chessboard rendered client-side via chessboardjs.com CDN + chess.js for move validation.
