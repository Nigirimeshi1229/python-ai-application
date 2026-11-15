"""Gemini API との通信を担当するモジュール。"""

import time
from collections.abc import Callable, Iterator

from google import genai
from google.genai import errors, types

# 一覧を取得できなかったときに使うモデル（先頭が初期値）
DEFAULT_MODELS = [
    "gemini-3.8-flash",
]

# 時間をおけば成功する可能性があるエラー（回数制限・サーバーエラー・混雑）
RETRYABLE_CODES = {429, 500, 503}
MAX_RETRIES = 3

# Gemini から応答が途切れたまま、この時間が過ぎたらエラーにする（ミリ秒）
TIMEOUT_MS = 120_000


def list_models(api_key: str) -> list[str]:
    """API キーで使える、文章生成に対応した Gemini モデルの一覧を返す。"""
    client = genai.Client(api_key=api_key)
    names = [
        m.name.removeprefix("models/")
        for m in client.models.list()
        if m.name and "gemini" in m.name and "generateContent" in (m.supported_actions or [])
    ]
    return sorted(names, reverse=True)


def stream_generate(
    api_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    temperature: float = 0.7,
    on_retry: Callable[[int, errors.APIError], None] | None = None,
) -> Iterator[str]:
    """Gemini にプロンプトを送り、生成されたテキストを少しずつ返す。

    一時的なエラーのときは、間隔を空けて最大 MAX_RETRIES 回やり直す。
    ただし文章を返し始めた後は、二重に出力しないようにやり直さない。
    on_retry には、やり直すたびに「何回目か」と「エラー」が渡される。
    """
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )
    for attempt in range(MAX_RETRIES + 1):
        started = False
        try:
            for chunk in client.models.generate_content_stream(
                model=model, contents=prompt, config=config
            ):
                if chunk.text:
                    started = True
                    yield chunk.text
            return
        except errors.APIError as e:
            if started or e.code not in RETRYABLE_CODES or attempt == MAX_RETRIES:
                raise
            if on_retry:
                on_retry(attempt + 1, e)
            time.sleep(2**attempt)  # 1秒 → 2秒 → 4秒
