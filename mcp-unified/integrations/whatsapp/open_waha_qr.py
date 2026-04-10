"""
Open the WAHA page in a browser and save a screenshot for QR/login inspection.

This is intended to be run on the host machine with a GUI-capable browser
environment. It is a lightweight helper for QR-authenticated WhatsApp sessions.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright


DEFAULT_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3000")
DEFAULT_OUTPUT = Path(
    os.getenv(
        "WHATSAPP_QR_SCREENSHOT",
        "/home/aseps/MCP/logs/whatsapp_waha_qr.png",
    )
)


async def open_waha(url: str, output_path: Path, headed: bool = True) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not headed,
            args=["--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1200})
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)
        html = await page.content()
        await page.screenshot(path=str(output_path), full_page=True)
        print(f"URL      : {url}")
        print(f"Screenshot: {output_path}")
        print(f"Title    : {await page.title()}")
        print(f"Current  : {page.url}")
        print("HTML     :", html[:1200].replace("\n", " "))
        await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open WAHA and capture QR/login screen.")
    parser.add_argument("--url", default=DEFAULT_URL, help="WAHA base URL")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to save screenshot PNG",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless instead of opening a visible browser window",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(open_waha(args.url, Path(args.output), headed=not args.headless))


if __name__ == "__main__":
    main()
