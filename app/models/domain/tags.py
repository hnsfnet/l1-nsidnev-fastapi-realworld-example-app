from pydantic import BaseModel


class PopularTag(BaseModel):
    tag: str
    article_count: int
