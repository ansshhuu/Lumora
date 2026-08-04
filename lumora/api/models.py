from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    repo_url: str = Field(..., description="HTTPS GitHub repository URL")


class IndexResponse(BaseModel):
    status: str
    collection: str
    items_count: int


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    collection: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    answer: str


class HealthResponse(BaseModel):
    status: str
