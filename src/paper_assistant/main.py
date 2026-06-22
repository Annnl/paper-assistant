from __future__ import annotations

import argparse
import webbrowser
import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="paper-assistant",
        description="启动 paper-assistant 的本地网页界面与 API 服务",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", default=8000, type=int, help="监听端口，默认 8000")
    parser.add_argument(
        "--open", action="store_true", help="启动后自动在默认浏览器中打开首页",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    url = f"http://{args.host}:{args.port}/"
    if args.open:
        webbrowser.open(url)

    uvicorn.run("paper_assistant.app:app", host=args.host, port=args.port)
