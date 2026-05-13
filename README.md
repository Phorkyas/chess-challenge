# chess-challenge

Website to interactively solve chess puzzles with spaced repetition (Anki-style). Users register with email, create puzzles with FEN positions and solution moves, then solve them. Harder puzzles appear more often via the SM-2 algorithm.

## Routes

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/` | GET | optional | Dashboard with stats, due items, and new puzzles for authenticated users; landing page otherwise |
| `/register` | GET | no | Registration form |
| `/register` | POST | no | Create account (email + password, bcrypt hashed) |
| `/login` | GET | no | Login form |
| `/login` | POST | no | Authenticate and set session cookie |
| `/logout` | POST | yes | Clear session cookie |
| `/puzzles` | GET | yes | List user's puzzles with review stats (interval, ease) |
| `/puzzles/new` | GET | yes | Puzzle creation form with interactive chessboard for FEN preview |
| `/puzzles/new` | POST | yes | Create puzzle — validates FEN and UCI solution moves |
| `/puzzles/{id}/delete` | POST | yes | Delete own puzzle |
| `/review` | GET | yes | Show next due puzzle (oldest `next_review` first) or a never-reviewed puzzle |
| `/review/{puzzle_id}` | POST | yes | Submit grade (0-5) and solve time — SM-2 reschedules the puzzle |

### SM-2 Grades

| Grade | Description |
|-------|-------------|
| 0 | Complete blackout |
| 1 | Seen answer, makes sense |
| 2 | Incorrect, easy recall |
| 3 | Correct, hard |
| 4 | Correct, hesitated |
| 5 | Perfect |

### Session Auth

Uses an [itsdangerous](https://itsdangerous.palletsprojects.com/)-signed cookie (`chess_session`) containing the user ID. `current_user` dependency returns the authenticated user or 401; `current_user_optional` returns `None` for anonymous visitors.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The SQLite database (`app.db`) is created automatically on startup.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy (async, aiosqlite) + Jinja2
- **Chess:** python-chess (server), chessboard.js + chess.js (browser)
- **Pieces:** [Lichess cburnett SVGs](https://github.com/lichess-org/lila/tree/master/public/piece/cburnett) served from `/static/pieces/`
- **Algorithm:** SM-2 spaced repetition (minimum ease factor 1.3)

## License

MIT
