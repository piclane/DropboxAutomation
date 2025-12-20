import datetime
import re
from pathlib import Path
from typing import Any

from utils.llm_processor import LocalFilePromptDescribe


class PdfSummaryPrompt(LocalFilePromptDescribe):

    def __init__(self, local_path: str | Path):
        super().__init__(local_path)

        # 今日の日付をYYYYMMDD形式で取得
        self.today_date = datetime.datetime.now().strftime("%Y%m%d")

    def get_prompt(self) -> str:

        prompt_template = """
You are an expert document analyst with advanced PDF processing and information extraction capabilities. Your task is to analyze a PDF document, perform OCR if necessary, and extract specific information. Today's date for reference is:

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

Please begin your analysis now, starting with the OCR process if necessary, and then proceed with the document analysis steps. It's OK for each thought process section to be quite long.
"""
        # プレースホルダーを実際の値に置き換え
        prompt = prompt_template.replace("{{today}}", self.today_date)

        return prompt

    def validate_json(self, json_data: Any) -> Any:
        # 必須フィールドの確認
        required_fields = ["date", "title", "summary"]
        for field in required_fields:
            if field not in json_data:
                json_data[field] = "不明" if field == "date" else "Unknown"

        # 日付形式のバリデーション
        if json_data["date"] == "不明":
            json_data["date"] = self.today_date
        else:
            # 数字以外を削除して8桁にする
            date_str = re.sub(r'\D', '', json_data["date"])
            if len(date_str) == 8:
                json_data["date"] = date_str
            else:
                json_data["date"] = self.today_date

        # タイトルの長さ確認と調整
        if len(json_data["title"]) > 100:
            json_data["title"] = json_data["title"][:97] + "..."

        # ファイル名に使用できない文字を削除
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            json_data["title"] = json_data["title"].replace(char, '')

        return json_data
