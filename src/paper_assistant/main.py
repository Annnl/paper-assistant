from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path


def resolve_site_directory() -> Path:
    current = Path(__file__).resolve()
    root = current.parents[2]
    root_index = root / "index.html"
    if root_index.exists():
        return root
    docs_dir = root / "docs"
    if docs_dir.exists():
        return docs_dir
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="paper-assistant",
        description="启动 paper-assistant 的本地网页界面",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", default=8000, type=int, help="监听端口，默认 8000")
    parser.add_argument(
        "--open", action="store_true", help="启动后自动在默认浏览器中打开首页",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    site_dir = resolve_site_directory()

    if not site_dir.exists() or not site_dir.is_dir():
        raise FileNotFoundError(
            f"未找到可用的静态网页目录。请确认项目根目录中存在 index.html 或 docs/ 文件夹。"
        )

    os.chdir(site_dir)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as httpd:
        url = f"http://{args.host}:{args.port}/"
        print(f"Paper Assistant 已启动：{url}")
        print(f"使用 Ctrl-C 停止服务器")
        if args.open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("服务器已停止。")
