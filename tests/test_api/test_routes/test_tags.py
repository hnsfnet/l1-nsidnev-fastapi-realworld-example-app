import pytest
from asyncpg.pool import Pool
from fastapi import FastAPI
from httpx import AsyncClient

from app.db.repositories.articles import ArticlesRepository
from app.db.repositories.tags import TagsRepository
from app.db.repositories.users import UsersRepository
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB

pytestmark = pytest.mark.asyncio


async def test_empty_list_when_no_tags_exist(app: FastAPI, client: AsyncClient) -> None:
    response = await client.get(app.url_path_for("tags:get-all"))
    assert response.json() == {"tags": []}


async def test_list_of_tags_when_tags_exist(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    tags = ["tag1", "tag2", "tag3", "tag4", "tag1"]

    async with pool.acquire() as conn:
        tags_repo = TagsRepository(conn)
        await tags_repo.create_tags_that_dont_exist(tags=tags)

    response = await client.get(app.url_path_for("tags:get-all"))
    tags_from_response = response.json()["tags"]
    assert len(tags_from_response) == len(set(tags))
    assert all((tag in tags for tag in tags_from_response))


# ---------- Popular tags tests ----------


async def _create_user(pool: Pool, username: str) -> UserInDB:
    async with pool.acquire() as conn:
        return await UsersRepository(conn).create_user(
            email=f"{username}@test.com",
            password="password",
            username=username,
        )


async def _create_article(
    pool: Pool,
    author: UserInDB,
    slug: str,
    tags: list,
) -> Article:
    async with pool.acquire() as conn:
        return await ArticlesRepository(conn).create_article(
            slug=slug,
            title=slug.replace("-", " ").title(),
            description="desc",
            body="body",
            author=author,
            tags=tags,
        )


async def test_popular_tags_empty_when_no_articles(
    app: FastAPI, client: AsyncClient
) -> None:
    response = await client.get(app.url_path_for("tags:get-popular"))
    assert response.status_code == 200
    assert response.json() == {"tags": []}


async def test_popular_tags_ordered_by_count_desc_then_tag_asc(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    user = await _create_user(pool, "pop_user1")

    # Create 3 articles with tag "beta", 2 with "alpha", 1 with "gamma"
    await _create_article(pool, user, "slug-a1", ["beta"])
    await _create_article(pool, user, "slug-a2", ["beta"])
    await _create_article(pool, user, "slug-a3", ["beta"])
    await _create_article(pool, user, "slug-a4", ["alpha"])
    await _create_article(pool, user, "slug-a5", ["alpha"])
    await _create_article(pool, user, "slug-a6", ["gamma"])

    response = await client.get(app.url_path_for("tags:get-popular"))
    assert response.status_code == 200
    tags = response.json()["tags"]
    assert tags == [
        {"tag": "beta", "article_count": 3},
        {"tag": "alpha", "article_count": 2},
        {"tag": "gamma", "article_count": 1},
    ]


async def test_popular_tags_tie_breaking_by_tag_asc(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    user = await _create_user(pool, "pop_user2")

    # All three tags appear in exactly 1 article each → tie → alphabetical
    await _create_article(pool, user, "tie-1", ["cherry"])
    await _create_article(pool, user, "tie-2", ["apple"])
    await _create_article(pool, user, "tie-3", ["banana"])

    response = await client.get(app.url_path_for("tags:get-popular"))
    tags = response.json()["tags"]
    assert [t["tag"] for t in tags] == ["apple", "banana", "cherry"]
    assert all(t["article_count"] == 1 for t in tags)


async def test_popular_tags_limit(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    user = await _create_user(pool, "pop_user3")

    # Create tags with different counts: t5=5, t4=4, ..., t1=1
    for i in range(5, 0, -1):
        tag_name = f"t{i}"
        for j in range(i):
            await _create_article(pool, user, f"lim-{tag_name}-{j}", [tag_name])

    response = await client.get(
        app.url_path_for("tags:get-popular"), params={"limit": 3}
    )
    tags = response.json()["tags"]
    assert len(tags) == 3
    assert tags[0] == {"tag": "t5", "article_count": 5}
    assert tags[1] == {"tag": "t4", "article_count": 4}
    assert tags[2] == {"tag": "t3", "article_count": 3}


async def test_popular_tags_excludes_orphan_tags(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    """Tags that exist in the tags table but have no linked articles must not appear."""
    async with pool.acquire() as conn:
        tags_repo = TagsRepository(conn)
        await tags_repo.create_tags_that_dont_exist(
            tags=["orphan1", "orphan2", "linked"]
        )

    user = await _create_user(pool, "pop_user4")
    await _create_article(pool, user, "linked-art", ["linked"])

    response = await client.get(app.url_path_for("tags:get-popular"))
    tags = response.json()["tags"]
    tag_names = [t["tag"] for t in tags]
    assert "linked" in tag_names
    assert "orphan1" not in tag_names
    assert "orphan2" not in tag_names


async def test_popular_tags_count_decreases_after_article_delete(
    app: FastAPI, client: AsyncClient, pool: Pool
) -> None:
    user = await _create_user(pool, "pop_user5")

    article1 = await _create_article(pool, user, "del-1", ["deltag"])
    await _create_article(pool, user, "del-2", ["deltag"])
    await _create_article(pool, user, "del-3", ["deltag"])

    # Confirm count is 3
    response = await client.get(app.url_path_for("tags:get-popular"))
    tags = response.json()["tags"]
    assert tags[0] == {"tag": "deltag", "article_count": 3}

    # Delete one article (cascade removes articles_to_tags rows)
    async with pool.acquire() as conn:
        await ArticlesRepository(conn).delete_article(article=article1)

    response = await client.get(app.url_path_for("tags:get-popular"))
    tags = response.json()["tags"]
    assert tags[0] == {"tag": "deltag", "article_count": 2}

