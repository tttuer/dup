from dependency_injector import containers, providers

from application.file_service import FileService
from application.user_service import UserService
from infra.repository.file_repo import FileRepository
from infra.repository.user_repo import UserRepository


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["domain", "application", "infra", "interface"]
    )

    user_repo = providers.Factory(UserRepository)
    user_service = providers.Factory(UserService, user_repo=user_repo)

    file_repo = providers.Factory(FileRepository)
    file_service = providers.Factory(FileService, file_repo=file_repo)
