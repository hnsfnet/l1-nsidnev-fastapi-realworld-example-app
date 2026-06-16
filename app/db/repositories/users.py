from typing import Optional, Union

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.users import User, UserInDB

_UNSET = object()


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

    async def get_user_by_email_ci(self, *, email: str) -> UserInDB:
        user_row = await queries.get_user_by_email_ci(
            self.connection,
            email=email,
        )
        if user_row:
            return UserInDB(**user_row)

        raise EntityDoesNotExist("user with email {0} does not exist".format(email))

    async def get_user_by_username_ci(self, *, username: str) -> UserInDB:
        user_row = await queries.get_user_by_username_ci(
            self.connection,
            username=username,
        )
        if user_row:
            return UserInDB(**user_row)

        raise EntityDoesNotExist(
            "user with username {0} does not exist".format(username),
        )

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
        username: Union[str, object] = _UNSET,
        email: Union[str, object] = _UNSET,
        password: Union[str, object] = _UNSET,
        bio: Union[Optional[str], object] = _UNSET,
        image: Union[Optional[str], object] = _UNSET,
    ) -> UserInDB:
        user_in_db = await self.get_user_by_username(username=user.username)

        if username is not _UNSET:
            user_in_db.username = username
        if email is not _UNSET:
            user_in_db.email = email
        if bio is not _UNSET:
            user_in_db.bio = bio if bio is not None else ""
        if image is not _UNSET:
            user_in_db.image = image
        if password is not _UNSET:
            user_in_db.change_password(password)

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
