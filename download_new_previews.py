import asyncio
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

CATALOG_PATH = Path('/home/artem/Other/catalog-repo/catalog.json')
OUTPUT_DIR = Path('/home/artem/Other/dota2-media/images')
CONCURRENCY = 10
RETRY_COUNT = 3
TIMEOUT_SECONDS = 45


def slugify_filename(name: str) -> str:
    name = unquote(name)
    name = Path(name).name
    name = re.sub(r'[^A-Za-z0-9._-]+', '-', name)
    name = re.sub(r'-+', '-', name).strip('-')
    return name or 'file'


async def download_one(url: str, destination: Path) -> bool:
    if destination.exists() and destination.stat().st_size > 0:
        print(f'Skipped existing: {destination}')
        return True

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                data = response.read()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            print(f'Downloaded: {destination}')
            return True
        except Exception as exc:
            if attempt == RETRY_COUNT:
                print(f'Failed after {RETRY_COUNT} attempts: {url} -> {exc}')
                return False
            await asyncio.sleep(attempt * 1.5)

    return False


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(CATALOG_PATH, encoding='utf-8') as raw:
        content = json.load(raw)

    mods_data = content.get('mods', {}).get('modsData', {})

    target_categories = ['music', 'mega-kill', 'roshan', 'emblems', 'creeps', 'creep-deny', 'item-effects']
    urls: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for category in target_categories:
        for item in mods_data.get(category, []):
            preview = item.get('preview')
            if not preview or not isinstance(preview, str):
                continue
            if not preview.startswith('http'):
                continue
            if 'githubusercontent.com' not in preview and 'raw.githubusercontent.com' not in preview:
                continue
            key = (category, preview)
            if key in seen:
                continue
            seen.add(key)
            urls.append((category, preview))

    print(f'Total preview URLs: {len(urls)}')

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def worker(category: str, url: str) -> None:
        async with semaphore:
            parsed = urlparse(url)
            filename = slugify_filename(parsed.path)
            if not filename:
                filename = 'preview'
            destination = OUTPUT_DIR / filename
            await download_one(url, destination)

    tasks = [asyncio.create_task(worker(category, url)) for category, url in urls]
    await asyncio.gather(*tasks)

    print('Finished downloading previews')


if __name__ == '__main__':
    asyncio.run(main())
