from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from campaigns import router
from database import engine

app = FastAPI(title="Keitaro Campaigns")
app.include_router(router)
static_dir = Path(__file__).with_name("static")


@app.get("/campaigns", include_in_schema=False)
@app.get("/campaigns/new", include_in_schema=False)
@app.get("/campaigns/{campaign_id:int}", include_in_schema=False)
@app.get("/offers", include_in_schema=False)
def dashboard():
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ok", "database": "ok"}


app.mount(
    "/",
    StaticFiles(directory=static_dir, html=True),
    name="frontend",
)
