from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="eval-runner",
    version="0.1.0",
    description="FastAPI project scaffold for eval-runner.",
)

app.include_router(api_router)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": "eval-runner API is running"}
