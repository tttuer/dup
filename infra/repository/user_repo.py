from fastapi import HTTPException

from domain.repository.user_repo import IUserRepository
from domain.user import User as UserVo
from infra.db_models.user import User


class UserRepository(IUserRepository):
    async def save(self, user: UserVo):
        new_user = User(
            id=user.id,
            user_id=user.user_id,
            password=user.password,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        await new_user.insert()

    async def find_by_user_id(self, user_id) -> User:
        user = await User.find_one(User.user_id == user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found:{user_id}",
            )
        return user
