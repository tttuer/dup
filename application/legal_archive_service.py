import io
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dependency_injector.wiring import inject
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from ulid import ULID
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF

from application.base_service import BaseService
from domain.repository.approval_request_repo import IApprovalRequestRepository
from domain.repository.approval_line_repo import IApprovalLineRepository
from domain.repository.approval_history_repo import IApprovalHistoryRepository
from domain.repository.user_repo import IUserRepository
from domain.repository.attached_file_repo import IAttachedFileRepository
from common.db import client
from utils.time import get_utc_now_naive, utc_to_kst_naive


class LegalArchiveService(BaseService):
    @inject
    def __init__(
        self,
        approval_repo: IApprovalRequestRepository,
        line_repo: IApprovalLineRepository,
        history_repo: IApprovalHistoryRepository,
        user_repo: IUserRepository,
        file_repo: IAttachedFileRepository,
    ):
        super().__init__(user_repo)
        self.approval_repo = approval_repo
        self.line_repo = line_repo
        self.history_repo = history_repo
        self.file_repo = file_repo
        self.ulid = ULID()
        
        # GridFS 설정 (법적 문서 보관용)
        self.db = client.dup
        self.legal_fs = AsyncIOMotorGridFSBucket(self.db, bucket_name="legal_documents")

    async def create_legal_document(self, request_id: str, created_by: str) -> str:
        """결재 완료된 문서를 법적 효력이 있는 PDF로 변환 및 보관"""
        
        # 결재 요청서 조회
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # 완료된 결재만 처리
        from common.auth import DocumentStatus
        if request.status != DocumentStatus.APPROVED:
            raise HTTPException(status_code=400, detail="Only approved documents can be archived")
        
        # 사용자 검증
        await self.validate_user_exists(created_by)
        
        try:
            # PDF 문서 생성
            pdf_content = await self._generate_pdf_document(request_id)
            
            # 메타데이터 준비
            metadata = await self._prepare_document_metadata(request_id)
            
            # GridFS에 저장 (읽기 전용)
            file_id = await self.legal_fs.upload_from_stream(
                filename=f"legal_{request.document_number}_{request_id}.pdf",
                source=io.BytesIO(pdf_content),
                metadata={
                    **metadata,
                    "created_by": created_by,
                    "created_at": get_utc_now_naive(),
                    "is_legal_document": True,
                    "readonly": True,
                }
            )
            
            return str(file_id)
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create legal document: {str(e)}"
            )

    async def get_legal_document(self, request_id: str, user_id: str) -> tuple[bytes, str]:
        """법적 문서 다운로드"""
        
        # 권한 확인
        await self._validate_access_permission(request_id, user_id)
        
        # 문서 조회
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        # GridFS에서 파일 조회
        filename_pattern = f"legal_{request.document_number}_{request_id}.pdf"
        
        try:
            # 파일 스트림 조회
            file_cursor = self.legal_fs.find({"filename": filename_pattern})
            file_doc = await file_cursor.to_list(length=1)
            
            if not file_doc:
                raise HTTPException(status_code=404, detail="Legal document not found")
            
            file_id = file_doc[0]["_id"]
            
            # 파일 내용 다운로드
            file_stream = await self.legal_fs.open_download_stream(file_id)
            content = await file_stream.read()
            
            return content, filename_pattern
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve legal document: {str(e)}"
            )

    async def verify_legal_document_exists(self, request_id: str) -> bool:
        """법적 문서 존재 여부 확인"""
        
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            return False
        
        filename_pattern = f"legal_{request.document_number}_{request_id}.pdf"
        
        try:
            file_cursor = self.legal_fs.find({"filename": filename_pattern})
            files = await file_cursor.to_list(length=1)
            return len(files) > 0
        except:
            return False

    async def _generate_pdf_document(self, request_id: str) -> bytes:
        """결재 문서를 PDF로 변환 (reportlab 사용)"""
        
        # 결재 정보 수집
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        histories = await self.history_repo.find_by_request_id(request_id)
        attached_files = await self.file_repo.find_by_request_id(request_id)
        
        # PDF 문서 생성 (전문적인 여백과 설정)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=25*mm,
            bottomMargin=25*mm
        )
        
        # 한글 폰트 등록
        import os
        font_path = os.path.join(os.path.dirname(__file__), "..", "fonts", "malgun.ttf")
        pdfmetrics.registerFont(TTFont("맑은고딕", font_path))
        korean_font_name = "맑은고딕"
        
        # 스타일 설정
        styles = getSampleStyleSheet()
        
        # 전문적인 한글 스타일 정의
        document_title_style = ParagraphStyle(
            'DocumentTitle',
            parent=styles['Title'],
            fontName=korean_font_name,
            fontSize=20,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.black,
            borderWidth=2,
            borderColor=colors.black,
            borderPadding=10,
            backColor=colors.lightgrey
        )
        
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading1'],
            fontName=korean_font_name,
            fontSize=14,
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=8,
            leftIndent=0
        )
        
        subsection_style = ParagraphStyle(
            'SubSection',
            parent=styles['Heading2'],
            fontName=korean_font_name,
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=6,
            spaceBefore=12,
            textColor=colors.darkred,
            leftIndent=10
        )
        
        content_style = ParagraphStyle(
            'Content',
            parent=styles['Normal'],
            fontName=korean_font_name,
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            spaceBefore=3,
            leftIndent=15,
            rightIndent=15
        )
        
        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName=korean_font_name,
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.black
        )
        
        table_content_style = ParagraphStyle(
            'TableContent',
            parent=styles['Normal'],
            fontName=korean_font_name,
            fontSize=9,
            alignment=TA_LEFT
        )
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName=korean_font_name,
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        
        # PDF 내용 구성
        story = []
        
        # 문서 헤더 (공식 문서 스타일)
        story.append(Paragraph("전자결재 법적문서", document_title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # 문서 기본 정보 테이블
        story.append(Paragraph("I. 문서 기본 정보", section_title_style))
        
        basic_info_data = [
            [Paragraph("문서번호", table_header_style), Paragraph(str(request.document_number), table_content_style)],
            [Paragraph("제목", table_header_style), Paragraph(str(request.title), table_content_style)],
            [Paragraph("기안자", table_header_style), Paragraph(str(request.requester_name), table_content_style)],
            [Paragraph("기안일시", table_header_style), Paragraph(utc_to_kst_naive(request.created_at).strftime('%Y년 %m월 %d일 %H시 %M분'), table_content_style)],
            [Paragraph("완료일시", table_header_style), Paragraph(utc_to_kst_naive(request.completed_at).strftime('%Y년 %m월 %d일 %H시 %M분') if request.completed_at else '처리중', table_content_style)],
            [Paragraph("문서상태", table_header_style), Paragraph(request.status.value if hasattr(request.status, 'value') else str(request.status), table_content_style)]
        ]
        
        basic_info_table = Table(basic_info_data, colWidths=[40*mm, 120*mm])
        basic_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), korean_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(basic_info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 문서 내용
        story.append(Paragraph("II. 결재 요청 내용", section_title_style))
        content_text = self._html_to_plain_text(request.content)
        story.append(Paragraph(content_text, content_style))
        story.append(Spacer(1, 0.3*inch))
        
        # 결재선 정보 테이블
        story.append(Paragraph("III. 결재선 및 승인 현황", section_title_style))
        
        approval_data = [
            [Paragraph("단계", table_header_style), 
             Paragraph("결재자", table_header_style), 
             Paragraph("상태", table_header_style), 
             Paragraph("승인일시", table_header_style), 
             Paragraph("의견", table_header_style)]
        ]
        
        sorted_lines = sorted(approval_lines, key=lambda x: x.step_order)
        for line in sorted_lines:
            status_text = line.status.value if hasattr(line.status, 'value') else str(line.status)
            approved_text = utc_to_kst_naive(line.approved_at).strftime('%Y-%m-%d %H:%M') if line.approved_at else '-'
            comment = line.comment or '-'
            
            # 상태에 따른 색상 적용
            status_color = colors.green if status_text == 'APPROVED' else colors.red if status_text == 'REJECTED' else colors.orange
            
            approval_data.append([
                Paragraph(str(line.step_order), table_content_style),
                Paragraph(str(line.approver_name), table_content_style),
                Paragraph(status_text, ParagraphStyle('StatusStyle', parent=table_content_style, textColor=status_color)),
                Paragraph(approved_text, table_content_style),
                Paragraph(comment[:50] + ('...' if len(comment) > 50 else ''), table_content_style)
            ])
        
        approval_table = Table(approval_data, colWidths=[20*mm, 35*mm, 25*mm, 35*mm, 55*mm])
        approval_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), korean_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(approval_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 결재 이력
        story.append(Paragraph("IV. 상세 결재 이력", section_title_style))
        
        history_data = [
            [Paragraph("일시", table_header_style),
             Paragraph("결재자", table_header_style),
             Paragraph("처리내용", table_header_style),
             Paragraph("접속IP", table_header_style),
             Paragraph("의견", table_header_style)]
        ]
        
        sorted_histories = sorted(histories, key=lambda x: x.created_at)
        for history in sorted_histories:
            action_text = history.action.value if hasattr(history.action, 'value') else str(history.action)
            action_color = colors.green if action_text == 'APPROVE' else colors.red if action_text == 'REJECT' else colors.orange
            
            history_data.append([
                Paragraph(utc_to_kst_naive(history.created_at).strftime('%Y-%m-%d<br/>%H:%M:%S'), table_content_style),
                Paragraph(str(history.approver_name), table_content_style),
                Paragraph(action_text, ParagraphStyle('ActionStyle', parent=table_content_style, textColor=action_color)),
                Paragraph(history.ip_address or '-', table_content_style),
                Paragraph((history.comment or '-')[:40] + ('...' if history.comment and len(history.comment) > 40 else ''), table_content_style)
            ])
        
        history_table = Table(history_data, colWidths=[35*mm, 35*mm, 25*mm, 30*mm, 45*mm])
        history_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), korean_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(history_table)
        
        # 첨부파일 정보
        if attached_files:
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("V. 첨부파일 목록", section_title_style))
            
            file_data = [
                [Paragraph("파일명", table_header_style),
                 Paragraph("크기", table_header_style),
                 Paragraph("업로드일시", table_header_style),
                 Paragraph("업로드자", table_header_style)]
            ]
            
            for file in attached_files:
                file_size = f"{file.file_size:,} bytes" if file.file_size < 1024*1024 else f"{file.file_size/(1024*1024):.1f} MB"
                file_data.append([
                    Paragraph(str(file.file_name), table_content_style),
                    Paragraph(file_size, table_content_style),
                    Paragraph(utc_to_kst_naive(file.uploaded_at).strftime('%Y-%m-%d %H:%M'), table_content_style),
                    Paragraph(str(file.uploaded_by), table_content_style)
                ])
            
            file_table = Table(file_data, colWidths=[60*mm, 30*mm, 40*mm, 40*mm])
            file_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), korean_font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            story.append(file_table)
        
        # 법적 효력 안내 (새 페이지)
        story.append(PageBreak())
        story.append(Paragraph("법적 효력 및 보안 안내", document_title_style))
        story.append(Spacer(1, 0.2*inch))
        
        legal_notice = [
            "■ 법적 효력 제한 사항",
            "1. 본 문서는 전자결재 시스템을 통해 생성된 전자문서입니다.",
            "2. 완전한 법적 효력을 위해서는 다음 요건이 추가로 필요합니다:",
            "   - 전자서명법에 따른 공인인증서 기반 전자서명",
            "   - 공인된 타임스탬프 기관(TSA)의 시각 인증",
            "   - 문서 무결성 보장을 위한 해시체인 구현",
            "3. 현재 문서는 내부 업무용 전자결재 기록으로 활용 가능합니다.",
            "4. 대외적 법적 효력이 필요한 경우 별도 법적 검토가 필요합니다.",
            "5. 본 시스템은 전자문서 보관 및 이력 관리 기능을 제공합니다."
        ]
        
        for notice in legal_notice:
            story.append(Paragraph(notice, content_style))
            story.append(Spacer(1, 0.1*inch))
        
        # 문서 생성 정보
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("■ 문서 생성 정보", subsection_style))
        story.append(Paragraph(f"생성일시: {utc_to_kst_naive(get_utc_now_naive()).strftime('%Y년 %m월 %d일 %H시 %M분 %S초')}", footer_style))
        story.append(Paragraph(f"생성시스템: 전자결재시스템 v2.0", footer_style))
        story.append(Paragraph(f"문서ID: {request_id}", footer_style))
        
        # PDF 빌드
        doc.build(story)
        
        # PDF 바이트 반환
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _html_to_plain_text(self, html_content: str) -> str:
        """HTML을 일반 텍스트로 변환 (간단한 처리)"""
        import re
        
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # HTML 엔티티 변환
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        
        # 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    async def _prepare_document_metadata(self, request_id: str) -> Dict[str, Any]:
        """문서 메타데이터 준비"""
        
        request = await self.approval_repo.find_by_id(request_id)
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        histories = await self.history_repo.find_by_request_id(request_id)
        
        return {
            "request_id": request_id,
            "document_number": request.document_number,
            "title": request.title,
            "requester_id": request.requester_id,
            "requester_name": request.requester_name,
            "status": request.status.value if hasattr(request.status, 'value') else str(request.status),
            "created_at": request.created_at,
            "completed_at": request.completed_at,
            "approval_lines_count": len(approval_lines),
            "histories_count": len(histories),
            "archived_at": get_utc_now_naive(),
        }

    async def _validate_access_permission(self, request_id: str, user_id: str) -> None:
        """접근 권한 검증 (기안자, 결재자, 관리자만)"""
        
        request = await self.approval_repo.find_by_id(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        user = await self.validate_user_exists(user_id)
        
        # 기안자인지 확인
        if request.requester_id == user_id:
            return
        
        # 결재자인지 확인
        approval_lines = await self.line_repo.find_by_request_id(request_id)
        is_approver = any(line.approver_id == user_id for line in approval_lines)
        if is_approver:
            return
        
        # 관리자인지 확인
        is_admin = any(role.value == "ADMIN" for role in user.roles)
        if is_admin:
            return
        
        raise HTTPException(status_code=403, detail="No permission to access this legal document")