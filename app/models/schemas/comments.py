from typing import List

from pydantic import validator

from app.models.domain.comments import Comment
from app.models.schemas.rwschema import RWSchema


def _validate_body_not_empty(body: str) -> str:
    cleaned = body.strip()
    if not cleaned:
        raise ValueError("body is not allowed to be empty")
    return cleaned


class ListOfCommentsInResponse(RWSchema):
    comments: List[Comment]


class CommentInResponse(RWSchema):
    comment: Comment


class CommentInCreate(RWSchema):
    body: str

    _validate_body = validator("body", allow_reuse=True)(_validate_body_not_empty)


class CommentInUpdate(RWSchema):
    body: str

    _validate_body = validator("body", allow_reuse=True)(_validate_body_not_empty)
