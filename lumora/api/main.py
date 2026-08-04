import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from lumora.api.routes import health, index, query

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Lumora API")

app.include_router(health.router)
app.include_router(index.router)
app.include_router(query.router)
