"""
ファイル関連のユーティリティ
"""

import os
from typing import Final

# 拡張子に対応するMIMEタイプのマッピング
MIME_TYPES: Final[dict[str, str]] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".rtf": "application/rtf",
    ".epub": "application/epub+zip",
    ".json": "application/json",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".xml": "application/xml",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def to_extension(file_name: str) -> str:
    """
    ファイル名から拡張子（ドット付き・小文字）を取得する

    :param file_name: ファイル名（パス含んでいても可）
    :return: 拡張子（例: ".pdf"）。拡張子が無い場合は空文字
    """
    if not file_name:
        return ""
    _, ext = os.path.splitext(file_name)
    return ext.lower()


def to_basename(file_name: str) -> str:
    """
    ファイル名からベース名（拡張子を除いた名前）を取得する

    :returns: ベース名。ファイル名がない場合は空文字列
    :raises ValueError: オブジェクトがファイルではない場合
    """
    return os.path.splitext(file_name)[0]


def to_mime_type(file_name: str) -> str:
    """
    ファイル名の拡張子から MIME タイプを取得する

    :param file_name: ファイル名
    :return: MIME タイプ。対応が無い場合は 'application/octet-stream'
    """
    ext = to_extension(file_name)
    return MIME_TYPES.get(ext, "application/octet-stream")
