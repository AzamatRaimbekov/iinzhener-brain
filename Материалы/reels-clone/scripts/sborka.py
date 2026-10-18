#!/usr/bin/env python3
"""
Сборка клона рилса: аватар HeyGen + вставки из референса.

Логика: ролик построен на сплите (вставка сверху, спикер снизу) с редкими
полноэкранными вставками. Звук берётся целиком из аватара отдельной дорожкой —
как в МЕТОДОЛОГИЯ.md, чтобы не держать лишние видеослои ради аудио.

Геометрия шва — 830 px из СТИЛЬ.md. Побочная польза: вшитые субтитры
референса сидят на 45–48% высоты и при обрезке по 830 в кадр не попадают.
"""

import subprocess
from pathlib import Path

BASE = Path(__file__).parent
REF = BASE / "ref.mp4"
AVATAR = BASE / "avatar.mp4"
OUT = BASE / "sborka"
OUT.mkdir(exist_ok=True)

SEAM = 830          # шов сплита, px от верха кадра 1080×1920
W, H = 1080, 1920
BOTTOM = H - SEAM   # 1090 px — высота нижней части

# Кроп аватара: берём квадрат с лицом и вписываем в нижнюю половину,
# чтобы макушка встала сразу под швом, а не была срезана.
AV_CROP_Y = 400
AV_CROP_H = 1080

from karta import SEGMENTS, TITLE_Y

# Замыливание полосы в ВЕРХНЕЙ вставке сплита: {индекс сегмента: (y, высота)}.
# Нужно, когда чужой титр сидит впритык над швом и обрезка оставляет в кадре
# верхушки букв. В этом референсе «Elon Musk Just Open-Sourced» стоит на 825
# при нашем шве 830 — без полосы английский торчал бы полоской.
try:
    from karta import SPLIT_BLUR
except ImportError:
    SPLIT_BLUR = {}

# Вторая полоса замыливания в ПОЛНОЭКРАННОМ сегменте: {индекс: (y, высота)}.
# У этого референса есть свой крупный титр-число в верхней трети — он лежит
# выше того титра, что закрывает основная полоса, и одной полосой их не накрыть.
try:
    from karta import TOP_BLUR
except ImportError:
    TOP_BLUR = {}

# Высота замыливаемой полосы. Держим её близкой к высоте нашей плашки: широкая
# полоса торчит из-под строки размытыми краями сверху и снизу и читается как
# отдельный артефакт. Чужой титр в этом референсе занимает 1384..1446, плашка
# накрывает примерно 1345..1485 — полоса в 150 px ложится ровно под неё.
BLUR_BAND = 150


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg упал:\n{' '.join(cmd)}\n{res.stderr[-800:]}")


def build_segment(index, seg):
    start, end, mode, src_start, src_dur, label = seg
    dur = round(end - start, 3)
    # >1 = замедляем исходник, чтобы закрыть отрезок. В режиме avatar источника нет.
    speed = dur / src_dur if src_dur else 1.0
    out = OUT / f"s{index:02d}.mp4"

    if mode == "full":
        # Вставка на весь кадр: аватара не видно, идёт только его голос.
        # Полосу с вшитым титром референса замыливаем: компактная плашка
        # субтитра его не перекрывает — чужой текст торчал по бокам.
        polosy = [(max(0, TITLE_Y.get(index, 1250) - BLUR_BAND // 2), BLUR_BAND)]
        if index in TOP_BLUR:
            polosy.append(TOP_BLUR[index])

        # Каждая полоса — своя ветка split → crop → boxblur → overlay.
        vf = (f"setpts={speed:.4f}*PTS,"
              f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"split={len(polosy) + 1}" + "".join(f"[p{n}]" for n in range(len(polosy) + 1)) + ";")
        cur_tag = "[p0]"
        for n, (by, bh) in enumerate(polosy):
            radius = max(2, min(28, bh // 4))
            out_tag = f"[o{n}]" if n < len(polosy) - 1 else ""
            vf += (f"[p{n + 1}]crop={W}:{bh}:0:{by},boxblur={radius}:2[bl{n}];"
                   f"{cur_tag}[bl{n}]overlay=0:{by}{out_tag};")
            cur_tag = out_tag
        vf = vf.rstrip(";")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(src_start), "-t", str(src_dur), "-i", str(REF),
            "-an", "-vf", vf, "-t", str(dur),
            "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out),
        ]
    elif mode == "png":
        # Своя вставка: русская таблица/карточка из vstavki/. Чужого титра на ней
        # нет, поэтому и замыливать нечего. Поле src_start здесь несёт имя файла —
        # так карта остаётся одним плоским кортежем на все режимы.
        src = BASE / "vstavki" / f"{src_start}.png"
        if not src.exists():
            raise FileNotFoundError(f"нет вставки {src}")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-t", str(dur), "-i", str(src),
            "-an", "-vf", f"scale={W}:{H},setsar=1",
            "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out),
        ]
    elif mode == "avatar":
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(start), "-t", str(dur), "-i", str(AVATAR),
            "-an", "-vf", f"scale={W}:{H},setsar=1", "-t", str(dur),
            "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out),
        ]
    else:
        # Сплит: верх — вставка из референса (обрезана по шву, его титры отсечены),
        # низ — аватар, перекадрированный так, чтобы макушка встала под шов.
        blur = SPLIT_BLUR.get(index)
        if blur:
            by, bh = blur
            # boxblur упирается в размер плоскости цветности: на полосе высотой
            # 62 px радиус больше 15 отвергается. Держим его в четверти высоты.
            radius = max(2, min(28, bh // 4))
            top = (
                f"[0:v]setpts={speed:.4f}*PTS,crop={W}:{SEAM}:0:0,setsar=1,split[t1][t2];"
                f"[t2]crop={W}:{bh}:0:{by},boxblur={radius}:2[tb];"
                f"[t1][tb]overlay=0:{by}[top];"
            )
        else:
            top = f"[0:v]setpts={speed:.4f}*PTS,crop={W}:{SEAM}:0:0,setsar=1[top];"
        fc = (
            top +
            f"[1:v]crop={W}:{AV_CROP_H}:0:{AV_CROP_Y},scale={W}:{BOTTOM},setsar=1[bot];"
            f"[top][bot]vstack=inputs=2[v]"
        )
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(src_start), "-t", str(src_dur), "-i", str(REF),
            "-ss", str(start), "-t", str(dur), "-i", str(AVATAR),
            "-filter_complex", fc, "-map", "[v]", "-an", "-t", str(dur),
            "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out),
        ]

    run(cmd)
    print(f"  {index:02d}. {start:5.2f}–{end:5.2f}с  {mode:5s}  {label}"
          f"{'  (замедление ×%.2f)' % speed if speed > 1.05 else ''}")
    return out


def main():
    print("Собираю сегменты:")
    parts = [build_segment(i, s) for i, s in enumerate(SEGMENTS, 1)]

    listfile = OUT / "list.txt"
    listfile.write_text("".join(f"file '{p.name}'\n" for p in parts))

    silent = BASE / "video_bez_zvuka.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c", "copy", str(silent)])

    final = BASE / "klon_bez_subtitrov.mp4"
    run(["ffmpeg", "-y", "-v", "error",
         "-i", str(silent), "-i", str(AVATAR),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(final)])

    print(f"\nГотово: {final.name}")


if __name__ == "__main__":
    main()
