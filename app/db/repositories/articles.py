from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Set, Union

from asyncpg import Connection, Record
from pypika import Query

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.queries.tables import (
    Parameter,
    articles,
    articles_to_tags,
    favorites,
    tags as tags_table,
    users,
)
from app.db.repositories.base import BaseRepository
from app.db.repositories.profiles import ProfilesRepository
from app.db.repositories.tags import TagsRepository
from app.models.domain.articles import Article
from app.models.domain.profiles import Profile
from app.models.domain.users import User

AUTHOR_USERNAME_ALIAS = "author_username"
SLUG_ALIAS = "slug"

CAMEL_OR_SNAKE_CASE_TO_WORDS = r"^[a-z\d_\-]+|[A-Z\d_\-][^A-Z\d_\-]*"


class ArticlesRepository(BaseRepository):  # noqa: WPS214
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self._profiles_repo = ProfilesRepository(conn)
        self._tags_repo = TagsRepository(conn)

    async def create_article(  # noqa: WPS211
        self,
        *,
        slug: str,
        title: str,
        description: str,
        body: str,
        author: User,
        tags: Optional[Sequence[str]] = None,
    ) -> Article:
        async with self.connection.transaction():
            article_row = await queries.create_new_article(
                self.connection,
                slug=slug,
                title=title,
                description=description,
                body=body,
                author_username=author.username,
            )

            if tags:
                await self._tags_repo.create_tags_that_dont_exist(tags=tags)
                await self._link_article_with_tags(slug=slug, tags=tags)

        return await self._get_article_from_db_record(
            article_row=article_row,
            slug=slug,
            author_username=article_row[AUTHOR_USERNAME_ALIAS],
            requested_user=author,
        )

    async def update_article(  # noqa: WPS211
        self,
        *,
        article: Article,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        body: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Article:
        updated_article = article.copy(deep=True)
        updated_article.slug = slug or updated_article.slug
        updated_article.title = title or article.title
        updated_article.body = body or article.body
        updated_article.description = description or article.description

        async with self.connection.transaction():
            updated_article.updated_at = await queries.update_article(
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
                new_slug=updated_article.slug,
                new_title=updated_article.title,
                new_body=updated_article.body,
                new_description=updated_article.description,
            )

        return updated_article

    async def delete_article(self, *, article: Article) -> None:
        async with self.connection.transaction():
            await queries.delete_article(
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
            )

    async def filter_articles(  # noqa: WPS211
        self,
        *,
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        requested_user: Optional[User] = None,
    ) -> List[Article]:
        query_params: List[Union[str, int]] = []
        query_params_count = 0

        # fmt: off
        query = Query.from_(
            articles,
        ).select(
            articles.id,
            articles.slug,
            articles.title,
            articles.description,
            articles.body,
            articles.created_at,
            articles.updated_at,
            Query.from_(
                users,
            ).where(
                users.id == articles.author_id,
            ).select(
                users.username,
            ).as_(
                AUTHOR_USERNAME_ALIAS,
            ),
        )
        # fmt: on

        if tag:
            query_params.append(tag)
            query_params_count += 1

            # fmt: off
            query = query.join(
                articles_to_tags,
            ).on(
                (articles.id == articles_to_tags.article_id) & (
                    articles_to_tags.tag == Query.from_(
                        tags_table,
                    ).where(
                        tags_table.tag == Parameter(query_params_count),
                    ).select(
                        tags_table.tag,
                    )
                ),
            )
            # fmt: on

        if author:
            query_params.append(author)
            query_params_count += 1

            # fmt: off
            query = query.join(
                users,
            ).on(
                (articles.author_id == users.id) & (
                    users.id == Query.from_(
                        users,
                    ).where(
                        users.username == Parameter(query_params_count),
                    ).select(
                        users.id,
                    )
                ),
            )
            # fmt: on

        if favorited:
            query_params.append(favorited)
            query_params_count += 1

            # fmt: off
            query = query.join(
                favorites,
            ).on(
                (articles.id == favorites.article_id) & (
                    favorites.user_id == Query.from_(
                        users,
                    ).where(
                        users.username == Parameter(query_params_count),
                    ).select(
                        users.id,
                    )
                ),
            )
            # fmt: on

        query = query.limit(Parameter(query_params_count + 1)).offset(
            Parameter(query_params_count + 2),
        )
        query_params.extend([limit, offset])

        articles_rows = await self.connection.fetch(query.get_sql(), *query_params)

        return await self._batch_get_articles_from_db_records(
            articles_rows=articles_rows,
            requested_user=requested_user,
        )

    async def get_articles_for_user_feed(
        self,
        *,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Article]:
        articles_rows = await queries.get_articles_for_feed(
            self.connection,
            follower_username=user.username,
            limit=limit,
            offset=offset,
        )
        return await self._batch_get_articles_from_db_records(
            articles_rows=articles_rows,
            requested_user=user,
        )

    async def get_article_by_slug(
        self,
        *,
        slug: str,
        requested_user: Optional[User] = None,
    ) -> Article:
        article_row = await queries.get_article_by_slug(self.connection, slug=slug)
        if article_row:
            return await self._get_article_from_db_record(
                article_row=article_row,
                slug=article_row[SLUG_ALIAS],
                author_username=article_row[AUTHOR_USERNAME_ALIAS],
                requested_user=requested_user,
            )

        raise EntityDoesNotExist("article with slug {0} does not exist".format(slug))

    async def get_tags_for_article_by_slug(self, *, slug: str) -> List[str]:
        tag_rows = await queries.get_tags_for_article_by_slug(
            self.connection,
            slug=slug,
        )
        return [row["tag"] for row in tag_rows]

    async def get_favorites_count_for_article_by_slug(self, *, slug: str) -> int:
        return (
            await queries.get_favorites_count_for_article(self.connection, slug=slug)
        )["favorites_count"]

    async def is_article_favorited_by_user(self, *, slug: str, user: User) -> bool:
        return (
            await queries.is_article_in_favorites(
                self.connection,
                username=user.username,
                slug=slug,
            )
        )["favorited"]

    async def add_article_into_favorites(self, *, article: Article, user: User) -> None:
        await queries.add_article_to_favorites(
            self.connection,
            username=user.username,
            slug=article.slug,
        )

    async def remove_article_from_favorites(
        self,
        *,
        article: Article,
        user: User,
    ) -> None:
        await queries.remove_article_from_favorites(
            self.connection,
            username=user.username,
            slug=article.slug,
        )

    async def _batch_get_articles_from_db_records(
        self,
        *,
        articles_rows: List[Record],
        requested_user: Optional[User],
    ) -> List[Article]:
        if not articles_rows:
            return []

        article_ids = [row["id"] for row in articles_rows]
        author_usernames = list({row[AUTHOR_USERNAME_ALIAS] for row in articles_rows})

        # Fetch all related data in bulk (4 queries total instead of 4*N)
        tags_by_article_id = await self._batch_get_tags_for_articles(
            article_ids=article_ids,
        )
        favorites_count_by_article_id = await self._batch_get_favorites_counts(
            article_ids=article_ids,
        )
        favorited_article_ids = await self._batch_get_favorited_article_ids(
            article_ids=article_ids,
            requested_user=requested_user,
        )
        profiles_by_username = await self._batch_get_profiles(
            usernames=author_usernames,
            requested_user=requested_user,
        )

        result = []
        for article_row in articles_rows:
            article_id = article_row["id"]
            author_username = article_row[AUTHOR_USERNAME_ALIAS]
            result.append(
                Article(
                    id_=article_id,
                    slug=article_row[SLUG_ALIAS],
                    title=article_row["title"],
                    description=article_row["description"],
                    body=article_row["body"],
                    author=profiles_by_username.get(
                        author_username,
                        Profile(username=author_username),
                    ),
                    tags=tags_by_article_id.get(article_id, []),
                    favorites_count=favorites_count_by_article_id.get(article_id, 0),
                    favorited=article_id in favorited_article_ids,
                    created_at=article_row["created_at"],
                    updated_at=article_row["updated_at"],
                ),
            )
        return result

    async def _batch_get_tags_for_articles(
        self,
        *,
        article_ids: List[int],
    ) -> Dict[int, List[str]]:
        if not article_ids:
            return {}
        rows = await self.connection.fetch(
            "SELECT article_id, tag FROM articles_to_tags "
            "WHERE article_id = ANY($1::int[]) ORDER BY article_id",
            article_ids,
        )
        result: Dict[int, List[str]] = defaultdict(list)
        for row in rows:
            result[row["article_id"]].append(row["tag"])
        return dict(result)

    async def _batch_get_favorites_counts(
        self,
        *,
        article_ids: List[int],
    ) -> Dict[int, int]:
        if not article_ids:
            return {}
        rows = await self.connection.fetch(
            "SELECT article_id, count(*) AS favorites_count "
            "FROM favorites WHERE article_id = ANY($1::int[]) "
            "GROUP BY article_id",
            article_ids,
        )
        return {row["article_id"]: row["favorites_count"] for row in rows}

    async def _batch_get_favorited_article_ids(
        self,
        *,
        article_ids: List[int],
        requested_user: Optional[User],
    ) -> Set[int]:
        if not requested_user or not article_ids:
            return set()
        rows = await self.connection.fetch(
            "SELECT article_id FROM favorites "
            "WHERE user_id = (SELECT id FROM users WHERE username = $1) "
            "AND article_id = ANY($2::int[])",
            requested_user.username,
            article_ids,
        )
        return {row["article_id"] for row in rows}

    async def _batch_get_profiles(
        self,
        *,
        usernames: List[str],
        requested_user: Optional[User],
    ) -> Dict[str, Profile]:
        if not usernames:
            return {}
        rows = await self.connection.fetch(
            "SELECT username, bio, image FROM users "
            "WHERE username = ANY($1::text[])",
            usernames,
        )
        profiles: Dict[str, Profile] = {}
        for row in rows:
            profiles[row["username"]] = Profile(
                username=row["username"],
                bio=row["bio"] or "",
                image=row["image"],
                following=False,
            )

        if requested_user and profiles:
            following_statuses = await self._batch_get_following_statuses(
                usernames=usernames,
                requested_user=requested_user,
            )
            for username, is_following in following_statuses.items():
                if username in profiles:
                    profiles[username].following = is_following

        return profiles

    async def _batch_get_following_statuses(
        self,
        *,
        usernames: List[str],
        requested_user: User,
    ) -> Dict[str, bool]:
        rows = await self.connection.fetch(
            "SELECT u.username, "
            "CASE WHEN f.following_id IS NULL THEN FALSE ELSE TRUE END "
            "AS is_following "
            "FROM users u "
            "LEFT OUTER JOIN followers_to_followings f "
            "ON u.id = f.following_id "
            "AND f.follower_id = (SELECT id FROM users WHERE username = $1) "
            "WHERE u.username = ANY($2::text[])",
            requested_user.username,
            usernames,
        )
        return {row["username"]: row["is_following"] for row in rows}

    async def _get_article_from_db_record(
        self,
        *,
        article_row: Record,
        slug: str,
        author_username: str,
        requested_user: Optional[User],
    ) -> Article:
        return Article(
            id_=article_row["id"],
            slug=slug,
            title=article_row["title"],
            description=article_row["description"],
            body=article_row["body"],
            author=await self._profiles_repo.get_profile_by_username(
                username=author_username,
                requested_user=requested_user,
            ),
            tags=await self.get_tags_for_article_by_slug(slug=slug),
            favorites_count=await self.get_favorites_count_for_article_by_slug(
                slug=slug,
            ),
            favorited=await self.is_article_favorited_by_user(
                slug=slug,
                user=requested_user,
            )
            if requested_user
            else False,
            created_at=article_row["created_at"],
            updated_at=article_row["updated_at"],
        )

    async def _link_article_with_tags(self, *, slug: str, tags: Sequence[str]) -> None:
        await queries.add_tags_to_article(
            self.connection,
            [{SLUG_ALIAS: slug, "tag": tag} for tag in tags],
        )
