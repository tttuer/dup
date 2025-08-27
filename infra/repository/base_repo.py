from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Any
from beanie import Document
from common.exceptions import NotFoundError, InternalServerError

T = TypeVar('T', bound=Document)


class BaseRepository(ABC, Generic[T]):
    """Base repository class providing common CRUD operations."""
    
    def __init__(self, model: type[T]):
        self.model = model
    
    async def create(self, entity: T) -> T:
        """Create a new entity in the database.
        
        Args:
            entity: The entity to create
            
        Returns:
            T: The created entity
            
        Raises:
            InternalServerError: if creation fails
        """
        try:
            return await entity.insert()
        except Exception as e:
            raise InternalServerError(f"Failed to create {self.model.__name__}: {str(e)}")
    
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to find
            
        Returns:
            Optional[T]: The entity if found, None otherwise
        """
        try:
            return await self.model.get(entity_id)
        except Exception:
            return None
    
    async def find_by_id_or_raise(self, entity_id: str, entity_name: str = None) -> T:
        """Find an entity by its ID or raise an exception.
        
        Args:
            entity_id: The ID of the entity to find
            entity_name: Custom name for error message
            
        Returns:
            T: The entity if found
            
        Raises:
            NotFoundError: if entity is not found
        """
        entity = await self.find_by_id(entity_id)
        if not entity:
            name = entity_name or self.model.__name__
            raise NotFoundError(f"{name} not found: {entity_id}")
        return entity
    
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Find all entities with pagination.
        
        Args:
            skip: Number of entities to skip
            limit: Maximum number of entities to return
            
        Returns:
            List[T]: List of entities
        """
        return await self.model.find().skip(skip).limit(limit).to_list()
    
    async def update(self, entity: T) -> T:
        """Update an existing entity.
        
        Args:
            entity: The entity to update
            
        Returns:
            T: The updated entity
            
        Raises:
            InternalServerError: if update fails
        """
        try:
            return await entity.save()
        except Exception as e:
            raise InternalServerError(f"Failed to update {self.model.__name__}: {str(e)}")
    
    async def delete(self, entity: T) -> bool:
        """Delete an entity.
        
        Args:
            entity: The entity to delete
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            InternalServerError: if deletion fails
        """
        try:
            await entity.delete()
            return True
        except Exception as e:
            raise InternalServerError(f"Failed to delete {self.model.__name__}: {str(e)}")
    
    async def delete_by_id(self, entity_id: str) -> bool:
        """Delete an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to delete
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            NotFoundError: if entity is not found
            InternalServerError: if deletion fails
        """
        entity = await self.find_by_id_or_raise(entity_id)
        return await self.delete(entity)
    
    async def count(self, *filters: Any) -> int:
        """Count entities matching the given filters.
        
        Args:
            *filters: Filter conditions
            
        Returns:
            int: Number of matching entities
        """
        query = self.model.find()
        for filter_condition in filters:
            query = query.find(filter_condition)
        return await query.count()
    
    async def exists(self, *filters: Any) -> bool:
        """Check if any entity matches the given filters.
        
        Args:
            *filters: Filter conditions
            
        Returns:
            bool: True if at least one entity matches
        """
        return await self.count(*filters) > 0