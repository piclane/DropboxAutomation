import base64
import datetime
import json
import logging
import re

import anthropic

from settings import CLAUDE_API_KEY

logger = logging.getLogger(__name__)

def init_claude():
    """
    Claude API クライアントを初期化

    :returns: Anthropic クライアントインスタンス
    """
    return anthropic.Anthropic(api_key=CLAUDE_API_KEY)

def analyze_with_claude(pdf_path):
    """
    PDF ファイルを Claude AI で解析して情報を抽出

    :param pdf_path: 解析対象の PDF ファイルパス
    :returns: 以下のキーを含む解析結果辞書
        - date: 文書作成日 (YYYYMMDD形式)
        - title: 文書タイトル (50文字以内)
        - summary: 文書要約 (約500文字)
    :raises FileNotFoundError: 指定された PDF ファイルが存在しないの場合
    :raises json.JSONDecodeError: Claude からのレスポンスが JSON 形式でないの場合
    :raises anthropic.APIError: Claude API でエラーが発生したの場合
    :raises Exception: その他のエラーが発生したの場合
    """
    try:
        logger.info(f"Analyzing PDF with Claude: {pdf_path}")

        # Claudeクライアントの初期化
        claude_client = init_claude()

        # PDFファイルをバイナリとして読み込み
        with open(pdf_path, 'rb') as file:
            pdf_data = file.read()

        # 今日の日付をYYYYMMDD形式で取得
        today_date = datetime.datetime.now().strftime("%Y%m%d")

        # 改善されたプロンプトテンプレート
        prompt_template = """You are an expert document analyst with advanced PDF processing and information extraction capabilities. Your task is to analyze a PDF document, perform OCR if necessary, and extract specific information. Today's date for reference is:

<todays_date>
{{today}}
</todays_date>

Please follow these steps to analyze the document:

1. OCR Processing:
   - Determine if OCR is necessary by assessing whether the PDF is image-based or if text can be easily extracted.
   - If OCR is needed, perform Optical Character Recognition (OCR) on the document.
   - Extract the text content from the PDF.

2. Document Analysis:
   Your goal is to extract and generate the following information:
   a. Document creation date (in YYYYMMDD format)
   b. Document title (50 characters or less)
   c. Document summary (approximately 500 characters)

   For each step of your analysis, wrap your thought process in <thought_process> tags.

   Step 0: Identify the document type or category
   <thought_process>
   - List key features or content that indicate the document type.
   - Propose 2-3 possible document categories based on these features.
   - Choose the most likely category and explain why.
   </thought_process>

   Step 1: Determine the document creation date
   <thought_process>
   - List all potential dates found in the document, including their context and format.
   - For each date, explain why it might or might not be the creation date, considering its format and surrounding context.
   - If no explicit date is found, explain how you inferred the date from the content.
   - If inference is not possible, use today's date and explain why.
   </thought_process>

   Step 2: Identify or generate the document title
   <thought_process>
   - Quote potential titles directly from the document.
   - Identify 3-5 key themes or keywords from the document content.
   - If generating a title, list 2-3 options based on these themes and keywords.
   - For each potential title, explain why it might be suitable or not.
   - Ensure the final chosen title is 50 characters or less.
   - Translate the final title into Japanese.
   </thought_process>

   Step 3: Summarize the document
   <thought_process>
   - Identify 3-5 main topics from the document.
   - For each main topic, list 1-2 subtopics or key points.
   - Quote 3-5 key passages from the document that represent these main points.
   - Create a concise summary of approximately 500 characters based on these topics and key points.
   - Translate the summary into Japanese.
   </thought_process>

3. Output Format:
   After your analysis, provide the final output in JSON format with the following structure:

   {
     "date": "YYYYMMDD",
     "title": "文書タイトル (50文字以内)",
     "summary": "文書の要約 (約500文字)"
   }

   Ensure that both the title and summary in the JSON output are in Japanese.

Please begin your analysis now, starting with the OCR process if necessary, and then proceed with the document analysis steps. It's OK for each thought process section to be quite long."""

        # プレースホルダーを実際の値に置き換え
        prompt = prompt_template.replace("{{today}}", today_date)

        # Claude APIに直接PDFファイルを送信
        message = claude_client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            temperature=0,
            system="You are an expert document analyst with advanced OCR capabilities. You can extract information from any type of PDF, including image-based documents.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.b64encode(pdf_data).decode('utf-8')
                            }
                        }
                    ]
                }
            ]
        )

        response_text = message.content[0].text
        logger.info("Received response from Claude API")

        # 完全な応答を記録
        logger.debug(f"Full Claude response: {response_text}")

        # JSON部分を正規表現で抽出
        json_match = re.search(r'```json\s*({.*?})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'{.*"date".*"title".*"summary".*}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("Could not extract JSON from Claude response, using full response")
                json_str = response_text

        try:
            # JSON文字列をパース
            analysis_result = json.loads(json_str)

            # 必須フィールドの確認
            required_fields = ["date", "title", "summary"]
            for field in required_fields:
                if field not in analysis_result:
                    analysis_result[field] = "不明" if field == "date" else "Unknown"

            # 日付形式のバリデーション
            if analysis_result["date"] == "不明":
                analysis_result["date"] = today_date
            else:
                # 数字以外を削除して8桁にする
                date_str = re.sub(r'\D', '', analysis_result["date"])
                if len(date_str) == 8:
                    analysis_result["date"] = date_str
                else:
                    analysis_result["date"] = today_date

            # タイトルの長さ確認と調整
            if len(analysis_result["title"]) > 100:
                analysis_result["title"] = analysis_result["title"][:97] + "..."

            # ファイル名に使用できない文字を削除
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            for char in invalid_chars:
                analysis_result["title"] = analysis_result["title"].replace(char, '')

            return analysis_result

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from Claude response: {e}")
            # JSON解析に失敗した場合はデフォルト値を返す
            return {
                "date": today_date,
                "title": "Unreadable Document",
                "summary": "This document appears to be unreadable or contains complex formatting that could not be analyzed."
            }

    except Exception as e:
        logger.error(f"Error with Claude analysis: {e}")
        raise e
