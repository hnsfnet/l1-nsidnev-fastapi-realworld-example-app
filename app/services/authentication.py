from app.db.repositories.users import UsersRepository


async def check_username_is_taken(repo: UsersRepository, username: str) -> bool:
    return await repo.check_username_exists_ci(username=username)


async def check_email_is_taken(repo: UsersRepository, email: str) -> bool:
    return await repo.check_email_exists_ci(email=email)
