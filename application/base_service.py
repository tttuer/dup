from abc import ABC
from typing import TypeVar, Generic, Optional
from fastapi import HTTPException

from domain.user import User
from domain.repository.user_repo import IUserRepository

T = TypeVar('T')


class BaseService(ABC, Generic[T]):
    """Base service class providing common functionality for all services."""
    
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo
    
    async def validate_user_exists(self, user_id: str) -> User:
        """Validate that a user exists and return the user object.
        
        Args:
            user_id: The user_id field of the user to validate
            
        Returns:
            User: The user object if found
            
        Raises:
            HTTPException: 404 if user is not found
        """
        user = await self.user_repo.find_by_user_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        return user
    
    async def validate_user_is_admin(self, user_id: str) -> User:
        """Validate that a user exists and is an admin.
        
        Args:
            user_id: The ID of the user to validate
            
        Returns:
            User: The user object if found and is admin
            
        Raises:
            HTTPException: 404 if user is not found, 403 if not admin
        """
        user = await self.validate_user_exists(user_id)
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin privileges required")
        return user
    
    def validate_required_field(self, field_value: Optional[str], field_name: str) -> str:
        """Validate that a required field is not empty.
        
        Args:
            field_value: The value to validate
            field_name: The name of the field for error messages
            
        Returns:
            str: The validated field value
            
        Raises:
            HTTPException: 400 if field is empty or None
        """
        if not field_value or field_value.strip() == "":
            raise HTTPException(status_code=400, detail=f"{field_name} is required")
        return field_value.strip()