# src/ai_coc_kp/llm.py

from google import genai
from google.genai import types
import tiktoken
import time
import uuid
import traceback

from .config import Settings
from .logger import LogTracker
enc = tiktoken.get_encoding("cl100k_base")

tracker = LogTracker()


def count_tokens(messages: list[dict]) -> int:
	"""计算消息的总 token 数"""
	return sum(len(enc.encode(m["text"])) for m in messages)


def to_gemini_contents(history: list[dict]) -> list[types.Content]:
	"""将历史消息转换为 Gemini API 格式"""
	return [
		types.Content(
			role=m["role"],
			parts=[
				types.Part(text=m["text"])
			]
		)
		for m in history
	]

def chat(history: list[dict], config: types.GenerateContentConfig, setting: Settings,user_id="unknown") -> str:
    """Minimal Gemini Chat call. Returns dict with text + usage."""
    client = genai.Client(
        api_key=setting.gemini_api_key.get_secret_value()
    )
    model = setting.llm_model
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        resp = client.models.generate_content(
            model=model,
            contents=to_gemini_contents(history),
            config=config
        )
        latency_ms = (time.perf_counter() - start) * 1000
        tracker.record(
            model=model,

            user_id=user_id,

            request_id=request_id,

            history_tokens=count_tokens(history),

            response=resp,

            latency_ms=latency_ms,

            text=resp.text, # type: ignore

            status="ok",
        )
        return resp.text # type: ignore
    except Exception as e:

        latency_ms = (time.perf_counter() - start) * 1000

        error_type = type(e).__name__

        error_message = str(e)

        tracker.record_error(
            model=model,

            user_id=user_id,

            request_id=request_id,

            latency_ms=latency_ms,

            error_type=error_type,

            error_message=error_message,

            traceback_text=traceback.format_exc(),
        )

        return error_message 

