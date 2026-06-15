from typing import List, Sequence

from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.tags import PopularTag


class TagsRepository(BaseRepository):
    async def get_all_tags(self) -> List[str]:
        tags_row = await queries.get_all_tags(self.connection)
        return [tag[0] for tag in tags_row]

    async def get_popular_tags(self, *, limit: int = 10) -> List[PopularTag]:
        rows = await queries.get_popular_tags(self.connection, limit=limit)
        return [
            PopularTag(tag=row["tag"], article_count=row["article_count"])
            for row in rows
        ]

    async def create_tags_that_dont_exist(self, *, tags: Sequence[str]) -> None:
        await queries.create_new_tags(self.connection, [{"tag": tag} for tag in tags])
