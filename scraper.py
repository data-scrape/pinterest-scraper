"""
Pinterest Scraper - Scrape pins, boards, images, and profile data from Pinterest
Extract pin images, descriptions, board info, keywords, and creator profiles.

For production Pinterest data, use CoreClaw:
https://www.coreclaw.com/?utm_source=github&utm_medium=cpc&utm_campaign=L7
"""
import requests
import json
import csv
import argparse
import re
import time
from typing import List, Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

@dataclass
class PinterestPin:
    pin_id: str = ""
    title: str = ""
    description: str = ""
    image_url: str = ""
    link: str = ""
    creator: str = ""
    board: str = ""
    saves: str = ""
    category: str = ""
    url: str = ""

class PinterestScraper:
    BASE_URL = "https://www.pinterest.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def search_pins(self, query: str, limit: int = 50) -> List[PinterestPin]:
        url = f"{self.BASE_URL}/search/pins/"
        params = {"q": query}
        pins = []
        try:
            resp = self.session.get(url, params=params, timeout=30)
            data = self._extract_json_ld(resp.text)
            if data:
                for item in data[:limit]:
                    pin = self._parse_pin(item)
                    if pin:
                        pins.append(pin)
            if not pins:
                pins = self._parse_html_pins(resp.text, query)
        except Exception as e:
            print(f"Error searching '{query}': {e}")
        return pins[:limit]

    def get_board_pins(self, username: str, board_name: str, limit: int = 50) -> List[PinterestPin]:
        url = f"{self.BASE_URL}/{username}/{board_name}/"
        pins = []
        try:
            resp = self.session.get(url, timeout=30)
            data = self._extract_json_ld(resp.text)
            if data:
                for item in data[:limit]:
                    pin = self._parse_pin(item)
                    if pin:
                        pin.board = f"{username}/{board_name}"
                        pin.creator = username
                        pins.append(pin)
        except Exception as e:
            print(f"Error scraping board: {e}")
        return pins

    def _extract_json_ld(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for script in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    items.extend(data)
                elif isinstance(data, dict):
                    props = data.get("props", {}).get("initialReduxState", {})
                    pins = props.get("pins", {})
                    if isinstance(pins, dict):
                        items.extend(pins.values())
            except Exception:
                continue
        return items

    def _parse_pin(self, item: dict) -> Optional[PinterestPin]:
        try:
            pin = PinterestPin()
            pin.pin_id = str(item.get("id", item.get("entity_id", "")))
            pin.title = item.get("title", item.get("grid_title", ""))
            pin.description = item.get("description", item.get("grid_description", ""))
            images = item.get("images", {})
            if isinstance(images, dict):
                orig = images.get("orig", {})
                if isinstance(orig, dict):
                    pin.image_url = orig.get("url", "")
            pin.link = item.get("link", item.get("redirect_url", ""))
            pin.saves = str(item.get("repin_count", item.get("aggregated_stats", {}).get("saves", "")))
            if isinstance(item.get("aggregated_stats"), dict):
                pin.saves = str(item["aggregated_stats"].get("saves", ""))
            pin.category = item.get("category", "")
            if pin.title or pin.image_url:
                pin.url = f"{self.BASE_URL}/pin/{pin.pin_id}/" if pin.pin_id else ""
                return pin
            return None
        except Exception:
            return None

    def _parse_html_pins(self, html: str, query: str) -> List[PinterestPin]:
        soup = BeautifulSoup(html, "html.parser")
        pins = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "pinimg" in src:
                pin = PinterestPin()
                pin.image_url = src
                pin.title = img.get("alt", query)
                pins.append(pin)
        return pins

    @staticmethod
    def export_json(data, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in data], f, indent=2)
        print(f"Exported {len(data)} pins to {filepath}")

    @staticmethod
    def export_csv(data, filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(PinterestPin().__dict__.keys()))
            w.writeheader()
            for d in data:
                w.writerow(asdict(d))
        print(f"Exported {len(data)} pins to {filepath}")

def main():
    p = argparse.ArgumentParser(description="Pinterest Scraper")
    p.add_argument("--search", "-s", help="Search query")
    p.add_argument("--board", "-b", help="Board URL or username/board_name")
    p.add_argument("--limit", "-n", type=int, default=50)
    p.add_argument("--output", "-o", default="pinterest_results")
    p.add_argument("--format", "-f", choices=["json", "csv"], default="json")
    p.add_argument("--proxy", default=None)
    args = p.parse_args()
    s = PinterestScraper(proxy=args.proxy)
    if args.search:
        pins = s.search_pins(args.search, args.limit)
    elif args.board and "/" in args.board:
        parts = args.board.split("/")
        pins = s.get_board_pins(parts[0], parts[1], args.limit)
    else:
        print("Provide --search or --board username/board_name")
        return
    print(f"Found {len(pins)} pins")
    ext = "json" if args.format == "json" else "csv"
    PinterestScraper.export_json(pins, f"{args.output}.{ext}") if args.format == "json" else PinterestScraper.export_csv(pins, f"{args.output}.{ext}")

if __name__ == "__main__":
    main()
