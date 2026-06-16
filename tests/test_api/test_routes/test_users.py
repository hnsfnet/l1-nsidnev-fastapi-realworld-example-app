import pytest
from asyncpg.pool import Pool
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from app.db.repositories.users import UsersRepository
from app.models.domain.users import UserInDB
from app.models.schemas.users import UserInResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture(params=("", "value", "Token value", "JWT value", "Bearer value"))
def wrong_authorization_header(request) -> str:
    return request.param


@pytest.mark.parametrize(
    "api_method, route_name",
    (("GET", "users:get-current-user"), ("PUT", "users:update-current-user")),
)
async def test_user_can_not_access_own_profile_if_not_logged_in(
    app: FastAPI,
    client: AsyncClient,
    test_user: UserInDB,
    api_method: str,
    route_name: str,
) -> None:
    response = await client.request(api_method, app.url_path_for(route_name))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    "api_method, route_name",
    (("GET", "users:get-current-user"), ("PUT", "users:update-current-user")),
)
async def test_user_can_not_retrieve_own_profile_if_wrong_token(
    app: FastAPI,
    client: AsyncClient,
    test_user: UserInDB,
    api_method: str,
    route_name: str,
    wrong_authorization_header: str,
) -> None:
    response = await client.request(
        api_method,
        app.url_path_for(route_name),
        headers={"Authorization": wrong_authorization_header},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_user_can_retrieve_own_profile(
    app: FastAPI, authorized_client: AsyncClient, test_user: UserInDB, token: str
) -> None:
    response = await authorized_client.get(app.url_path_for("users:get-current-user"))
    assert response.status_code == status.HTTP_200_OK

    user_profile = UserInResponse(**response.json())
    assert user_profile.user.email == test_user.email


@pytest.mark.parametrize(
    "update_field, update_value",
    (
        ("username", "new_username"),
        ("email", "new_email@email.com"),
        ("bio", "new bio"),
        ("image", "http://testhost.com/imageurl"),
    ),
)
async def test_user_can_update_own_profile(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    update_value: str,
    update_field: str,
) -> None:
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {update_field: update_value}},
    )
    assert response.status_code == status.HTTP_200_OK

    user_profile = UserInResponse(**response.json()).dict()
    assert user_profile["user"][update_field] == update_value


async def test_user_can_change_password(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    pool: Pool,
) -> None:
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"password": "new_password"}},
    )
    assert response.status_code == status.HTTP_200_OK
    user_profile = UserInResponse(**response.json())

    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.get_user_by_username(
            username=user_profile.user.username
        )

    assert user.check_password("new_password")


@pytest.mark.parametrize(
    "credentials_part, credentials_value",
    (("username", "taken_username"), ("email", "taken@email.com")),
)
async def test_user_can_not_take_already_used_credentials(
    app: FastAPI,
    authorized_client: AsyncClient,
    pool: Pool,
    token: str,
    credentials_part: str,
    credentials_value: str,
) -> None:
    user_dict = {
        "username": "not_taken_username",
        "password": "password",
        "email": "free_email@email.com",
    }
    user_dict.update({credentials_part: credentials_value})
    async with pool.acquire() as conn:
        users_repo = UsersRepository(conn)
        await users_repo.create_user(**user_dict)

    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {credentials_part: credentials_value}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "update_field, setup_value, clear_value, expected",
    (
        ("bio", "some bio", "", ""),
        ("bio", "some bio", None, ""),
        ("image", "http://testhost.com/imageurl", None, None),
    ),
)
async def test_user_can_clear_optional_profile_fields(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    update_field: str,
    setup_value: str,
    clear_value,
    expected,
) -> None:
    await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {update_field: setup_value}},
    )

    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {update_field: clear_value}},
    )
    assert response.status_code == status.HTTP_200_OK

    user_profile = UserInResponse(**response.json()).dict()
    assert user_profile["user"][update_field] == expected


@pytest.mark.parametrize(
    "credentials_part, taken_value, attempt_value",
    (
        ("username", "TakenUser", "takenuser"),
        ("username", "TakenUser", "TAKENUSER"),
        ("email", "TakenCI@test.com", "takenCI@test.com"),
    ),
)
async def test_user_can_not_take_already_used_credentials_case_insensitive(
    app: FastAPI,
    authorized_client: AsyncClient,
    pool: Pool,
    token: str,
    credentials_part: str,
    taken_value: str,
    attempt_value: str,
) -> None:
    user_dict = {
        "username": "not_taken_ci",
        "password": "password",
        "email": "free_ci@email.com",
    }
    user_dict.update({credentials_part: taken_value})
    async with pool.acquire() as conn:
        users_repo = UsersRepository(conn)
        await users_repo.create_user(**user_dict)

    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {credentials_part: attempt_value}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "invalid_password",
    ("", "   "),
)
async def test_user_can_not_set_empty_password(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    invalid_password: str,
) -> None:
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"password": invalid_password}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_empty_password_does_not_corrupt_existing_password(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    pool: Pool,
) -> None:
    await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"password": ""}},
    )

    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        user = await users_repo.get_user_by_username(username=test_user.username)

    assert user.check_password("password")


async def test_update_response_contains_valid_token(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
) -> None:
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"username": "updated_name"}},
    )
    assert response.status_code == status.HTTP_200_OK

    user_profile = UserInResponse(**response.json())
    assert user_profile.user.token
    assert user_profile.user.username == "updated_name"
