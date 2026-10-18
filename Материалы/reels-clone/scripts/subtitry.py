#!/usr/bin/env python3
"""
Субтитры для клона: карточки рисуются в PNG и накладываются на собранное видео.

Две системы, как в референсе и в СТИЛЬ.md:
  • на сплите — без плашки, строка стоит на шве (титры референса туда не попадают);
  • на полноэкранной вставке — на плашке, которая заодно закрывает вшитый
    субтитр референса.

Плашка рисуется по ширине текста, а не во всю ширину кадра, и она полностью
непрозрачная: при alpha 242 чужой белый текст просвечивал сквозь неё.

Акцентное слово выделяется И цветом, И размером — терять один из двух нельзя.

Все карточки сводятся в ОДИН прозрачный слой на кадр, и ffmpeg делает ровно одно
наложение. Раньше каждая карточка шла отдельным входом и своим overlay-фильтром:
стоимость росла как «кадры × карточки», на ролике в 80 секунд со сотней карточек
это четверть миллиона наложений, и на загруженной машине рендер вставал совсем
(41 минута без единого записанного байта). Слоем — половина минуты.

Кадры с одинаковым набором активных карточек не перерисовываются, на них
ставится жёсткая ссылка: рисуется около сотни картинок вместо двух с половиной
тысяч.
"""

import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).parent
SRC = BASE / "klon_bez_subtitrov.mp4"
OUT = BASE / "klon_final.mp4"
CARDS = BASE / "titry"
CARDS.mkdir(exist_ok=True)
SEKV = BASE / "sekv"      # прозрачный слой титров, по кадру на файл
FPS = 30

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
# Акцентное слово набирается курсивной антиквой — так же, как в опубликованных
# роликах Рамиса (СТИЛЬ.md). Настоящих рукописных с кириллицей в системе нет:
# Apple Chancery и Zapfino отдают квадраты вместо русских букв.
FONT_ACCENT = "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf"
W, H = 1080, 1920

SIZE = 76                    # было 92 — Рамис попросил мельче
ACCENT_SCALE = 1.34            # акцент крупнее: и цветом, и размером, и гарнитурой
SIDE_PAD = 57                # поля кадра из СТИЛЬ.md
PLATE_PAD_X = 24             # воздух вокруг текста внутри плашки
PLATE_PAD_Y = 14
PLATE_RADIUS = 30

WHITE = (255, 255, 255, 255)
ACCENT = (185, 160, 255, 255)     # #B9A0FF — светлее брендового #6739FF:
                                  # тёмно-фиолетовый тонул на синих вставках
PLATE = (38, 38, 42, 255)         # тёмно-серая, не чёрная; непрозрачная — сквозь
                                  # полупрозрачную чужой титр пробивал

# Строка стоит ровно на шве: половина на вставке, половина на тёмном аватаре —
# так она читается на любом фоне. Поднимать её на вставку нельзя: на светлых
# кадрах белый текст сливается. Заезды на лицо давала не эта позиция, а карточки,
# переживавшие смену кадра — они режутся по границам сегментов в karta.py.
Y_SEAM = 830

from karta import build_cards, full_ranges, avatar_ranges

FULL_RANGES = full_ranges()
AVATAR_RANGES = avatar_ranges()
Y_AVATAR = 1190                   # 62% высоты — ниже начинается интерфейс Instagram

CARDS_DATA = build_cards()

# Крупный титр-число сверху — приём этого референса: ключевая цифра
# открывается отдельной строкой на 22% высоты, пока внизу идёт обычный субтитр.
# Роликам без этого приёма ключ в карте просто не нужен.
try:
    from karta import CHISLA
except ImportError:
    CHISLA = []

Y_CHISLO = 420                    # 22% высоты — замерено по референсу
SIZE_CHISLO = 104


# Тёмно-синий #0F2A5C из СТИЛЬ.md рассчитан на белую футболку; на серых
# схемах он вязнет. Текст всегда белый, читаемость на светлом даёт тень.
LIGHT_BG_THRESHOLD = 150          # средняя яркость полосы, выше которой фон считаем светлым


def bg_is_light(t, y_center):
    """
    Светлый ли фон под строкой в этот момент.

    Две цветовые системы — правило из СТИЛЬ.md: на тёмном фоне белый текст,
    на светлом тёмно-синий. Без этого белая строка тонет на светлых вставках
    (схемы на белом, кадр с картофелиной), а тени не хватает.
    """
    # Меряем ВЕРХНЮЮ половину строки. На шве нижняя половина приходится на
    # тёмного аватара, и среднее по всей полосе всегда выходило «серым» —
    # светлая вставка не распознавалась.
    band = max(0, min(H - 70, int(y_center) - 72))
    probe = CARDS / "_probe.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(SRC),
         "-frames:v", "1", "-vf", f"crop={W}:70:0:{band},scale=8:3", str(probe)],
        capture_output=True,
    )
    if not probe.exists():
        return False
    im = Image.open(probe).convert("L")
    pixels = list(im.getdata())
    return sum(pixels) / len(pixels) > LIGHT_BG_THRESHOLD


def in_avatar_shot(t):
    return any(a <= t < b for a, b in AVATAR_RANGES)


def full_range_of(t):
    for a, b, y in FULL_RANGES:
        if a <= t < b:
            return (a, b, y)
    return None


def measure(text, accent, base_color=WHITE):
    """Считает раскладку слов: шрифты, ширины, общую ширину строки."""
    font = ImageFont.truetype(FONT, SIZE)
    font_acc = ImageFont.truetype(FONT_ACCENT, int(SIZE * ACCENT_SCALE))
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    words = text.split()
    fonts = [font_acc if (accent and w == accent) else font for w in words]
    colors = [ACCENT if (accent and w == accent) else base_color for w in words]
    # Ширину берём по реальным глифам, а не по advance: у курсивной антиквы
    # свисающие элементы выходят за advance, и соседние слова налезали друг
    # на друга. bbox учитывает и выносные элементы, и наклон.
    widths = [max(probe.textlength(w, font=f), probe.textbbox((0, 0), w, font=f)[2])
              for w, f in zip(words, fonts)]
    space = probe.textlength(" ", font=font) * 1.4
    total = sum(widths) + space * (len(words) - 1)

    limit = W - 2 * SIDE_PAD - 2 * PLATE_PAD_X
    if total > limit:                      # ужимаем, но кегль между карточками не скачет сильно
        k = limit / total
        font = ImageFont.truetype(FONT, int(SIZE * k))
        font_acc = ImageFont.truetype(FONT_ACCENT, int(SIZE * ACCENT_SCALE * k))
        fonts = [font_acc if (accent and w == accent) else font for w in words]
        widths = [max(probe.textlength(w, font=f), probe.textbbox((0, 0), w, font=f)[2])
                  for w, f in zip(words, fonts)]
        space = probe.textlength(" ", font=font) * 1.4
        total = sum(widths) + space * (len(words) - 1)

    return words, fonts, colors, widths, space, total


def draw_card(index, text, accent, with_plate, heavy_shadow=False):
    words, fonts, colors, widths, space, total = measure(text, accent)

    line_h = int(SIZE * ACCENT_SCALE * 1.35)
    if with_plate:
        cw = int(total) + 2 * PLATE_PAD_X
        ch = line_h + 2 * PLATE_PAD_Y
    else:
        cw = int(total) + 80          # запас под размытую тень
        ch = line_h + 60

    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if with_plate:
        d.rounded_rectangle([(0, 0), (cw - 1, ch - 1)], radius=PLATE_RADIUS, fill=PLATE)

    x0 = (cw - total) / 2
    baseline = ch / 2

    if not with_plate:
        # Мягкая тень отдельным слоем — без обводки, её Рамис забраковал отдельно.
        shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        x = x0
        for w, f, c, wd in zip(words, fonts, colors, widths):
            is_accent = c is ACCENT
            alpha = 255 if heavy_shadow else (245 if is_accent else 215)
            # на светлом фоне тень кладём в два прохода — одного не хватает
            for dy in ((4, 7) if heavy_shadow else (5,)):
                sd.text((x, baseline + dy), w, font=f, fill=(0, 0, 0, alpha), anchor="lm")
            x += wd + space
        # Тень плотнее и шире, чем в СТИЛЬ.md: строка на шве попадает и на светлые
        # вставки, где мягкой тени не хватало — белый текст сливался с фоном.
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(12 if heavy_shadow else 9)))
        d = ImageDraw.Draw(img)

    x = x0
    for w, f, c, wd in zip(words, fonts, colors, widths):
        d.text((x, baseline), w, font=f, fill=c, anchor="lm")
        x += wd + space

    path = CARDS / f"t{index:02d}.png"
    img.save(path)
    return path, cw, ch


def draw_chislo(index, text, size=None):
    """
    Крупный титр сверху: число блока или заголовок хука. Всегда белый и без
    плашки — он стоит в верхней трети, где идут вставки, а плашка на таком
    кегле выглядит баннером. Читаемость на светлом даёт тень в два прохода.

    Переносы строк задаются через \\n: заголовок хука ставится в две строки,
    как в референсе.
    """
    size = size or SIZE_CHISLO
    font = ImageFont.truetype(FONT, size)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    lines = text.split("\n")
    line_h = int(size * 1.22)
    tw = max(probe.textbbox((0, 0), ln, font=font)[2] for ln in lines)

    # Длинный заголовок ужимаем под ширину кадра, иначе он уходит за поля.
    limit = W - 2 * SIDE_PAD
    if tw > limit:
        font = ImageFont.truetype(FONT, int(size * limit / tw))
        line_h = int(size * limit / tw * 1.22)
        tw = max(probe.textbbox((0, 0), ln, font=font)[2] for ln in lines)

    cw, ch = tw + 120, line_h * len(lines) + 110
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    def put(draw, dy, fill):
        y0 = ch / 2 - line_h * (len(lines) - 1) / 2
        for i, ln in enumerate(lines):
            draw.text((cw / 2, y0 + i * line_h + dy), ln, font=font, fill=fill, anchor="mm")

    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for dy in (5, 9):
        put(sd, dy, (0, 0, 0, 235))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(11)))

    put(ImageDraw.Draw(img), 0, WHITE)

    path = CARDS / f"ch{index:02d}.png"
    img.save(path)
    return path, cw, ch


def stretch_within_full(cards):
    """
    Внутри полноэкранной вставки карточки смыкаются встык: пауза между фразами
    оставила бы дыру, в которой видно чужой субтитр.
    """
    out = []
    for i, (start, end, text, accent) in enumerate(cards):
        rng = full_range_of(start)
        if rng:
            a, b, _ = rng
            following = cards[i + 1][0] if i + 1 < len(cards) else None
            # Тянем до следующей карточки, если она в этой же вставке,
            # иначе — до конца вставки.
            end = following if (following is not None and a <= following < b) else b
        out.append((start, end, text, accent))
    return out


def dlitelnost(path):
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(res.stdout.strip())


def sobrat_sloi():
    """Готовит все карточки кадра: субтитры и крупные титры."""
    cards_data = stretch_within_full(CARDS_DATA)
    sloi = []

    for i, (start, end, text, accent) in enumerate(cards_data, 1):
        rng = full_range_of(start)
        y_line = rng[2] if rng else (Y_AVATAR if in_avatar_shot(start) else Y_SEAM)
        # Замер фона стоит запуска ffmpeg на карточку, поэтому меряем только
        # там, где от него что-то зависит: обычная карточка на вставке и так
        # ложится на плашку, и её светлота ни на что не влияет.
        nuzhen_zamer = bool(accent) or not rng
        svetlo = bg_is_light(start + 0.05, y_line) if nuzhen_zamer else False
        # Плашку под акцентной карточкой убираем — акцент должен читаться
        # как выделение, а не как обычный субтитр. Но только на тёмном фоне:
        # на светлой вставке светло-фиолетовый акцент без плашки тонет.
        plate = bool(rng) and (not accent or svetlo)
        light = (not plate) and svetlo
        p, cw, ch = draw_card(i, text, accent, with_plate=plate, heavy_shadow=light)
        sloi.append((Image.open(p).convert("RGBA"),
                     (W - cw) // 2, y_line - ch // 2, start, end))

    # Элемент карты: (старт, конец, текст) либо (старт, конец, текст, Y, кегль).
    # Своя позиция нужна заголовку хука: он стоит не на 22%, а у самого шва.
    for i, item in enumerate(CHISLA, 1):
        start, end, text = item[0], item[1], item[2]
        y_line = item[3] if len(item) > 3 else Y_CHISLO
        size = item[4] if len(item) > 4 else None
        p, cw, ch = draw_chislo(i, text, size)
        sloi.append((Image.open(p).convert("RGBA"),
                     (W - cw) // 2, y_line - ch // 2, start, end))

    return sloi


def narisovat_sekvenciyu(sloi, kadrov):
    """Прозрачный слой на каждый кадр; одинаковые кадры не перерисовываются."""
    if SEKV.exists():
        shutil.rmtree(SEKV)
    SEKV.mkdir()

    kesh, narisovano = {}, 0
    for n in range(kadrov):
        t = n / FPS
        aktivnye = tuple(i for i, s in enumerate(sloi) if s[3] <= t < s[4])
        put = SEKV / f"{n:05d}.png"

        gotovoe = kesh.get(aktivnye)
        if gotovoe:
            os.link(gotovoe, put)      # тот же набор карточек — тот же кадр
            continue

        holst = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i in aktivnye:
            img, x, y, _, _ = sloi[i]
            holst.alpha_composite(img, (max(0, x), max(0, y)))
        holst.save(put)
        kesh[aktivnye] = put
        narisovano += 1

    return narisovano


def main():
    if not CARDS_DATA:
        raise SystemExit("CARDS_DATA пуст — заполните карточки под таймкоды аватара")

    sloi = sobrat_sloi()
    kadrov = int(dlitelnost(SRC) * FPS)
    narisovano = narisovat_sekvenciyu(sloi, kadrov)

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(SRC),
        "-framerate", str(FPS), "-i", str(SEKV / "%05d.png"),
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-shortest", str(OUT),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-1500:])

    subs = len(sloi) - len(CHISLA)
    print(f"Готово: {OUT.name}  ·  субтитров {subs}, крупных титров {len(CHISLA)}")
    print(f"кадров {kadrov}, из них нарисовано {narisovano}, остальные — ссылки")


if __name__ == "__main__":
    main()
