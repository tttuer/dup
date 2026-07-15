import re
from pathlib import PurePath

import bleach
from bleach.css_sanitizer import CSSSanitizer
from fastapi import UploadFile

from common.exceptions import ValidationError


MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024

ALLOWED_HTML_TAGS = [
    "a", "abbr", "b", "blockquote", "br", "code", "del", "div", "em", "figcaption",
    "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "mark", "ol",
    "p", "pre", "s", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "u", "ul",
]
ALLOWED_HTML_ATTRIBUTES = {
    "*": ["align", "aria-label", "class", "colspan", "id", "rowspan", "style", "title"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]
CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "background-color", "border", "border-color", "color", "display", "float", "font-size",
        "font-style", "font-weight", "height", "margin", "margin-left", "margin-right", "max-width",
        "padding", "text-align", "text-decoration", "vertical-align", "width",
    ]
)

SAFE_IMAGE_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}
IMAGE_SIGNATURES = {
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}

# Attachments are downloaded with Content-Disposition: attachment and nosniff.
# Common business documents such as HWP/HWPX, PDF, Office, CSV, and ZIP remain allowed.
BLOCKED_EXTENSIONS = {
    ".apk", ".app", ".bat", ".cmd", ".com", ".cpl", ".dll", ".dmg", ".exe", ".gadget",
    ".hta", ".htm", ".html", ".img", ".inf", ".iso", ".jar", ".js", ".jse", ".lnk",
    ".mjs", ".msi", ".msp", ".mst", ".php", ".ps1", ".py", ".scr", ".sh", ".svg",
    ".swf", ".url", ".vbe", ".vbs", ".wsf", ".wsh", ".xhtml", ".xml", ".xsl",
}
BLOCKED_CONTENT_TYPES = {
    "application/ecmascript", "application/javascript", "application/x-httpd-php",
    "application/xhtml+xml", "image/svg+xml", "text/css", "text/html", "text/javascript",
}
HTML_LIKE_CONTENT = re.compile(br"^\s*(?:<!doctype\s+html|<html|<head|<body|<script|<iframe|<svg)\b", re.I)


def sanitize_wiki_content(content: str) -> str:
    """Sanitize rich HTML while preserving Markdown source for normal editing."""
    if not content.lstrip().startswith("<"):
        return content
    return bleach.clean(
        content,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=CSS_SANITIZER,
        strip=True,
    )


async def read_valid_image(file: UploadFile) -> bytes:
    file_data = await _read_limited(file, MAX_IMAGE_SIZE, "이미지")
    content_type = (file.content_type or "").lower()
    if content_type not in SAFE_IMAGE_TYPES:
        raise ValidationError("지원하지 않는 이미지 형식입니다. JPG, PNG, GIF, WEBP만 업로드할 수 있습니다.")

    is_webp = content_type == "image/webp" and file_data.startswith(b"RIFF") and file_data[8:12] == b"WEBP"
    if not is_webp and not any(file_data.startswith(signature) for signature in IMAGE_SIGNATURES[content_type]):
        raise ValidationError("파일 내용이 이미지 형식과 일치하지 않습니다.")
    return file_data


async def read_valid_attachment(file: UploadFile) -> bytes:
    file_data = await _read_limited(file, MAX_ATTACHMENT_SIZE, "첨부파일")
    extension = PurePath(file.filename or "").suffix.lower()
    content_type = (file.content_type or "application/octet-stream").lower()

    if extension in BLOCKED_EXTENSIONS or content_type in BLOCKED_CONTENT_TYPES:
        raise ValidationError("보안상 실행 가능한 파일 또는 웹 문서는 첨부할 수 없습니다.")
    if file_data.startswith((b"MZ", b"\x7fELF", b"#!")) or HTML_LIKE_CONTENT.match(file_data[:4096]):
        raise ValidationError("실행 파일 또는 웹 문서는 첨부할 수 없습니다.")
    return file_data


async def _read_limited(file: UploadFile, maximum_size: int, label: str) -> bytes:
    file_data = await file.read(maximum_size + 1)
    if not file_data:
        raise ValidationError(f"비어 있는 {label}은 업로드할 수 없습니다.")
    if len(file_data) > maximum_size:
        raise ValidationError(f"{label}은 최대 {maximum_size // 1024 // 1024}MB까지 업로드할 수 있습니다.")
    return file_data
