import datetime
import re
from pathlib import Path
from typing import Any

from utils.llm_processor import LocalFilePromptDescribe


class PdfSummaryPrompt(LocalFilePromptDescribe):

    def __init__(self, local_path: str | Path, target_individuals: list[str]):
        super().__init__(local_path)

        # 今日の日付をYYYYMMDD形式で取得
        self.today_date = datetime.datetime.now().strftime("%Y%m%d")
        self.target_individuals = target_individuals

    def get_prompt(self) -> str:

        prompt_template = """
You are an expert document analyst with advanced PDF processing and information extraction capabilities. Your task is to analyze a PDF document, perform OCR if necessary, and extract specific information. Today's date for reference is:

<todays_date>
{{today}}
</todays_date>

Target individuals for focused analysis:
<target_individuals>
{{target_individuals}}
</target_individuals>

Please follow these steps to analyze the document:

1. OCR Processing:
   - Determine if OCR is necessary by assessing whether the PDF is image-based or if text can be easily extracted.
   - If OCR is needed, perform Optical Character Recognition (OCR) on the document.
   - Extract the text content from the PDF.

2. Target Individual Identification:
   - Check if the document mentions any of the target individuals listed above.
   - Look for their names, schools, or classes.
   - Determine which target individual(s), if any, this document is relevant to.

3. Document Analysis:
   Analyze the document internally and extract the following information:
   
   a. Document creation date (in YYYYMMDD format):
      - Look for explicit dates in the document
      - Consider the context and format of each date found
      - If no explicit date is found, infer from content
      - If inference is not possible, use today's date
   
   b. Document title (50 characters or less in Japanese):
      - Use the actual title if present in the document
      - If no title exists, generate one based on the main themes and content
      - If a target individual is identified, consider including their name or context in the title when relevant
      - Ensure it is concise and under 50 characters
      - Provide the title in Japanese
   
   c. Document summary (approximately 800 characters in Japanese):
      - Identify the main topics and key points
      - **If one or more target individuals are mentioned in the document:**
        - Focus the summary on information relevant to the identified target individual(s)
        - Highlight specific details, requirements, or actions that pertain to them
        - Include their name and relevant context (school, class, etc.) in the summary
        - Prioritize information that directly affects or concerns the target individual(s)
      - **If no target individuals are mentioned:**
        - Provide a general, comprehensive summary covering the essential content
        - Focus on the main topics and key points for a general audience
      - **Format the summary preferably using bullet points:**
        - Use bullet points (・) to list key information whenever possible
        - You may include brief headings or section titles as needed
        - Short explanatory sentences without bullet points are acceptable when they provide necessary context
        - Prioritize clarity and readability - the goal is to make information easy to scan and understand
        - Example format:
          【イベント名】
          ・日時: XX月XX日
          ・場所: XXX
          ・持ち物: XXX
          保護者の方も参加できます。
      - Ensure the summary is approximately 800 characters
      - Provide the summary in Japanese

   d. TODO list extraction:
      - Carefully examine the document for any requests, actions, or tasks that require response or completion
      - **TODO items are actions the reader must perform** — such as submitting forms, making payments, preparing items, replying to confirmations, signing permission slips, etc.
      - **Do NOT include scheduled events or appointments as TODO items.** Events, ceremonies, meetings, and other calendar-type entries should be extracted as schedule items (see section e below).
      - **If one or more target individuals are identified:**
        - Extract only actions/tasks that are relevant to the identified target individual(s)
        - Look for items that require parent/guardian action or response
      - **If no target individuals are identified:**
        - Extract general action items that would apply to any reader of the document
      - For each TODO item:
        - Write a clear, concise action description in Japanese
        - Identify any associated deadline dates
        - Convert deadline dates to YYYY-MM-DD format
        - If no deadline is specified or implied, set deadline to null
        - If a deadline is given as a relative term (e.g., "by the end of this month", "within 3 days"), calculate the actual date based on today's date
      - If no actionable items are found, return an empty array for the "todo" field

   e. Schedule (event/appointment) extraction:
      - Carefully examine the document for any scheduled events, appointments, ceremonies, meetings, or other calendar-type entries
      - **Schedule items are events that occur at a specific date/time** — such as school events, parent meetings, ceremonies, excursions, class observations, holidays, etc.
      - **Do NOT include action items or tasks here.** Those belong in the TODO section (see section d above).
      - **If one or more target individuals are identified:**
        - Extract only events/schedules that are relevant to the identified target individual(s)
      - **If no target individuals are identified:**
        - Extract general events that would apply to any reader of the document
      - For each schedule item:
        - **title**: A concise event name in Japanese (e.g., "授業参観", "運動会", "保護者会")
        - **description**: A brief description of the event in Japanese, including relevant details such as what to bring, notes, etc. Keep it concise but informative.
        - **location**: The venue or place where the event takes place, in Japanese (e.g., "体育館", "3年1組教室", "校庭"). Set to null if no location is specified or inferable from the document.
        - **start_datetime**: The event's start date and time in ISO 8601 format (YYYY-MM-DDThh:mm:ss)
          - If both date and time are specified: use full format (e.g., "2025-04-15T09:30:00")
          - If only a date is specified with no time: use T00:00:00 (e.g., "2025-04-15T00:00:00")
          - If the date is given as a relative term (e.g., "来週の月曜日", "今月末"), calculate the actual date based on today's date
        - **end_datetime** (optional): The event's end date and time in ISO 8601 format, if specified. Set to null if not specified.
      - If no schedule items are found, return an empty array for the "schedule" field

4. Output Format:
   Output ONLY the following JSON format with no additional text, explanations, or markdown code blocks:

{
  "date": "YYYYMMDD",
  "title": "文書タイトル (50文字以内)",
  "summary": "文書の要約 (約800文字)",
  "todo": [
    {"action": "TODOアクション", "deadline": "YYYY-MM-DD"},
    {"action": "TODOアクション", "deadline": null}
  ],
  "schedule": [
    {"title": "イベント名", "description": "イベントの概要", "location": "開催場所", "start_datetime": "YYYY-MM-DDThh:mm:ss", "end_datetime": "YYYY-MM-DDThh:mm:ss"},
    {"title": "イベント名", "description": "イベントの概要", "location": null, "start_datetime": "YYYY-MM-DDThh:mm:ss", "end_datetime": null}
  ]
}

Notes on the "todo" field:
- If there are no TODO items, use an empty array: "todo": []
- Each TODO item must have an "action" field (string in Japanese)
- Each TODO item must have a "deadline" field (string in YYYY-MM-DD format or null)
- Action descriptions should be clear and specific about what needs to be done
- Include relevant context in the action if it helps clarify the task
- Do NOT include scheduled events here — those belong in the "schedule" field

Notes on the "schedule" field:
- If there are no schedule items, use an empty array: "schedule": []
- Each schedule item must have a "title" field (concise event name in Japanese)
- Each schedule item must have a "description" field (brief event details in Japanese)
- Each schedule item must have a "location" field (venue/place in Japanese, or null if unspecified)
- Each schedule item must have a "start_datetime" field (ISO 8601 format: YYYY-MM-DDThh:mm:ss)
- Each schedule item must have an "end_datetime" field (ISO 8601 format or null)
- Use T00:00:00 for start_datetime when only a date is known without a specific time
- Schedule items represent events to attend or be aware of, NOT tasks to complete

Important: Return only the JSON object. Do not include any explanations, thought processes, or additional text before or after the JSON output.
"""
        # プレースホルダーを実際の値に置き換え
        target_individuals_str = "\n".join([f"- {person}" for person in self.target_individuals])
        prompt = prompt_template.replace("{{today}}", self.today_date)
        prompt = prompt.replace("{{target_individuals}}", target_individuals_str)

        return prompt

    def validate_json(self, json_data: Any) -> Any:
        # 必須フィールドの確認
        required_fields = ["date", "title", "summary", "todo", "schedule"]
        for field in required_fields:
            if field not in json_data:
                if field == "date":
                    json_data[field] = "不明"
                elif field == "todo" or field == "schedule":
                    json_data[field] = []
                else:
                    json_data[field] = "Unknown"

        # todo がリストであることを確認
        if not isinstance(json_data["todo"], list):
            json_data["todo"] = []

        # todo の各項目のバリデーション
        for item in json_data["todo"]:
            if not isinstance(item, dict):
                continue
            if "action" not in item:
                item["action"] = "Unknown"
            if "deadline" not in item:
                item["deadline"] = None

        # schedule がリストであることを確認
        if not isinstance(json_data["schedule"], list):
            json_data["schedule"] = []

        # schedule の各項目のバリデーション
        for item in json_data["schedule"]:
            if not isinstance(item, dict):
                continue
            if "title" not in item:
                item["title"] = "Unknown"
            if "description" not in item:
                item["description"] = "Unknown"
            if "location" not in item:
                item["location"] = None
            if "start_datetime" not in item:
                item["start_datetime"] = self.today_date + "T00:00:00"
            if "end_datetime" not in item:
                item["end_datetime"] = None

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

        # タイトルの長さ確認と調整 (50文字以内)
        if len(json_data["title"]) > 50:
            json_data["title"] = json_data["title"][:47] + "..."

        # ファイル名に使用できない文字を削除
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            json_data["title"] = json_data["title"].replace(char, '')

        return json_data
