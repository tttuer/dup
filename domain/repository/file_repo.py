from abc import ABCMeta, abstractmethod


class IFileRepository(metaclass=ABCMeta):
    @abstractmethod
    def get_file_list(self):
        pass
