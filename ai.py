import logging
from pathlib import Path

from prompts import PdfSummaryPrompt
from utils.llm_processor import LlmProcessor

logger = logging.getLogger(__name__)

_self_dir = Path(__file__).resolve().parent


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
        llm_proc = LlmProcessor(
            model="claude-sonnet-4-5-20250929",
            temperature=0,
            max_tokens=4000,
        )

        prompt = PdfSummaryPrompt(pdf_path)
        response = llm_proc.process_with_llm(prompt)
        analysis = response.response_as_json()
        return analysis

    except Exception as e:
        logger.error(f"Error with Claude analysis: {e}")
        raise e
