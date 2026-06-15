import asyncio

import pytest
from asyncpg.pool import Pool
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from app.db.repositories.comments import CommentsRepository
from app.db.repositories.users import UsersRepository
from app.models.domain.articles import Article
from app.models.schemas.comments import CommentInResponse, ListOfCommentsInResponse

pytestmark = pytest.mark.asyncio


async def test_user_can_add_comment_for_article(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    created_comment_response = await authorized_client.post(
        app.url_path_for("comments:create-comment-for-article", slug=test_article.slug),
        json={"comment": {"body": "comment"}},
    )

    created_comment = CommentInResponse(**created_comment_response.json())

    comments_for_article_response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug)
    )

    comments = ListOfCommentsInResponse(**comments_for_article_response.json())

    assert comments.comments_count == 1
    assert created_comment.comment == comments.comments[0]


async def test_user_can_delete_own_comment(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    created_comment_response = await authorized_client.post(
        app.url_path_for("comments:create-comment-for-article", slug=test_article.slug),
        json={"comment": {"body": "comment"}},
    )

    created_comment = CommentInResponse(**created_comment_response.json())

    await authorized_client.delete(
        app.url_path_for(
            "comments:delete-comment-from-article",
            slug=test_article.slug,
            comment_id=str(created_comment.comment.id_),
        )
    )

    comments_for_article_response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug)
    )

    comments = ListOfCommentsInResponse(**comments_for_article_response.json())

    assert len(comments.comments) == 0
    assert comments.comments_count == 0


async def test_user_can_not_delete_not_authored_comment(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article, pool: Pool
) -> None:
    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.create_user(
            username="test_author", email="author@email.com", password="password"
        )
        comments_repo = CommentsRepository(connection)
        comment = await comments_repo.create_comment_for_article(
            body="tmp", article=test_article, user=user
        )

    forbidden_response = await authorized_client.delete(
        app.url_path_for(
            "comments:delete-comment-from-article",
            slug=test_article.slug,
            comment_id=str(comment.id_),
        )
    )

    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN


async def test_user_will_receive_error_for_not_existing_comment(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    not_found_response = await authorized_client.delete(
        app.url_path_for(
            "comments:delete-comment-from-article",
            slug=test_article.slug,
            comment_id="1",
        )
    )

    assert not_found_response.status_code == status.HTTP_404_NOT_FOUND


async def test_comments_default_sort_is_desc(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article, pool: Pool
) -> None:
    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.create_user(
            username="commenter", email="commenter@email.com", password="password"
        )
        comments_repo = CommentsRepository(connection)
        first = await comments_repo.create_comment_for_article(
            body="first", article=test_article, user=user
        )
        # Ensure different created_at timestamps
        await asyncio.sleep(0.05)
        second = await comments_repo.create_comment_for_article(
            body="second", article=test_article, user=user
        )

    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug)
    )
    data = ListOfCommentsInResponse(**response.json())

    assert data.comments_count == 2
    assert len(data.comments) == 2
    # Default desc => newest first
    assert data.comments[0].id_ == second.id_
    assert data.comments[1].id_ == first.id_


async def test_comments_sort_asc(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article, pool: Pool
) -> None:
    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.create_user(
            username="commenter_asc", email="asc@email.com", password="password"
        )
        comments_repo = CommentsRepository(connection)
        first = await comments_repo.create_comment_for_article(
            body="first", article=test_article, user=user
        )
        await asyncio.sleep(0.05)
        second = await comments_repo.create_comment_for_article(
            body="second", article=test_article, user=user
        )

    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"sort": "asc"},
    )
    data = ListOfCommentsInResponse(**response.json())

    assert data.comments_count == 2
    assert data.comments[0].id_ == first.id_
    assert data.comments[1].id_ == second.id_


async def test_comments_pagination_limit_and_offset(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article, pool: Pool
) -> None:
    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.create_user(
            username="paginator", email="paginator@email.com", password="password"
        )
        comments_repo = CommentsRepository(connection)
        created = []
        for i in range(5):
            c = await comments_repo.create_comment_for_article(
                body=f"comment-{i}", article=test_article, user=user
            )
            created.append(c)

    # Page 1: limit=2, offset=0, default desc => newest first
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"limit": 2, "offset": 0, "sort": "asc"},
    )
    page1 = ListOfCommentsInResponse(**response.json())
    assert page1.comments_count == 5
    assert len(page1.comments) == 2
    assert page1.comments[0].id_ == created[0].id_
    assert page1.comments[1].id_ == created[1].id_

    # Page 2: limit=2, offset=2
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"limit": 2, "offset": 2, "sort": "asc"},
    )
    page2 = ListOfCommentsInResponse(**response.json())
    assert page2.comments_count == 5
    assert len(page2.comments) == 2
    assert page2.comments[0].id_ == created[2].id_
    assert page2.comments[1].id_ == created[3].id_

    # Page 3: limit=2, offset=4 => only 1 left
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"limit": 2, "offset": 4, "sort": "asc"},
    )
    page3 = ListOfCommentsInResponse(**response.json())
    assert page3.comments_count == 5
    assert len(page3.comments) == 1
    assert page3.comments[0].id_ == created[4].id_


async def test_comments_invalid_limit(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"limit": 0},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_comments_invalid_offset(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"offset": -1},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_comments_invalid_sort(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug),
        params={"sort": "invalid"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_comments_empty_list(
    app: FastAPI, authorized_client: AsyncClient, test_article: Article
) -> None:
    response = await authorized_client.get(
        app.url_path_for("comments:get-comments-for-article", slug=test_article.slug)
    )
    data = ListOfCommentsInResponse(**response.json())
    assert data.comments == []
    assert data.comments_count == 0
