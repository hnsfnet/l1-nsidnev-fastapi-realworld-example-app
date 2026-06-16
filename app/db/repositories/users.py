from typing import Any, Dict

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.users import User, UserInDB


class UsersRepository(BaseRepository):
    async def get_user_by_email(self, *, email: str) -> UserInDB:
        user_row = await queries.get_user_by_email(self.connection, email=email)
        if user_row:
            return UserInDB(**user_row)

        raise EntityDoesNotExist("user with email {0} does not exist".format(email))

    async def get_user_by_username(self, *, username: str) -> UserInDB:
        user_row = await queries.get_user_by_username(
            self.connection,
            username=username,
        )
        if user_row:
            return UserInDB(**user_row)

        raise EntityDoesNotExist(
            "user with username {0} does not exist".format(username),
        )

    async def check_username_exists_ci(self, *, username: str) -> bool:
        result = await queries.check_username_exists_ci(
            self.connection, username=username
        )
        return result is not None

    async def check_email_exists_ci(self, *, email: str) -> bool:
        result = await queries.check_email_exists_ci(
            self.connection, email=email
        )
        return result is not None

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> UserInDB:
        user = UserInDB(username=username, email=email)
        user.change_password(password)

        async with self.connection.transaction():
            user_row = await queries.create_new_user(
                self.connection,
                username=user.username,
                email=user.email,
                salt=user.salt,
                hashed_password=user.hashed_password,
            )

        return user.copy(update=dict(user_row))

    async def update_user(  # noqa: WPS211
        self,
        *,
        user: User,
        update_data: Dict[str, Any],
    ) -> UserInDB:
        user_in_db = await self.get_user_by_username(username=user.username)

        # Apply only explicitly provided fields (exclude_unset already done by caller)
        if "username" in update_data and update_data["username"]:
            user_in_db.username = update_data["username"]
        if "email" in update_data and update_data["email"]:
            user_in_db.email = update_data["email"]
        if "bio" in update_data:
            # Allow clearing bio to empty string
            user_in_db.bio = update_data["bio"] if update_data["bio"] is not None else ""
        if "image" in update_data:
            # Allow clearing image to None/empty
            user_in_db.image = update_data["image"] or ""
        if "password" in update_data and update_data["password"]:
            user_in_db.change_password(update_data["password"])

        async with self.connection.transaction():
            user_in_db.updated_at = await queries.update_user_by_username(
                self.connection,
                username=user.username,
                new_username=user_in_db.username,
                new_email=user_in_db.email,
                new_salt=user_in_db.salt,
                new_password=user_in_db.hashed_password,
                new_bio=user_in_db.bio,
                new_image=user_in_db.image,
            )

        return user_in_db
