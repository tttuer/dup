import asyncio
from io import BytesIO
import unittest

from fastapi import UploadFile
from starlette.datastructures import Headers

from application.wiki_security import read_valid_attachment, sanitize_wiki_content
from common.exceptions import ValidationError


class WikiSecurityTest(unittest.TestCase):
    def test_sanitizes_executable_html_but_preserves_safe_formatting(self):
        clean = sanitize_wiki_content(
            '<p style="color: red">정상</p>'
            '<img src="x" onerror="alert(1)">'
            '<a href="javascript:alert(1)">링크</a>'
        )

        self.assertIn('정상', clean)
        self.assertIn('style="color: red;"', clean)
        self.assertNotIn('onerror', clean)
        self.assertNotIn('javascript:', clean)

    def test_preserves_markdown_source_for_editor(self):
        markdown = '# 제목\n\n- 목록\n- **강조**'
        self.assertEqual(sanitize_wiki_content(markdown), markdown)

    def test_allows_common_business_attachment(self):
        file = UploadFile(
            filename='report.hwp',
            file=BytesIO(b'HWP business document'),
            headers=Headers({'content-type': 'application/x-hwp'}),
        )

        result = asyncio.run(read_valid_attachment(file))

        self.assertEqual(result, b'HWP business document')

    def test_blocks_html_attachment_even_when_extension_is_changed(self):
        file = UploadFile(
            filename='invoice.pdf',
            file=BytesIO(b'<html><script>alert(1)</script></html>'),
            headers=Headers({'content-type': 'application/pdf'}),
        )

        with self.assertRaises(ValidationError):
            asyncio.run(read_valid_attachment(file))


if __name__ == '__main__':
    unittest.main()
