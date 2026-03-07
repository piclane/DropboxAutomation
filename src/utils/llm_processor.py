import base64
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import StringPromptValue

import settings
from utils.file_util import to_extension, to_mime_type

T = TypeVar("T", bound="PromptDescribe")


class PromptDescribe(ABC):
    """
    プロンプト記述のための抽象基底クラス
    言語モデル入力に適した形式にプロンプトを変換するためのインターフェースを定義
    """

    @abstractmethod
    def as_input(self) -> LanguageModelInput:
        """
        プロンプトを言語モデル入力形式に変換

        :return: 言語モデルへの入力形式に変換されたプロンプト
        """
        raise NotImplementedError

    def post_process(self, response: str) -> str:
        """
        プロンプトの回答を後処理します

        :param response: LLM の返したレスポンス
        :return: 後処理されたレスポンス
        """
        return response

    def post_process_for_json(self, response: str) -> str:
        """
        JSON に変換する直前にプロンプトの回答を後処理します

        :param response: post_process メソッドで後処理されたレスポンス
        :return: JSON 変換に使用するレスポンス
        """
        return response

    def validate_json(self, json_data: Any) -> Any:
        """
        JSON データを検証および必要に応じて変換

        :param json_data: 検証対象の JSON データ
        :return: 検証および変換後の JSON データ
        """
        return json_data

    @staticmethod
    def json_keys() -> list[str]:
        """
        JSON 形式の回答が返ってくる際のキーのリストを取得します

        :return: JSON 形式の回答が返ってくる際のキーのリスト
        """
        return []

class LocalFilePromptDescribe(PromptDescribe):
    """
    ファイルベースのプロンプト用のプロンプト記述子
    ファイルの検証と言語モデル入力形式への変換を処理

    サポートされるファイル拡張子: PDF、DOCX、CSV、TXT、HTML、ODT、RTF、EPUB、JSON、XLSX、PNG、JPG、JPEG
    """

    def __init__(self, local_path: str | Path):
        """
        ファイルベースのプロンプト記述子を初期化

        :param local_path: ローカルファイルへのパス
        :raises ValueError: file_info がファイルでない場合、またはサポートされていないファイル形式の場合
        """
        if local_path is None or not os.path.isfile(local_path):
            raise ValueError("local_path が不正です（ファイルではありません）")
        # サポートされている拡張子のリスト
        supported_extensions = [".pdf", ".docx", ".csv", ".txt", ".html", ".md", ".odt", ".rtf", ".epub", ".json", ".xlsx", ".png", ".jpg", ".jpeg"]
        # 拡張子を小文字に変換して比較
        if to_extension(local_path) not in supported_extensions:
            raise ValueError(
                f"指定された S3Object はサポートされていません。サポートされている形式: {', '.join(supported_extensions)}"
            )
        self.local_path = local_path

    @abstractmethod
    def get_prompt(self) -> str:
        """
        プロンプトテキストを取得

        :return: プロンプト文字列
        """
        raise NotImplementedError

    def as_input(self) -> LanguageModelInput:
        """
        ファイルをBase64エンコードし言語モデル入力形式に変換
        画像ファイル（PNG、JPG、JPEG）の場合は画像として、その他は文書として処理

        :return: ファイルデータを含む言語モデル入力形式
        """
        with open(self.local_path, "rb") as file:
            binary_data = file.read()

        ext = to_extension(self.local_path)
        mime_type = to_mime_type(self.local_path)

        # 画像ファイルの場合は画像として処理
        if ext in [".png", ".jpg", ".jpeg"]:
            content = [
                {"type": "text", "text": self.get_prompt()},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(binary_data).decode("utf-8"),
                    },
                },
            ]
        # html
        elif ext in [".csv", ".html", ".md", ".txt"]:
            content = [
                {"type": "text", "text": self.get_prompt()},
                {
                    "type": "document",
                    "source": {
                        "type": "text",
                        "media_type": "text/plain",
                        "data": binary_data.decode("utf-8"),
                    },
                    "title": os.path.basename(self.local_path),
                    "citations": {"enabled": True},
                },
            ]
        else:
            # その他のファイル（PDF、DOCX等）は文書として処理
            content = [
                {"type": "text", "text": self.get_prompt()},
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(binary_data).decode("utf-8"),
                    },
                    "title": os.path.basename(self.local_path),
                },
            ]

        return [HumanMessage(content=content)]


class PlainPromptDescribe(PromptDescribe):
    """
    テキストベースのプロンプト用のプロンプト記述子
    プレーンテキストプロンプトを言語モデル入力に変換する機能を提供
    """

    @abstractmethod
    def get_prompt(self) -> str:
        """
        プロンプトテキストを取得

        :return: プロンプト文字列
        """
        raise NotImplementedError

    def as_input(self) -> LanguageModelInput:
        """
        テキストプロンプトを言語モデル入力形式に変換

        :return: テキストベースの言語モデル入力形式
        """
        return StringPromptValue(text=self.get_prompt())


@dataclass
class LlmResult(Generic[T]):
    """
    LLM処理操作の結果を表すジェネリックデータクラス
    元のプロンプトと言語モデルからのレスポンスの両方を含む
    """

    prompt: T  #: 元のプロンプト
    response: str  #: LLMからのレスポンス文字列

    def response_as_json(self) -> Any:
        """
        レスポンスをJSON解析し辞書として返却

        :return: パース済みの辞書オブジェクト
        :raises JSONDecodeError: レスポンスが有効なJSONでない場合
        """
        json_str = self.prompt.post_process_for_json(self.response)
        json_str = re.sub(r"^\s*```[a-zA-Z]*", "", json_str, flags=re.MULTILINE)
        json_str = json_str.strip()

        try:
            json_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON のパースに失敗しました JSON={json_str}") from e

        json_data = self.prompt.validate_json(json_data)
        return json_data


class LlmProcessor:
    """
    言語モデル操作のためのプロセッサクラス
    LLMクライアントの初期化とプロンプトの処理を担当
    """

    def __init__(self, model: str, **kwargs: Any):
        """
        LLMプロセッサを初期化

        :param model: 使用する言語モデルの名前
        :param kwargs: ChatAnthropic のコンストラクタに渡す全ての引数
        :raises RuntimeError: 必要なライブラリが見つからない場合、またはLLMクライアントの初期化に失敗した場合
        """
        super().__init__()


        try:
            from langchain_anthropic import ChatAnthropic
            self.llm_client = ChatAnthropic(
                model=model,
                api_key=settings.CLAUDE_API_KEY,
                **kwargs
            )
        except ImportError as e:
            raise RuntimeError(
                "警告: langchain_anthropic がインストールされていません。LLM処理は無効化されます"
            ) from e
        except Exception as e:
            raise RuntimeError(f"LLMクライアントの初期化に失敗しました: {e}") from e

    def process_with_llm(self, prompt: T) -> LlmResult[T]:
        """
        プロンプトをLLMで処理

        :param prompt: 処理するプロンプト
        :return: LLM処理結果を含む結果オブジェクト
        """
        response = self.llm_client.invoke(input=prompt.as_input())
        response_content = prompt.post_process(response.content if response else "")
        return LlmResult(prompt=prompt, response=response_content)
