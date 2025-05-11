import logging
import os
import shutil

from ai import analyze_with_claude
from utils.pdf import annotate_pdf_to_temp

logger = logging.getLogger(__name__)

def process(file_path: str):
    """
    ローカル PDF ファイルを Claude AI で解析し、内容に基づいて処理を実行

    :param file_path: 処理対象の PDF ファイルパス
    :raises FileNotFoundError: 指定されたファイルが存在しないの場合
    :raises ValueError: ファイルが PDF 形式ではないの場合
    :raises Exception: ファイル処理中にエラーが発生したの場合

    処理内容:
        - Claude AI による文書解析
        - 解析結果に基づくファイル名変更
        - PDF への要約注釈追加
        - 解析結果の標準出力表示
    """
    logger.info(f"Processing local PDF file: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return

    if not file_path.lower().endswith('.pdf'):
        logger.error(f"File is not a PDF: {file_path}")
        return

    try:
        # Claudeでファイルを直接分析
        analysis = analyze_with_claude(file_path)
        logger.info(f"Analysis result: date={analysis['date']}, title='{analysis['title']}'")

        # 新しいファイル名の生成
        directory = os.path.dirname(file_path)
        original_filename = os.path.basename(file_path)
        new_file_name = f"{analysis['date']} {analysis['title']}.pdf"
        new_path = os.path.join(directory, new_file_name)

        # 要約を PDF に追加
        new_pdf_path = annotate_pdf_to_temp(file_path, analysis['summary'])

        # ファイル名の変更（ローカルファイルシステム）
        try:
            # すでに同名のファイルが存在する場合は、名前を変更
            if os.path.exists(new_path) and new_path != file_path:
                base_name = f"{analysis['date']} {analysis['title']}"
                extension = ".pdf"
                counter = 1
                while os.path.exists(new_path):
                    new_file_name = f"{base_name} ({counter}){extension}"
                    new_path = os.path.join(directory, new_file_name)
                    counter += 1

            # ファイル名を変更
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(new_path):
                os.remove(new_path)
            shutil.move(new_pdf_path, new_path)
            logger.info(f"Renamed local file to: {new_path}")

            # 要約を標準出力に表示
            print("\n=== ドキュメント分析結果 ===")
            print(f"元のファイル名: {original_filename}")
            print(f"推測された日付: {analysis['date']}")
            print(f"推測されたタイトル: {analysis['title']}")
            print(f"新しいファイル名: {new_file_name}")
            print("\n=== ドキュメント要約 ===")
            print(f"{analysis['summary']}")
            print("========================\n")

        except Exception as e:
            logger.error(f"Error renaming local file: {e}")

        logger.info(f"Successfully processed local file")

    except Exception as e:
        logger.error(f"Error processing local file {file_path}: {e}")
