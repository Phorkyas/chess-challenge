import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_homepage(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Chess Challenge" in r.text


async def test_register_login_flow(client):
    r = await client.post("/register", data={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"

    r = await client.post("/logout")
    assert r.status_code == 303

    r = await client.post("/login", data={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401

    r = await client.post("/login", data={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 303


async def test_create_and_review_puzzle(client):
    await client.post("/register", data={"email": "test@test.com", "password": "secret123"})

    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    r = await client.post(
        "/puzzles/new",
        data={
            "title": "Scholars Mate",
            "fen": fen,
            "solution": "e2e4 e7e5 d1h5 b8c6 f1c4 g8f6 h5f7",
        },
    )
    assert r.status_code == 303

    r = await client.get("/review")
    assert r.status_code == 200
    assert "Scholars Mate" in r.text

    r = await client.post("/review/1", data={"grade": "5", "time_ms": "3000"})
    assert r.status_code == 303

    r = await client.get("/puzzles")
    assert r.status_code == 200
    assert "Scholars Mate" in r.text

    r = await client.get("/")
    assert r.status_code == 200
    assert "1" in r.text
