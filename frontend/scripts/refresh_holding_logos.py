"""Refresh the app's holding logo cache without discarding usable copies."""

import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
from xml.etree import ElementTree


SOURCES = Path(__file__).with_name("holding-logo-sources.json")
CACHE = SOURCES.parents[1] / "src" / "assets" / "holding-logos"
MAX_BYTES = 128 * 1024


def is_image(data: bytes, suffix: str) -> bool:
    if suffix == ".ico":
        return len(data) >= 22 and data[:4] == b"\0\0\1\0"
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    return suffix == ".svg" and ElementTree.fromstring(data).tag == "{http://www.w3.org/2000/svg}svg"


def refresh(path: Path, url: str) -> None:
    request = Request(url, headers={"User-Agent": "UclAgentVerse/1.0 (holding logo refresh)"})
    with urlopen(request, timeout=10) as response:
        data = response.read(MAX_BYTES + 1)
        if not response.headers.get_content_type().startswith("image/"):
            raise ValueError("The source did not return an image")
    if len(data) > MAX_BYTES or not is_image(data, path.suffix):
        raise ValueError("Unexpected logo format or size")
    if path.exists() and path.read_bytes() == data:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    failures = 0
    for filename, url in json.loads(SOURCES.read_text(encoding="utf-8")).items():
        try:
            refresh(CACHE / filename, url)
            print(f"{filename}: cached")
        except (OSError, ValueError, ElementTree.ParseError) as error:
            failures += 1
            print(f"{filename}: {error}. Cache left intact.")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
