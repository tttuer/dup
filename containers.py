from dependency_injector import containers, providers

from application.voucher_service import VoucherService
from application.file_service import FileService
from application.user_service import UserService
from infra.repository.file_repo import FileRepository
from infra.repository.user_repo import UserRepository
from infra.repository.voucher_repo import VoucherRepository
from infra.repository.group_repo import GroupRepository
from application.group_service import GroupService
from application.websocket_manager import WebSocketManager
from application.sync_service import SyncService

class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["domain", "application", "infra", "interface"]
    )

    user_repo = providers.Factory(UserRepository)
    user_service = providers.Factory(UserService, user_repo=user_repo)

    file_repo = providers.Factory(FileRepository)
    file_service = providers.Factory(FileService, file_repo=file_repo)

    voucher_repo = providers.Factory(VoucherRepository)
    voucher_service = providers.Factory(VoucherService, voucher_repo=voucher_repo)

    group_repo = providers.Factory(GroupRepository)
    group_service = providers.Factory(GroupService, group_repo=group_repo, file_repo=file_repo)  # Assuming GroupRepository is similar to FileRepository
    
    sync_service = providers.Factory(SyncService)
    websocket_manager = providers.Factory(WebSocketManager)