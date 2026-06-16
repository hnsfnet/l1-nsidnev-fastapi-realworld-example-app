from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.models.domain.articles import Article
from app.models.schemas.rwschema import RWSchema
from app.services.articles import clean_tags

DEFAULT_ARTICLES_LIMIT = 20
DEFAULT_ARTICLES_OFFSET = 0


class ArticleForResponse(RWSchema, Article):
    tags: List[str] = Field(..., alias="tagList")


class ArticleInResponse(RWSchema):
    article: ArticleForResponse


class ArticleInCreate(RWSchema):
    title: str
    description: str
    body: str
    tags: List[str] = Field([], alias="tagList")

    @validator("tags", pre=True)
    def clean_tag_list(cls, v):  # noqa: N805
        return clean_tags(v) if v else v


class ArticleInUpdate(RWSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[List[str]] = Field(None, alias="tagList")

    @validator("tags", pre=True)
    def clean_tag_list(cls, v):  # noqa: N805
        if v is None:
            return v
        return clean_tags(v)


class ListOfArticlesInResponse(RWSchema):
    articles: List[ArticleForResponse]
    articles_count: int


class ArticlesFilters(BaseModel):
    tag: Optional[str] = None
    author: Optional[str] = None
    favorited: Optional[str] = None
    limit: int = Field(DEFAULT_ARTICLES_LIMIT, ge=1)
    offset: int = Field(DEFAULT_ARTICLES_OFFSET, ge=0)
