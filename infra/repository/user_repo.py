from fastapi import HTTPException

from domain.repository.user_repo import IUserRepository
from domain.user import User as UserVo
from infra.db_models.user import User


class UserRepository(IUserRepository):
    async def save(self, user: UserVo):
        new_user = User(
            id=user.id,
            user_id=user.user_id,
            name=user.name,
            password=user.password,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=user.roles,
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
    
    async def find(self) -> list[User]:
        users = await User.find().to_list()
        if not users:
            return []
        return [UserVo(**user.model_dump()) for user in users]
    
    async def update(self, user: UserVo):
        db_user = await User.find_one(User.id == user.id)
        if not db_user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found: {user.id}",
            )
        db_user.name = user.name
        db_user.password = user.password
        db_user.roles = user.roles
        db_user.updated_at = user.updated_at
        await db_user.save()
        
        return UserVo(**db_user.model_dump())
