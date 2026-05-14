import datetime
from contextlib import asynccontextmanager

import bcrypt
import chess
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import (
    clear_session,
    current_user,
    current_user_optional,
    set_session,
)
from app.database import get_db, init_db
from app.models import Puzzle, Review, User
from app.spaced_repetition import ReviewState, sm2


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def templates_with_user(request: Request, user: User | None):
    return {"request": request, "user": user}


# ── dashboard ──────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(current_user_optional),
):
    ctx = templates_with_user(request, user)
    if user is None:
        return templates.TemplateResponse(request, "index.html", ctx)

    now = datetime.datetime.now(datetime.UTC)

    total_puzzles_q = select(func.count(Puzzle.id)).where(Puzzle.creator_id == user.id)
    total_puzzles = await db.scalar(total_puzzles_q)

    due_q = (
        select(Review)
        .options(selectinload(Review.puzzle))
        .where(Review.user_id == user.id, Review.next_review <= now)
        .order_by(Review.next_review.asc())
    )
    due_reviews = (await db.execute(due_q)).scalars().all()

    new_puzzles_q = (
        select(Puzzle)
        .outerjoin(Review, (Review.puzzle_id == Puzzle.id) & (Review.user_id == user.id))
        .where(Puzzle.creator_id == user.id, Review.id.is_(None))
    )
    new_puzzles = (await db.execute(new_puzzles_q)).scalars().all()

    total_reviews_q = select(func.count(Review.id)).where(Review.user_id == user.id)
    total_reviews = await db.scalar(total_reviews_q)

    ctx.update(
        total_puzzles=total_puzzles or 0,
        due_reviews=due_reviews,
        new_puzzles=new_puzzles,
        total_reviews=total_reviews or 0,
        now=now,
    )
    return templates.TemplateResponse(request, "dashboard.html", ctx)


# ── auth ────────────────────────────────────────────────────────────


@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(User).where(User.email == email.lower().strip()))
    if existing:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Email already registered"}, status_code=400
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Password must be at least 6 characters"},
            status_code=400,
        )

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email.lower().strip(), password_hash=hashed)
    db.add(user)
    await db.commit()

    response = RedirectResponse("/", status_code=303)
    set_session(response, user.id)
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password"}, status_code=401
        )

    response = RedirectResponse("/", status_code=303)
    set_session(response, user.id)
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    clear_session(response)
    return response


# ── puzzles ─────────────────────────────────────────────────────────


@app.get("/puzzles", response_class=HTMLResponse)
async def puzzle_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    puzzles = (
        await db.execute(
            select(Puzzle).where(Puzzle.creator_id == user.id).order_by(Puzzle.created_at.desc())
        )
    ).scalars().all()

    puzzle_reviews = {}
    if puzzles:
        review_rows = (
            await db.execute(
                select(Review).where(
                    Review.user_id == user.id,
                    Review.puzzle_id.in_([p.id for p in puzzles]),
                )
            )
        ).scalars().all()
        puzzle_reviews = {r.puzzle_id: r for r in review_rows}

    ctx = templates_with_user(request, user)
    ctx.update(puzzles=puzzles, puzzle_reviews=puzzle_reviews)
    return templates.TemplateResponse(request, "puzzles.html", ctx)


@app.get("/puzzles/new", response_class=HTMLResponse)
async def create_puzzle_form(
    request: Request,
    user: User = Depends(current_user),
):
    return templates.TemplateResponse(
        request, "puzzle_create.html", templates_with_user(request, user)
    )


@app.post("/puzzles/new")
async def create_puzzle(
    request: Request,
    title: str = Form(...),
    fen: str = Form(...),
    solution: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        chess.Board(fen)
    except ValueError:
        return templates.TemplateResponse(
            request, "puzzle_create.html",
            {**templates_with_user(request, user), "error": "Invalid FEN position"},
            status_code=400,
        )

    moves = solution.strip().split()
    if not moves:
        return templates.TemplateResponse(
            request, "puzzle_create.html",
            {**templates_with_user(request, user), "error": "No solution moves provided"},
            status_code=400,
        )

    board = chess.Board(fen)
    for m in moves:
        try:
            board.push_uci(m)
        except ValueError:
            return templates.TemplateResponse(
                request, "puzzle_create.html",
                {**templates_with_user(request, user), "error": f"Invalid move: {m}"},
                status_code=400,
            )

    puzzle = Puzzle(
        creator_id=user.id,
        title=title.strip(),
        fen=fen.strip(),
        solution_moves=solution.strip(),
    )
    db.add(puzzle)
    await db.commit()

    return RedirectResponse("/puzzles", status_code=303)


@app.post("/puzzles/{puzzle_id}/delete")
async def delete_puzzle(
    puzzle_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    puzzle = await db.get(Puzzle, puzzle_id)
    if puzzle is None or puzzle.creator_id != user.id:
        raise HTTPException(status_code=404)
    await db.delete(puzzle)
    await db.commit()
    return RedirectResponse("/puzzles", status_code=303)


# ── review ──────────────────────────────────────────────────────────


@app.get("/review", response_class=HTMLResponse)
async def review_next(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
    puzzle_id: int = None,
):
    now = datetime.datetime.now(datetime.UTC)

    if puzzle_id is not None:
        puzzle = await db.scalar(
            select(Puzzle).where(Puzzle.id == puzzle_id, Puzzle.creator_id == user.id)
        )
        if puzzle is None:
            raise HTTPException(status_code=404)
        review = await db.scalar(
            select(Review).where(Review.user_id == user.id, Review.puzzle_id == puzzle_id)
        )
        if review is None:
            review = Review(user_id=user.id, puzzle_id=puzzle.id)
            db.add(review)
            await db.commit()
    else:
        review = await db.scalar(
            select(Review)
            .options(selectinload(Review.puzzle))
            .where(Review.user_id == user.id, Review.next_review <= now)
            .order_by(Review.next_review.asc())
            .limit(1)
        )
        if review is None:
            new_puzzle = await db.scalar(
                select(Puzzle)
                .outerjoin(Review, (Review.puzzle_id == Puzzle.id) & (Review.user_id == user.id))
                .where(Puzzle.creator_id == user.id, Review.id.is_(None))
                .limit(1)
            )
            if new_puzzle is None:
                ctx = templates_with_user(request, user)
                ctx["message"] = "No puzzles to review. Create some puzzles first!"
                return templates.TemplateResponse(request, "review_empty.html", ctx)
            review = Review(user_id=user.id, puzzle_id=new_puzzle.id)
            db.add(review)
            await db.commit()
            puzzle = new_puzzle
        else:
            puzzle = review.puzzle
    board = chess.Board(puzzle.fen)
    ctx = templates_with_user(request, user)
    ctx.update(
        puzzle=puzzle,
        review_id=review.id,
        fen=puzzle.fen,
        solution_moves=puzzle.solution_moves.split(),
        first_move_turn="white" if board.turn == chess.WHITE else "black",
        ease_factor=review.ease_factor,
        interval=review.interval,
        repetitions=review.repetitions,
    )
    return templates.TemplateResponse(request, "review.html", ctx)


@app.post("/review/{puzzle_id}", response_class=HTMLResponse)
async def submit_review(
    request: Request,
    puzzle_id: int,
    user_moves: str = Form(""),
    time_ms: int = Form(0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    review = await db.scalar(
        select(Review)
        .options(selectinload(Review.puzzle))
        .where(Review.user_id == user.id, Review.puzzle_id == puzzle_id)
    )
    if review is None:
        raise HTTPException(status_code=404)

    puzzle = review.puzzle
    solution_moves = puzzle.solution_moves.split()
    played = user_moves.strip().split() if user_moves.strip() else []
    expected = [solution_moves[i] for i in range(0, len(solution_moves), 2)]

    correct = 0
    for i, exp in enumerate(expected):
        if i < len(played) and played[i] == exp:
            correct += 1

    if not expected:
        grade = 5
    else:
        ratio = correct / len(expected)
        if ratio == 1.0:
            grade = 5
        elif ratio >= 0.75:
            grade = 4
        elif ratio >= 0.5:
            grade = 3
        elif ratio >= 0.25:
            grade = 2
        elif ratio > 0:
            grade = 1
        else:
            grade = 0

    old_state = ReviewState(review.ease_factor, review.interval, review.repetitions)
    new_state = sm2(old_state, grade)

    review.ease_factor = new_state.ease_factor
    review.interval = new_state.interval
    review.repetitions = new_state.repetitions
    review.total_attempts += 1
    if grade < 3:
        review.total_failures += 1
    review.total_time_ms += time_ms
    review.last_reviewed = datetime.datetime.now(datetime.UTC)
    review.next_review = review.last_reviewed + datetime.timedelta(
        days=new_state.interval
    )

    await db.commit()

    return RedirectResponse("/review", status_code=303)
