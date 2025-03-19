from abc import ABCMeta, abstractmethod


class IUserRepository(metaclass=ABCMeta):

    @abstractmethod
    async def save(self, user):
        raise NotImplementedError

    @abstractmethod
    async def find_by_user_id(self, user_id):
        raise NotImplementedError
