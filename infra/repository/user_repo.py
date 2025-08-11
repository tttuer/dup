from common.auth import ApprovalStatus
from common.exceptions import NotFoundError
from domain.repository.user_repo import IUserRepository
from domain.user import User as UserVo
from infra.db_models.user import User
from infra.repository.base_repo import BaseRepository


class UserRepository(BaseRepository[User], IUserRepository):
    def __init__(self):
        super().__init__(User)
    async def save(self, user: UserVo):
        new_user = User(
            id=user.id,
            user_id=user.user_id,
            name=user.name,
            password=user.password,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=user.roles,
            approval_status=user.approval_status,
        )

        await new_user.insert()

    async def find_by_user_id(self, user_id) -> User:
        user = await User.find_one(User.user_id == user_id)
        if not user:
            return None
        return user
    
    async def find(self) -> list[User]:
        users = await User.find().to_list()
        if not users:
            return []
        return users
    
    async def update(self, user: UserVo):
        db_user = await User.get(user.id)
        if not db_user:
            raise NotFoundError("User not found")
        db_user.name = user.name
        db_user.password = user.password
        db_user.roles = user.roles
        db_user.updated_at = user.updated_at
        updated_user = await db_user.save()
        
        return updated_user

    async def find_by_approval_status(self, approval_status: ApprovalStatus) -> list[User]:
        users = await User.find(User.approval_status == approval_status).to_list()
        return users or []
