import logging
import os
import shutil
import json

import settings
from ai import analyze_with_claude
from utils.summarizer import summarize_to_html
from utils.rabbitmq_publisher import create_publisher

logger = logging.getLogger(__name__)

def process(pdf_path: str):
    """
    ローカル PDF ファイルを Claude AI で解析し、内容に基づいて処理を実行

    :param pdf_path: 処理対象の PDF ファイルパス
    :raises FileNotFoundError: 指定されたファイルが存在しないの場合
    :raises ValueError: ファイルが PDF 形式ではないの場合
    :raises Exception: ファイル処理中にエラーが発生したの場合

    処理内容:
        - Claude AI による文書解析
        - 解析結果に基づくファイル名変更
        - PDF への要約注釈追加
        - 解析結果の標準出力表示
    """
    logger.info(f"Processing local PDF file: {pdf_path}")

    if not os.path.exists(pdf_path):
        logger.error(f"File does not exist: {pdf_path}")
        return

    if not pdf_path.lower().endswith('.pdf'):
        logger.error(f"File is not a PDF: {pdf_path}")
        return

    try:
        # Claudeでファイルを直接分析
        analysis = analyze_with_claude(pdf_path)
        logger.info(f"Analysis result: date={analysis['date']}, title='{analysis['title']}'")

        # 新しいファイル名の生成
        directory = os.path.dirname(pdf_path)
        original_filename = os.path.basename(pdf_path)
        base_name = f"{analysis['date']} {analysis['title']}"
        new_pdf_name = f"{base_name}.pdf"
        new_pdf_path = os.path.join(directory, new_pdf_name)
        new_html_name = f"{base_name}.html"
        new_html_path = os.path.join(directory, new_html_name)

        # ファイル名の変更（ローカルファイルシステム）
        try:
            # すでに同名のファイルが存在する場合は、名前を変更
            if os.path.exists(new_pdf_path) and new_pdf_path != pdf_path:
                counter = 1
                while os.path.exists(new_pdf_path):
                    new_pdf_name = f"{base_name} ({counter}).pdf"
                    new_pdf_path = os.path.join(directory, new_pdf_name)
                    new_html_name = f"{base_name} ({counter}).html"
                    new_html_path = os.path.join(directory, new_html_name)
                    counter += 1

            # 概要を html に保存
            summarize_to_html(analysis, new_html_path)

            # 要約を標準出力に表示
            print("\n=== ドキュメント分析結果 ===")
            print(f"元のファイル名: {original_filename}")
            print(f"推測された日付: {analysis['date']}")
            print(f"推測されたタイトル: {analysis['title']}")
            print(f"新しいファイル名: {new_pdf_name}")
            print("\n=== ドキュメント要約 ===")
            print(f"{analysis['summary']}")
            if analysis.get('todo'):
                print("\n=== TODOリスト ===")
                for item in analysis['todo']:
                    deadline_str = f" [期限: {item['deadline']}]" if item.get('deadline') else ""
                    print(f"・{item['action']}{deadline_str}")
            print("========================\n")

            # ファイルをコピー
            if os.path.exists(new_pdf_path) and new_pdf_path != pdf_path:
                os.remove(new_pdf_path)
            shutil.copy2(pdf_path, new_pdf_path)
            logger.info(f"Copied local file to: {new_pdf_path}")

            # RabbitMQ に解析結果を publish
            try:
                with create_publisher(settings.RABBITMQ_PUBLISH_EXCAHNGE) as pub:
                    pub.publish(
                        body=json.dumps(analysis, ensure_ascii=False).encode('utf-8'),
                        content_type="application/json"
                    )
                logger.info("Published analysis to RabbitMQ")
            except Exception as e:
                logger.error(f"Error publishing to RabbitMQ: {e}")

        except Exception as e:
            logger.error(f"Error renaming local file: {e}")

        logger.info(f"Successfully processed local file")

    except Exception as e:
        logger.error(f"Error processing local file {pdf_path}: {e}")
