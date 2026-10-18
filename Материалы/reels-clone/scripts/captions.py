#!/usr/bin/env python3
"""Достать таймкодированный транскрипт с YouTube на любом языке.

Зачем: скилл `watch` тянет субтитры только на английском
(`--sub-langs en.*` в его download.py), поэтому на русских роликах
он остаётся без транскрипта. Этот скрипт закрывает дыру: берёт
ru/en/оригинал, чистит от повторов авто-субтитров и печатает
готовый транскрипт с таймкодами.

Использование:
    python3 captions.py <url> [--langs ru,en] [--out-dir DIR] [--raw]

Печатает в stdout транскрипт вида "[MM:SS] текст".
Ничего никуда не отправляет — только yt-dlp к площадке.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMESTAMP_LINE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)
INLINE_TAG = re.compile(r"<[^>]+>")


class CaptionError(RuntimeError):
    """Транскрипт получить не удалось — с внятной причиной."""


def require_yt_dlp() -> str:
    found = shutil.which("yt-dlp")
    if not found:
        raise CaptionError(
            "yt-dlp не установлен. Поставь: brew install yt-dlp"
        )
    return found


def fetch_subtitles(url: str, langs: list[str], out_dir: Path) -> Path | None:
    """Скачать VTT-субтитры (сначала ручные, потом авто) в out_dir."""
    yt_dlp = require_yt_dlp()
    out_dir.mkdir(parents=True, exist_ok=True)
    sub_langs = ",".join(f"{lang}.*" for lang in langs) + ",-live_chat"

    command = [
        yt_dlp,
        "--skip-download",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", sub_langs,
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        "-o", str(out_dir / "video.%(ext)s"),
        "--",
        url,
    ]
    try:
        subprocess.run(command, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
    except subprocess.TimeoutExpired as exc:
        raise CaptionError("yt-dlp не уложился в 5 минут — проверь сеть или ссылку") from exc

    return pick_subtitle(out_dir, langs)


def pick_subtitle(out_dir: Path, langs: list[str]) -> Path | None:
    """Выбрать лучший VTT: приоритет по порядку языков, ручные важнее авто."""
    candidates = sorted(out_dir.glob("video*.vtt"))
    if not candidates:
        return None

    def rank(path: Path) -> tuple[int, int]:
        name = path.name
        language_rank = len(langs)
        for index, lang in enumerate(langs):
            if f".{lang}." in name or f".{lang}-" in name:
                language_rank = index
                break
        # "-orig" у YouTube означает исходную дорожку, а не машинный перевод
        auto_rank = 0 if "-orig" in name else 1
        return (language_rank, auto_rank)

    return sorted(candidates, key=rank)[0]


def read_metadata(out_dir: Path, url: str) -> dict:
    info_path = out_dir / "video.info.json"
    if not info_path.exists():
        return {"url": url}
    try:
        raw = json.loads(info_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[captions] info.json не прочитался: {exc}", file=sys.stderr)
        return {"url": url}
    return {
        "title": raw.get("title"),
        "uploader": raw.get("uploader") or raw.get("channel"),
        "duration": raw.get("duration"),
        "url": raw.get("webpage_url") or url,
    }


def parse_vtt(path: Path) -> list[tuple[float, str]]:
    """VTT → [(секунды, строка)], без дублей скользящего окна авто-субтитров."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CaptionError(f"не смог прочитать {path}: {exc}") from exc

    cues: list[tuple[float, str]] = []
    current_start: float | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_start is None or not buffer:
            return
        text = " ".join(buffer).strip()
        if text:
            cues.append((current_start, text))

    for line in raw.splitlines():
        match = TIMESTAMP_LINE.search(line)
        if match:
            flush()
            buffer = []
            hours, minutes, seconds, millis = (int(match.group(i)) for i in (1, 2, 3, 4))
            current_start = hours * 3600 + minutes * 60 + seconds + millis / 1000
            continue
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT" or stripped.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if stripped.isdigit():
            continue
        cleaned = html.unescape(INLINE_TAG.sub("", stripped)).strip()
        if cleaned:
            buffer.append(cleaned)
    flush()

    return dedupe(cues)


def strip_overlap(previous: str, current: str) -> str:
    """Отрезать у current начало, которое уже прозвучало в конце previous.

    Авто-субтитры YouTube едут скользящим окном: реплика N = "A B",
    реплика N+1 = "B C". Без этого транскрипт читается с двоением.
    Сравниваем по словам, а не по символам — иначе рвём слова пополам.
    """
    previous_words = previous.split()
    current_words = current.split()
    if not previous_words or not current_words:
        return current

    max_overlap = min(len(previous_words), len(current_words))
    for size in range(max_overlap, 0, -1):
        if previous_words[-size:] == current_words[:size]:
            return " ".join(current_words[size:])
    return current


def dedupe(cues: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Убрать повторы скользящего окна авто-субтитров."""
    result: list[tuple[float, str]] = []
    for start, text in cues:
        if not result:
            result.append((start, text))
            continue

        previous_text = result[-1][1]
        if text == previous_text or text in previous_text:
            continue

        remainder = strip_overlap(previous_text, text).strip()
        if not remainder:
            continue
        result.append((start, remainder))
    return result


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="ссылка на видео (YouTube и всё, что умеет yt-dlp)")
    parser.add_argument(
        "--langs",
        default="ru,en",
        help="языки субтитров по приоритету, через запятую (по умолчанию ru,en)",
    )
    parser.add_argument("--out-dir", help="куда класть рабочие файлы (по умолчанию временная папка)")
    parser.add_argument("--raw", action="store_true", help="печатать без таймкодов, сплошным текстом")
    args = parser.parse_args()

    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    if not langs:
        print("[captions] пустой --langs", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else Path(tempfile.mkdtemp(prefix="captions-"))

    try:
        subtitle_path = fetch_subtitles(args.url, langs, out_dir)
    except CaptionError as exc:
        print(f"[captions] {exc}", file=sys.stderr)
        return 1

    metadata = read_metadata(out_dir, args.url)
    if metadata.get("title"):
        print(f"# {metadata['title']}")
    if metadata.get("uploader"):
        print(f"Канал: {metadata['uploader']}")
    if metadata.get("duration"):
        print(f"Длительность: {format_timestamp(metadata['duration'])}")
    print(f"Источник: {metadata.get('url', args.url)}")
    print(f"Рабочая папка: {out_dir}")
    print()

    if subtitle_path is None:
        print(
            "[captions] субтитров нет ни на одном из языков: "
            f"{', '.join(langs)}. Нужен Whisper — см. SKILL.md, раздел «Нет субтитров».",
            file=sys.stderr,
        )
        return 3

    try:
        cues = parse_vtt(subtitle_path)
    except CaptionError as exc:
        print(f"[captions] {exc}", file=sys.stderr)
        return 1

    if not cues:
        print(f"[captions] файл {subtitle_path.name} пустой после разбора", file=sys.stderr)
        return 3

    print(f"Субтитры: {subtitle_path.name} ({len(cues)} реплик)")
    print()
    if args.raw:
        print(" ".join(text for _, text in cues))
    else:
        for start, text in cues:
            print(f"[{format_timestamp(start)}] {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
