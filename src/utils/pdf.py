import os
import uuid
from tempfile import gettempdir

import fitz


def annotate_pdf(src_path: str, dst_path: str, text: str, page_num: int = 0):
    """
    PDF ファイルにテキスト注釈を追加

    :param src_path: 入力 PDF ファイルのパス
    :param dst_path: 出力 PDF ファイルのパス
    :param text: 追加する注釈テキスト
    :param page_num: 注釈を追加するページ番号
    """
    doc = fitz.open(src_path)
    page = doc[page_num]
    point = fitz.Point(10, 10)  # top-left coordinates of the icon
    page.add_text_annot(point, text)
    doc.save(dst_path)

def annotate_pdf_to_temp(src_path: str, text: str, page_num: int = 0) -> str:
    """
    PDF ファイルに注釈を追加し一時ファイルとして保存

    :param src_path: 入力 PDF ファイルのパス
    :param text: 追加する注釈テキスト
    :param page_num: 注釈を追加するページ番号
    :return: 生成された一時ファイルのパス
    """
    temp_path = os.path.join(gettempdir(), f"{uuid.uuid4()}.pdf")
    annotate_pdf(src_path, temp_path, text, page_num)
    return temp_path
