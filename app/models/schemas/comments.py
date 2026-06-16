from enum import Enum
from typing import List

from pydantic import BaseModel, Field, validator

from app.models.domain.comments import Comment
from app.models.schemas.rwschema import RWSchema

DEFAULT_COMMENTS_LIMIT = 20
DEFAULT_COMMENTS_OFFSET = 0


class CommentSortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class CommentsFilters(BaseModel):
    limit: int = Field(DEFAULT_COMMENTS_LIMIT, ge=1, le=100)
    offset: int = Field(DEFAULT_COMMENTS_OFFSET, ge=0)
    sort: CommentSortOrder = CommentSortOrder.desc


class ListOfCommentsInResponse(RWSchema):
    comments: List[Comment]
    comments_count: int


class CommentInResponse(RWSchema):
    comment: Comment


class CommentInCreate(RWSchema):
    body: str

    @validator("body")
    def body_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("comment body cannot be blank")
        return v


class CommentInUpdate(RWSchema):
    body: str

    @validator("body")
    def body_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("comment body cannot be blank")
        return v
