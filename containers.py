from dependency_injector import containers, providers
from redis.asyncio import Redis

from application.voucher_service import VoucherService
from application.file_service import FileService
from application.user_service import UserService
from application.document_template_service import DocumentTemplateService
from application.approval_service import ApprovalService
from application.approval_line_service import ApprovalLineService
from application.approval_favorite_group_service import ApprovalFavoriteGroupService
from application.document_number_service import DocumentNumberService
from application.file_attachment_service import FileAttachmentService
from application.integrity_service import IntegrityService
from application.legal_archive_service import LegalArchiveService
from infra.repository.file_repo import FileRepository
from infra.repository.user_repo import UserRepository
from infra.repository.voucher_repo import VoucherRepository
from infra.repository.group_repo import GroupRepository
from infra.repository.document_template_repo import DocumentTemplateRepository
from infra.repository.approval_request_repo import ApprovalRequestRepository
from infra.repository.approval_line_repo import ApprovalLineRepository
from infra.repository.approval_favorite_group_repo import ApprovalFavoriteGroupRepository
from infra.repository.approval_history_repo import ApprovalHistoryRepository
from infra.repository.attached_file_repo import AttachedFileRepository
from infra.repository.document_integrity_repo import DocumentIntegrityRepository
from application.group_service import GroupService
from application.websocket_manager import WebSocketManager
from application.approval_notification_service import ApprovalNotificationService
from application.sync_service import SyncService
from utils.settings import settings

class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["domain", "application", "infra", "interface"]
    )
    
        # 환경 설정
    config = providers.Configuration()
    config.redis.host.from_value(settings.redis_host)
    config.redis.port.from_value(settings.redis_port)
    config.redis.password.from_value(settings.redis_password)

    redis = providers.Singleton(
        Redis,
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password,
        decode_responses=True,
    )

    user_repo = providers.Factory(UserRepository)
    user_service = providers.Factory(UserService, user_repo=user_repo, redis=redis)

    file_repo = providers.Factory(FileRepository)
    file_service = providers.Factory(FileService, file_repo=file_repo, user_repo=user_repo)

    voucher_repo = providers.Factory(VoucherRepository)
    voucher_service = providers.Factory(VoucherService, voucher_repo=voucher_repo)

    group_repo = providers.Factory(GroupRepository)
    group_service = providers.Factory(GroupService, group_repo=group_repo, file_repo=file_repo, user_repo=user_repo)
    
    # 전자결재 시스템 리포지토리
    document_template_repo = providers.Factory(DocumentTemplateRepository)
    approval_request_repo = providers.Factory(ApprovalRequestRepository)
    approval_line_repo = providers.Factory(ApprovalLineRepository)
    approval_favorite_group_repo = providers.Factory(ApprovalFavoriteGroupRepository)
    approval_history_repo = providers.Factory(ApprovalHistoryRepository)
    attached_file_repo = providers.Factory(AttachedFileRepository)
    document_integrity_repo = providers.Factory(DocumentIntegrityRepository)
    
    # 전자결재 시스템 서비스
    document_template_service = providers.Factory(
        DocumentTemplateService,
        template_repo=document_template_repo,
        user_repo=user_repo
    )
    
    approval_line_service = providers.Factory(
        ApprovalLineService,
        line_repo=approval_line_repo,
        approval_repo=approval_request_repo,
        user_repo=user_repo
    )
    
    approval_favorite_group_service = providers.Factory(
        ApprovalFavoriteGroupService,
        favorite_group_repo=approval_favorite_group_repo,
        user_repo=user_repo
    )
    
    document_number_service = providers.Factory(
        DocumentNumberService,
        template_repo=document_template_repo,
        approval_repo=approval_request_repo,
        user_repo=user_repo
    )
    
    file_attachment_service = providers.Factory(
        FileAttachmentService,
        file_repo=attached_file_repo,
        approval_repo=approval_request_repo,
        line_repo=approval_line_repo,
        user_repo=user_repo
    )
    
    websocket_manager = providers.Singleton(WebSocketManager)
    
    approval_notification_service = providers.Factory(
        ApprovalNotificationService,
        websocket_manager=websocket_manager,
        approval_line_repo=approval_line_repo,
        approval_request_repo=approval_request_repo
    )

    # 무결성 및 법적 아카이브 서비스
    integrity_service = providers.Factory(
        IntegrityService,
        integrity_repo=document_integrity_repo,
        approval_repo=approval_request_repo,
        line_repo=approval_line_repo,
        history_repo=approval_history_repo,
        user_repo=user_repo
    )
    
    legal_archive_service = providers.Factory(
        LegalArchiveService,
        approval_repo=approval_request_repo,
        line_repo=approval_line_repo,
        history_repo=approval_history_repo,
        user_repo=user_repo,
        file_repo=attached_file_repo
    )

    approval_service = providers.Factory(
        ApprovalService,
        approval_repo=approval_request_repo,
        line_repo=approval_line_repo,
        history_repo=approval_history_repo,
        template_repo=document_template_repo,
        user_repo=user_repo,
        notification_service=approval_notification_service,
        file_service=file_attachment_service,
        integrity_service=integrity_service,
        legal_archive_service=legal_archive_service
    )

    sync_service = providers.Factory(SyncService, redis=redis)
