import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from application.file_attachment_service import FileAttachmentService
from infra.repository.attached_file_repo import AttachedFileRepository


class PersonalFileChecksTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = object.__new__(FileAttachmentService)
        self.service.file_repo = SimpleNamespace(
            find_by_id=AsyncMock(return_value=SimpleNamespace(request_id='request')),
            set_completed=AsyncMock(),
        )
        self.service._validate_request_access = AsyncMock()

    async def test_check_and_uncheck_use_current_user(self):
        for completed in (True, False):
            await self.service.set_file_completed('file', 'me', completed)
            self.service.file_repo.set_completed.assert_awaited_with('file', 'me', completed)
        self.service._validate_request_access.assert_awaited_with('request', 'me')

    async def test_denied_access_cannot_change_check(self):
        self.service._validate_request_access.side_effect = HTTPException(403)
        with self.assertRaises(HTTPException):
            await self.service.set_file_completed('file', 'outsider', True)
        self.service.file_repo.set_completed.assert_not_awaited()

    async def test_missing_file_cannot_be_checked(self):
        self.service.file_repo.find_by_id.return_value = None
        with self.assertRaises(HTTPException) as error:
            await self.service.set_file_completed('missing', 'me', True)
        self.assertEqual(error.exception.status_code, 404)
        self.service.file_repo.set_completed.assert_not_awaited()

    async def test_list_includes_only_current_users_checks(self):
        from datetime import datetime
        from domain.attached_file import AttachedFile
        files = [AttachedFile(
            id=key, request_id='request', file_name='same.pdf', gridfs_file_id=key,
            file_size=1, file_type='application/pdf', uploaded_at=datetime.now(), uploaded_by='me',
        ) for key in ('a', 'b')]
        self.service.file_repo.find_by_request_id = AsyncMock(return_value=files)
        self.service.file_repo.get_completed_file_ids = AsyncMock(return_value={'b'})
        result = await self.service.get_files('request', 'me')
        self.assertEqual([file.is_completed for file in result], [False, True])
        self.service.file_repo.get_completed_file_ids.assert_awaited_once_with(['a', 'b'], 'me')

    async def test_repository_scopes_writes_to_file_and_user(self):
        repo = AttachedFileRepository()
        checks = SimpleNamespace(update_one=AsyncMock(), delete_one=AsyncMock())
        with patch('infra.repository.attached_file_repo.client', SimpleNamespace(
            dup=SimpleNamespace(personal_file_checks=checks),
        )):
            await repo.set_completed('file', 'me', True)
            await repo.set_completed('file', 'other', False)
        checks.update_one.assert_awaited_once_with(
            {'_id': {'file_id': 'file', 'user_id': 'me'}},
            {'$set': {'completed': True}}, upsert=True,
        )
        checks.delete_one.assert_awaited_once_with(
            {'_id': {'file_id': 'file', 'user_id': 'other'}},
        )


if __name__ == '__main__':
    unittest.main()
