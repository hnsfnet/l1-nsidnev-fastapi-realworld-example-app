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


async def test_user_can_clear_bio(
    app: FastAPI, authorized_client: AsyncClient, test_user: UserInDB, token: str
) -> None:
    # First, set bio to a non-empty value
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"bio": "some bio content"}},
    )
    assert response.status_code == status.HTTP_200_OK
    assert UserInResponse(**response.json()).user.bio == "some bio content"

    # Now clear bio by sending empty string
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"bio": ""}},
    )
    assert response.status_code == status.HTTP_200_OK
    assert UserInResponse(**response.json()).user.bio == ""


async def test_user_can_clear_image(
    app: FastAPI, authorized_client: AsyncClient, test_user: UserInDB, token: str
) -> None:
    # First, set image to a URL
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"image": "http://example.com/avatar.png"}},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "example.com" in UserInResponse(**response.json()).user.image

    # Now clear image by sending empty string
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"image": ""}},
    )
    assert response.status_code == status.HTTP_200_OK
    user_image = UserInResponse(**response.json()).user.image
    assert user_image in ("", None)


async def test_empty_password_is_rejected(
    app: FastAPI, authorized_client: AsyncClient, test_user: UserInDB, token: str
) -> None:
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"password": ""}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_user_can_not_take_username_case_insensitive(
    app: FastAPI, authorized_client: AsyncClient, pool: Pool, token: str
) -> None:
    # Create a user with a specific username (different from test_user "username")
    async with pool.acquire() as conn:
        users_repo = UsersRepository(conn)
        await users_repo.create_user(
            username="taken_name",
            email="ci_taken@email.com",
            password="password",
        )

    # Try to change to a case variation — should be rejected
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"username": "Taken_Name"}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_user_can_not_take_email_case_insensitive(
    app: FastAPI, authorized_client: AsyncClient, pool: Pool, token: str
) -> None:
    # Create a user with a specific email (different from test_user "test@test.com")
    async with pool.acquire() as conn:
        users_repo = UsersRepository(conn)
        await users_repo.create_user(
            username="ci_email_user",
            email="taken@email.com",
            password="password",
        )

    # Try to change to a case variation — should be rejected
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"email": "Taken@Email.com"}},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_user_can_change_own_username_case(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    pool: Pool,
) -> None:
    # Changing own username case (username → UserName) should succeed
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"username": "UserName"}},
    )
    assert response.status_code == status.HTTP_200_OK
    user_profile = UserInResponse(**response.json())
    assert user_profile.user.username == "UserName"
    assert user_profile.user.token  # Token is still returned

    # Verify the change persisted in DB
    async with pool.acquire() as conn:
        users_repo = UsersRepository(conn)
        user_from_db = await users_repo.get_user_by_username(username="UserName")
    assert user_from_db.username == "UserName"


async def test_user_can_change_own_email_case(
    app: FastAPI, authorized_client: AsyncClient, test_user: UserInDB, token: str
) -> None:
    # Changing own email case (test@test.com → Test@Test.com) should succeed
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"email": "Test@Test.com"}},
    )
    assert response.status_code == status.HTTP_200_OK
    user_profile = UserInResponse(**response.json())
    assert user_profile.user.email == "Test@Test.com"


async def test_token_remains_valid_after_profile_update(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    token: str,
    authorization_prefix: str,
) -> None:
    # Update bio and verify the token in the response can still authenticate
    response = await authorized_client.put(
        app.url_path_for("users:update-current-user"),
        json={"user": {"bio": "updated bio"}},
    )
    assert response.status_code == status.HTTP_200_OK
    new_token = UserInResponse(**response.json()).user.token

    # Use the new token to fetch the profile
    response = await authorized_client.get(
        app.url_path_for("users:get-current-user"),
        headers={"Authorization": f"{authorization_prefix} {new_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert UserInResponse(**response.json()).user.bio == "updated bio"
