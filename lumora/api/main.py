from fastapi import FastAPI

from lumora.core.version import VERSION

app = FastAPI(
    title="Lumora API",
    version=VERSION,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "version": VERSION,
    }