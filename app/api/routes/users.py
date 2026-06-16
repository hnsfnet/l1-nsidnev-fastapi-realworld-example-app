from fastapi import APIRouter, Body, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.core.config import get_app_settings
from app.core.settings.app import AppSettings
from app.db.repositories.users import UsersRepository
from app.models.domain.users import User
from app.models.schemas.users import UserInResponse, UserInUpdate, UserWithToken
from app.resources import strings
from app.services import jwt
from app.services.authentication import check_email_is_taken, check_username_is_taken

router = APIRouter()


@router.get("", response_model=UserInResponse, name="users:get-current-user")
async def retrieve_current_user(
    user: User = Depends(get_current_user_authorizer()),
    settings: AppSettings = Depends(get_app_settings),
) -> UserInResponse:
    token = jwt.create_access_token_for_user(
        user,
        str(settings.secret_key.get_secret_value()),
    )
    return UserInResponse(
        user=UserWithToken(
            username=user.username,
            email=user.email,
            bio=user.bio,
            image=user.image,
            token=token,
        ),
    )


@router.put(  # noqa: WPS231
    "",
    response_model=UserInResponse,
    name="users:update-current-user",
)
async def update_current_user(
    user_update: UserInUpdate = Body(..., embed=True, alias="user"),
    current_user: User = Depends(get_current_user_authorizer()),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
    settings: AppSettings = Depends(get_app_settings),
) -> UserInResponse:
    update_dict = user_update.dict(exclude_unset=True)

    if "password" in update_dict:
        if update_dict["password"] is None:
            del update_dict["password"]
        elif not update_dict["password"].strip():
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=strings.INVALID_PASSWORD,
            )

    if "username" in update_dict:
        if update_dict["username"].lower() != current_user.username.lower():
            if await check_username_is_taken(users_repo, update_dict["username"]):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail=strings.USERNAME_TAKEN,
                )
        elif update_dict["username"] == current_user.username:
            del update_dict["username"]

    if "email" in update_dict:
        if update_dict["email"].lower() != current_user.email.lower():
            if await check_email_is_taken(users_repo, update_dict["email"]):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail=strings.EMAIL_TAKEN,
                )
        elif update_dict["email"] == current_user.email:
            del update_dict["email"]

    if "bio" in update_dict:
        effective_bio = update_dict["bio"] or ""
        if effective_bio == current_user.bio:
            del update_dict["bio"]

    if "image" in update_dict:
        effective_image = (
            str(update_dict["image"]) if update_dict["image"] else None
        )
        if effective_image == current_user.image:
            del update_dict["image"]

    if update_dict:
        user = await users_repo.update_user(user=current_user, **update_dict)
    else:
        user = current_user

    token = jwt.create_access_token_for_user(
        user,
        str(settings.secret_key.get_secret_value()),
    )
    return UserInResponse(
        user=UserWithToken(
            username=user.username,
            email=user.email,
            bio=user.bio,
            image=user.image,
            token=token,
        ),
    )
