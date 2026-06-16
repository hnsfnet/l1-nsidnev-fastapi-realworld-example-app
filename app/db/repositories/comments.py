from typing import List, Optional, Tuple

from asyncpg import Connection, Record

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.db.repositories.profiles import ProfilesRepository
from app.models.domain.articles import Article
from app.models.domain.comments import Comment
from app.models.domain.users import User


class CommentsRepository(BaseRepository):
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self._profiles_repo = ProfilesRepository(conn)

    async def get_comment_by_id(
        self,
        *,
        comment_id: int,
        article: Article,
        user: Optional[User] = None,
    ) -> Comment:
        comment_row = await queries.get_comment_by_id_and_slug(
            self.connection,
            comment_id=comment_id,
            article_slug=article.slug,
        )
        if comment_row:
            return await self._get_comment_from_db_record(
                comment_row=comment_row,
                author_username=comment_row["author_username"],
                requested_user=user,
            )

        raise EntityDoesNotExist(
            "comment with id {0} does not exist".format(comment_id),
        )

    async def get_comments_for_article(
        self,
        *,
        article: Article,
        user: Optional[User] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "desc",
    ) -> Tuple[List[Comment], int]:
        if sort == "asc":
            comments_rows = await queries.get_comments_for_article_by_slug_asc(
                self.connection,
                slug=article.slug,
                limit=limit,
                offset=offset,
            )
        else:
            comments_rows = await queries.get_comments_for_article_by_slug_desc(
                self.connection,
                slug=article.slug,
                limit=limit,
                offset=offset,
            )

        count_row = await queries.get_comments_count_for_article(
            self.connection,
            slug=article.slug,
        )
        comments_count = count_row["comments_count"]

        comments = [
            await self._get_comment_from_db_record(
                comment_row=comment_row,
                author_username=comment_row["author_username"],
                requested_user=user,
            )
            for comment_row in comments_rows
        ]
        return comments, comments_count

    async def create_comment_for_article(
        self,
        *,
        body: str,
        article: Article,
        user: User,
    ) -> Comment:
        comment_row = await queries.create_new_comment(
            self.connection,
            body=body,
            article_slug=article.slug,
            author_username=user.username,
        )
        return await self._get_comment_from_db_record(
            comment_row=comment_row,
            author_username=comment_row["author_username"],
            requested_user=user,
        )

    async def update_comment(
        self,
        *,
        comment: Comment,
        body: str,
        user: User,
    ) -> Comment:
        comment_row = await queries.update_comment(
            self.connection,
            body=body,
            comment_id=comment.id_,
            author_username=user.username,
        )
        return await self._get_comment_from_db_record(
            comment_row=comment_row,
            author_username=comment.author.username,
            requested_user=user,
        )

    async def delete_comment(self, *, comment: Comment) -> None:
        await queries.delete_comment_by_id(
            self.connection,
            comment_id=comment.id_,
            author_username=comment.author.username,
        )

    async def _get_comment_from_db_record(
        self,
        *,
        comment_row: Record,
        author_username: str,
        requested_user: Optional[User],
    ) -> Comment:
        return Comment(
            id_=comment_row["id"],
            body=comment_row["body"],
            author=await self._profiles_repo.get_profile_by_username(
                username=author_username,
                requested_user=requested_user,
            ),
            created_at=comment_row["created_at"],
            updated_at=comment_row["updated_at"],
        )
