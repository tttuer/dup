from abc import ABCMeta, abstractmethod


class IUserRepository(metaclass=ABCMeta):

    @abstractmethod
    def save(self, user):
        raise NotImplementedError
