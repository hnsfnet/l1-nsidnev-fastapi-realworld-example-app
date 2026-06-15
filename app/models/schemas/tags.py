from typing import List

from pydantic import BaseModel


class TagsInList(BaseModel):
    tags: List[str]


class PopularTagInResponse(BaseModel):
    tag: str
    article_count: int

    class Config:
        orm_mode = True


class PopularTagsInList(BaseModel):
    tags: List[PopularTagInResponse]
