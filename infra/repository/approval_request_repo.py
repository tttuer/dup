from typing import List, Optional

from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.approval_request import ApprovalRequest as ApprovalRequestVo
from infra.db_models.approval_request import ApprovalRequest
from infra.repository.base_repo import BaseRepository
from common.auth import DocumentStatus
from beanie.operators import In


class ApprovalRequestRepository(BaseRepository[ApprovalRequest], IApprovalRequestRepository):
    def __init__(self):
        super().__init__(ApprovalRequest)

    async def save(self, request: ApprovalRequestVo) -> None:
        new_request = ApprovalRequest(
            id=request.id,
            template_id=request.template_id,
            document_number=request.document_number,
            title=request.title,
            content=request.content,
            form_data=request.form_data,
            requester_id=request.requester_id,
            requester_name=request.requester_name,
            department_id=request.department_id,
            status=request.status,
            current_step=request.current_step,
            created_at=request.created_at,
            updated_at=request.updated_at,
            submitted_at=request.submitted_at,
            completed_at=request.completed_at,
        )
        await new_request.insert()

    async def find_by_id(self, request_id: str) -> Optional[ApprovalRequest]:
        return await ApprovalRequest.get(request_id)
    
    async def find_by_requester_id(self, requester_id: str, skip: int = 0, limit: int = 20) -> List[ApprovalRequest]:
        requests = await ApprovalRequest.find(
            ApprovalRequest.requester_id == requester_id
        ).sort(-ApprovalRequest.created_at).skip(skip).limit(limit).to_list()
        return requests or []
    
    async def find_by_status(self, status: DocumentStatus, skip: int = 0, limit: int = 20) -> List[ApprovalRequest]:
        requests = await ApprovalRequest.find(
            ApprovalRequest.status == status
        ).sort(-ApprovalRequest.created_at).skip(skip).limit(limit).to_list()
        return requests or []
    
    async def find_by_approver_id(self, approver_id: str, skip: int = 0, limit: int = 20) -> List[ApprovalRequest]:
        # Aggregation Pipeline으로 한 번에 조회 (성능 최적화)
        from infra.db_models.approval_line import ApprovalLine
        
        pipeline = [
            # 1. ApprovalLine과 조인
            {
                "$lookup": {
                    "from": "approval_lines",
                    "localField": "_id", 
                    "foreignField": "request_id",
                    "as": "approval_lines"
                }
            },
            # 2. 해당 결재자가 포함된 요청만 필터링
            {
                "$match": {
                    "approval_lines.approver_id": approver_id
                }
            },
            # 3. 생성일 기준 정렬
            {
                "$sort": {"created_at": -1}
            },
            # 4. 페이지네이션
            {
                "$skip": skip
            },
            {
                "$limit": limit
            },
            # 5. approval_lines 필드 제거 (불필요한 데이터)
            {
                "$unset": "approval_lines"
            }
        ]
        
        results = await ApprovalRequest.aggregate(pipeline).to_list()
        return [ApprovalRequest(**doc) for doc in results] if results else []
    
    async def update(self, request: ApprovalRequestVo) -> ApprovalRequest:
        db_request = await self.find_by_id_or_raise(request.id, "ApprovalRequest")
        db_request.template_id = request.template_id
        db_request.document_number = request.document_number
        db_request.title = request.title
        db_request.content = request.content
        db_request.form_data = request.form_data
        db_request.requester_id = request.requester_id
        db_request.department_id = request.department_id
        db_request.status = request.status
        db_request.current_step = request.current_step
        db_request.updated_at = request.updated_at
        db_request.submitted_at = request.submitted_at
        db_request.completed_at = request.completed_at
        
        return await db_request.save()
    
    async def delete(self, request_id: str) -> None:
        await self.delete_by_id(request_id)
    
    async def find_by_document_number(self, document_number: str) -> Optional[ApprovalRequest]:
        return await ApprovalRequest.find_one(ApprovalRequest.document_number == document_number)
    
    async def search_by_query(self, query: dict, skip: int = 0, limit: int = 50) -> List[ApprovalRequest]:
        """MongoDB 쿼리로 전자결재 검색"""
        requests = await ApprovalRequest.find(query).sort(-ApprovalRequest.created_at).skip(skip).limit(limit).to_list()
        return requests or []
    
    async def find_by_ids(self, request_ids: List[str]) -> List[ApprovalRequest]:
        """여러 request_id의 결재 요청을 한 번에 조회"""
        if not request_ids:
            return []
            
        requests = await ApprovalRequest.find(
            In(ApprovalRequest.id, request_ids)
        ).sort(-ApprovalRequest.updated_at).to_list()
        return requests or []
    
    async def count_by_requester_id(self, requester_id: str, status: Optional[DocumentStatus] = None) -> int:
        """기안자별 결재 요청 수 카운트"""
        query = {"requester_id": requester_id}
        if status:
            query["status"] = status
        return await ApprovalRequest.find(query).count()
    
    async def count_by_approver_id(self, request_ids: List[str]) -> int:
        """결재자별 결재 요청 수 카운트"""
        if not request_ids:
            return 0
        return await ApprovalRequest.find(In(ApprovalRequest.id, request_ids)).count()