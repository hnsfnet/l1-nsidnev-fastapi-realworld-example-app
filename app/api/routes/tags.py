from fastapi import APIRouter, Depends, Query

from app.api.dependencies.database import get_repository
from app.db.repositories.tags import TagsRepository
from app.models.schemas.tags import PopularTagInResponse, PopularTagsInList, TagsInList

router = APIRouter()


@router.get("", response_model=TagsInList, name="tags:get-all")
async def get_all_tags(
    tags_repo: TagsRepository = Depends(get_repository(TagsRepository)),
) -> TagsInList:
    tags = await tags_repo.get_all_tags()
    return TagsInList(tags=tags)


@router.get("/popular", response_model=PopularTagsInList, name="tags:get-popular")
async def get_popular_tags(
    limit: int = Query(10, ge=1, le=100),
    tags_repo: TagsRepository = Depends(get_repository(TagsRepository)),
) -> PopularTagsInList:
    popular_tags = await tags_repo.get_popular_tags(limit=limit)
    return PopularTagsInList(
        tags=[
            PopularTagInResponse(tag=pt.tag, article_count=pt.article_count)
            for pt in popular_tags
        ]
    )
