from typing import List, Optional

from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.approval_line import ApprovalLine as ApprovalLineVo
from infra.db_models.approval_line import ApprovalLine
from infra.repository.base_repo import BaseRepository
from common.auth import ApprovalStatus
from utils.logger import logger
from beanie.operators import In


class ApprovalLineRepository(BaseRepository[ApprovalLine], IApprovalLineRepository):
    def __init__(self):
        super().__init__(ApprovalLine)

    async def save(self, line: ApprovalLineVo) -> None:
        new_line = ApprovalLine(
            id=line.id,
            request_id=line.request_id,
            approver_id=line.approver_id,
            approver_name=line.approver_name,
            step_order=line.step_order,
            is_required=line.is_required,
            is_parallel=line.is_parallel,
            status=line.status,
            approved_at=line.approved_at,
            comment=line.comment,
        )
        await new_line.insert()

    async def find_by_id(self, line_id: str) -> Optional[ApprovalLine]:
        return await ApprovalLine.get(line_id)
    
    async def find_by_request_id(self, request_id: str) -> List[ApprovalLine]:
        lines = await ApprovalLine.find(ApprovalLine.request_id == request_id).sort(ApprovalLine.step_order).to_list()
        return lines or []
    
    async def find_by_approver_id(self, approver_id: str, skip: int = 0, limit: int = 20) -> List[ApprovalLine]:
        lines = await ApprovalLine.find(
            ApprovalLine.approver_id == approver_id
        ).sort(-ApprovalLine.approved_at).skip(skip).limit(limit).to_list()
        return lines or []
    
    async def find_by_request_and_step(self, request_id: str, step_order: int) -> List[ApprovalLine]:
        lines = await ApprovalLine.find(
            ApprovalLine.request_id == request_id,
            ApprovalLine.step_order == step_order
        ).to_list()
        return lines or []
    
    async def find_pending_by_approver(self, approver_id: str, skip: int = 0, limit: int = 20) -> List[ApprovalLine]:
        """결재 대기 목록 - 기존 인터페이스 유지"""
        lines = await ApprovalLine.find(
            ApprovalLine.approver_id == approver_id,
            ApprovalLine.status == ApprovalStatus.PENDING
        ).sort(ApprovalLine.step_order).skip(skip).limit(limit).to_list()
        return lines or []
        
    async def find_pending_by_approver_with_filters(self, *filters, sort_field=None, skip: int = 0, limit: int = 20) -> List[ApprovalLine]:
        """결재 대기 목록 - 필터를 받아서 처리"""
        query = ApprovalLine.find(*filters)
        
        if sort_field:
            query = query.sort(sort_field)
        else:
            query = query.sort(ApprovalLine.step_order)  # 기본 정렬
            
        lines = await query.skip(skip).limit(limit).to_list()
        return lines or []
    
    async def find_completed_by_approver(self, approver_id: str, skip: int = 0, limit: int = 20) -> List[ApprovalLine]:
        lines = await ApprovalLine.find(
            ApprovalLine.approver_id == approver_id,
            In(ApprovalLine.status, [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])
        ).sort(-ApprovalLine.approved_at).skip(skip).limit(limit).to_list()
        return lines or []
    
    async def update(self, line: ApprovalLineVo) -> ApprovalLine:
        db_line = await self.find_by_id_or_raise(line.id, "ApprovalLine")
        db_line.request_id = line.request_id
        db_line.approver_id = line.approver_id
        db_line.step_order = line.step_order
        db_line.is_required = line.is_required
        db_line.is_parallel = line.is_parallel
        db_line.status = line.status
        db_line.approved_at = line.approved_at
        db_line.comment = line.comment
        
        return await db_line.save()
    
    async def delete_by_request_id(self, request_id: str) -> None:
        lines = await self.find_by_request_id(request_id)
        for line in lines:
            await line.delete()
    
    async def find_by_request_ids(self, request_ids: List[str]) -> List[ApprovalLine]:
        """여러 request_id의 결재선을 한 번에 조회"""
        if not request_ids:
            return []
        
        lines = await ApprovalLine.find(
            In(ApprovalLine.request_id, request_ids)
        ).sort(ApprovalLine.step_order).to_list()
        return lines or []
    
    async def bulk_save(self, lines: List[ApprovalLineVo]) -> None:
        """여러 결재선을 한 번에 저장"""
        if not lines:
            return
        
        db_lines = []
        for line in lines:
            db_line = ApprovalLine(
                id=line.id,
                request_id=line.request_id,
                approver_id=line.approver_id,
                approver_name=line.approver_name,
                step_order=line.step_order,
                is_required=line.is_required,
                is_parallel=line.is_parallel,
                status=line.status,
                approved_at=line.approved_at,
                comment=line.comment,
            )
            db_lines.append(db_line)
        
        # MongoDB bulk insert
        await ApprovalLine.insert_many(db_lines)

    async def find_pending_count_by_approver(self, approver_id: str) -> int:
        count = await ApprovalLine.find(
            ApprovalLine.approver_id == approver_id,
            ApprovalLine.status == ApprovalStatus.PENDING
        ).count()
        logger.debug(f"Pending count for approver {approver_id}: {count}")
        return count