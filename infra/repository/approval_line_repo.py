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
        """실제 결재 가능한 대기 건수를 효율적으로 계산"""
        # 1. 결재자의 모든 PENDING 결재선 조회 (1번의 DB 호출)
        pending_lines = await ApprovalLine.find(
            ApprovalLine.approver_id == approver_id,
            ApprovalLine.status == ApprovalStatus.PENDING
        ).to_list()
        
        if not pending_lines:
            return 0
        
        # 2. 관련된 모든 request_id의 결재선을 한번에 조회 (1번의 DB 호출)
        request_ids = list(set(line.request_id for line in pending_lines))
        all_lines = await ApprovalLine.find(
            In(ApprovalLine.request_id, request_ids)
        ).sort(ApprovalLine.step_order).to_list()
        
        # 3. 메모리에서 그룹화 및 계산 (DB 호출 없음)
        from collections import defaultdict
        lines_by_request = defaultdict(list)
        for line in all_lines:
            lines_by_request[line.request_id].append(line)
        
        # 4. 각 요청서별로 실제 결재 가능한지 확인
        actual_count = 0
        for request_id in request_ids:
            request_lines = lines_by_request[request_id]
            
            # 내 결재선 찾기
            my_line = next((line for line in request_lines if line.approver_id == approver_id), None)
            if not my_line:
                continue
            
            # 반려된 결재선이 있는지 확인
            has_rejected = any(line.status == ApprovalStatus.REJECTED for line in request_lines)
            if has_rejected:
                continue
            
            # 이전 단계가 모두 완료되었는지 확인
            can_approve = True
            for line in request_lines:
                if (line.step_order < my_line.step_order and 
                    line.status == ApprovalStatus.PENDING):
                    can_approve = False
                    break
            
            if can_approve:
                actual_count += 1
        
        logger.debug(f"Actual pending count for approver {approver_id}: {actual_count}")
        return actual_count