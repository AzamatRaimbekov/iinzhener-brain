#!/usr/bin/env python3
"""
Карта ролика: сегменты монтажа и карточки субтитров.

Отсюда sborka.py и subtitry.py берут свои данные — чтобы тайминги правились
в одном месте, а не в двух файлах.

Сегменты привязаны к СМЫСЛУ (что говорится), а не к секундам оригинала:
русская речь длиннее английской, ролик вырастает на 15–20%.
"""

import json
from pathlib import Path

BASE = Path(__file__).parent

# (старт, конец, режим, источник, длительность источника, подпись)
# режимы: split  — вставка сверху + аватар снизу
#         full   — вставка из ref.mp4 на весь кадр
#         png    — своя вставка из vstavki/, поле «источник» несёт имя файла
#         avatar — только аватар
#
# Замедление источника везде 1.02–1.23: ускоренное движение читается как брак,
# замедленное — нет.
SEGMENTS = [
    # ЗАПОЛНИТЬ под конкретный ролик.
    # (0.00, 3.00, "split",  0.0,  2.80, "пример: вставка сверху, аватар снизу"),
    # (3.00, 6.00, "full",  12.4,  2.70, "пример: вставка из референса на весь кадр"),
    # (6.00, 9.00, "png",   "v1",  0,    "пример: своя вставка из vstavki/v1.png"),
    # (9.00, 11.0, "avatar", 0,    0,    "пример: аватар в полный кадр"),
]

# Где в полноэкранном сегменте сидит вшитый титр референса — его замыливаем.
# Замерено в пяти точках (t = 8, 30, 46, 62, 80): везде 1415, разброса нет.
# Это редкая удача — у прошлых блогеров позиция гуляла от 48% до 78% высоты.
TITLE_Y = {i: 1415 for i, seg in enumerate(SEGMENTS, 1) if seg[2] == "full"}

# Замыливание в ВЕРХНЕЙ вставке сплита: {индекс сегмента: (y, высота)}.
# Титр «Elon Musk Just Open-Sourced» стоит на 825, наш шов — 830. Без полосы
# в кадр попадала бы полоска верхушек английских букв.
SPLIT_BLUR = {}          # например {1: (768, 62)}

# У референса свой крупный титр-число в верхней трети — замерен на 395..448.
# Он попадает только в сегменты 3 и 4: их источник взят из блока перечисления
# весов (0–22 с оригинала), где эти титры и живут. У остальных сегментов в этой
# полосе идёт контент вставки, а не титр, — проверено покадрово, их не трогаем.
TOP_BLUR = {}            # например {3: (382, 80), 4: (382, 80)}

# Наша строка стоит на 1190 (62% высоты, СТИЛЬ.md) — НЕ там, где чужая.
# Референс кладёт свои титры на 1415, то есть под кнопки Instagram: копировать
# это не надо, а перекрывать его строку нашей и не требуется — она замылена.
Y_STROKI = 1190

# Whisper пишет числа цифрами, а произнесены они словами.
FIX = {
    # ЗАПОЛНИТЬ по факту: whisper пишет произнесённое «двести» как «200».
    # Сюда же ослышки распознавания и потерянные «ё».
    # "200": "двести",
}

# Замены, привязанные к моменту: одно и то же «20» произнесено в двух падежах,
# и словарь по корню слова накрыл бы оба одинаково. Пустая строка = выбросить
# слово: на 13.83 whisper вставил лишнее «с» («отправка с ссылки»).
FIX_AT = {
    # ЗАПОЛНИТЬ при конфликте: одно слово в разных формах или лишний токен.
    # 13.83: "",            # выбросить слово целиком
    # 50.37: "двадцати",    # своя форма именно в этом месте
}

PUNCT = ".,!?–:;"

# Слова, которые выделяем цветом, размером и антиквой. Сравнение по корню.
ACCENTS = set()          # 5–9 ключевых слов на ролик, без знаков препинания

# Крупный титр в верхней трети: (старт, конец, текст[, Y, кегль]).
# Заголовок хука стоит ниже остальных — у самого шва, как в референсе.
CHISLA = []
# Пример: [(0.35, 2.55, "ЗАГОЛОВОК\nВ ДВЕ СТРОКИ", 560, 88), (5.6, 6.9, "0,5")]
# Перенос строки задаётся через \n. Y и кегль необязательны: без них титр
# встаёт на 22% высоты. Роликам без этого приёма список остаётся пустым.

MAX_WORDS = 2        # слов на карточку: Рамис просил 1–2, максимум 3
MERGE_LIMIT = 3      # предел при склейке коротких карточек
MIN_DUR = 0.45       # короче — мельтешит
BREAK_AFTER = (".", ",", "–", ":", "!", "?")

# На этих словах карточку не разрываем — предлог, повисший в конце строки,
# читается как обрыв и тянет за собой карточку в 0,2 секунды.
GLUE = {"в", "и", "а", "на", "с", "со", "по", "к", "у", "о", "об",
        "из", "для", "до", "от", "за", "же", "про", "над", "под"}


def load_words():
    """Слова с таймкодами, числа — обратно в словесную форму.

    Замена идёт по ядру слова: whisper отдаёт токен вместе со знаком
    препинания («13%,»), и словарь по точному совпадению его не ловил.
    Точечные замены из FIX_AT имеют приоритет над общими.
    """
    raw = json.load(open(BASE / "slova.json"))
    out = []
    for start, word in raw:
        core = word.rstrip(PUNCT)
        tail = word[len(core):]

        tochka = next((v for t, v in FIX_AT.items() if abs(t - start) < 0.01), None)
        zamena = tochka if tochka is not None else FIX.get(core, core)
        if not zamena:                     # пустая замена = выбросить слово
            continue
        out.append((start, zamena + tail))

    # Whisper иногда отдаёт два слова на одном таймкоде («Но важнее» — оба 33.10).
    # Карточка из них получается нулевой длины и вылетает при отсечке коротких:
    # фраза молча пропадает из титров. Раздвигаем такие пары.
    razdvinutye = [out[0]] if out else []
    for start, word in out[1:]:
        predyduschiy = razdvinutye[-1][0]
        razdvinutye.append((max(start, predyduschiy + 0.06), word))
    return razdvinutye


def build_cards():
    """Режет поток слов на карточки: по 2–3 слова, с разрывом на знаках."""
    words = load_words()
    cards, buf = [], []

    for i, (start, word) in enumerate(words):
        buf.append((start, word))
        nxt = words[i + 1][0] if i + 1 < len(words) else start + 0.9
        ends_phrase = word.endswith(BREAK_AFTER)
        gap = nxt - start

        hangs_on_preposition = word.strip(".,–:").lower() in GLUE and not ends_phrase
        # Карточку короче MIN_DUR не закрываем, даже если слов уже набралось:
        # быстрые пары вроде «И вот» whisper отдаёт почти одним таймкодом, такая
        # карточка вылетала по отсечке и фраза молча пропадала. Копим дальше,
        # а разбор на пары ниже сам порежет переросшую карточку.
        korotko = (nxt - buf[0][0]) < MIN_DUR
        if (ends_phrase or ((len(buf) >= MAX_WORDS or gap > 0.55) and not korotko)) \
                and not hangs_on_preposition:
            text = " ".join(w for _, w in buf)
            accent = next((w for _, w in buf if w.rstrip(PUNCT).lower() in ACCENTS), None)
            cards.append([buf[0][0], nxt, text, accent])
            buf = []

    if buf:
        text = " ".join(w for _, w in buf)
        cards.append([buf[0][0], buf[-1][0] + 0.9, text, None])

    # Слишком короткую карточку сливаем со следующей: приклеивать к предыдущей
    # нельзя — она уже показана и текст дёрнется на середине фразы.
    merged = []
    i = 0
    while i < len(cards):
        card = cards[i]
        # Ограничение по длине строки, а не по числу слов: мелькнувшая карточка
        # хуже длинной, но в кадр строка должна влезать без ужимания кегля.
        while ((card[1] - card[0]) < MIN_DUR and i + 1 < len(cards)
               and len(card[2].split()) + len(cards[i + 1][2].split()) <= MERGE_LIMIT
               and len(card[2]) + len(cards[i + 1][2]) + 1 <= 30):
            nxt = cards[i + 1]
            card = [card[0], nxt[1], f"{card[2]} {nxt[2]}", card[3] or nxt[3]]
            i += 1
        merged.append(card)
        i += 1

    # Режем карточки по границам сегментов. Карточка, пережившая смену кадра,
    # остаётся на старой позиции — и на долю секунды ложится на лицо, потому что
    # в новой композиции строка должна стоять в другом месте.
    bounds = sorted({b for _, b, *_ in SEGMENTS} | {a for a, *_ in SEGMENTS})
    split_by_shot = []
    for start, end, text, accent in merged:
        cur = start
        for b in bounds:
            if cur < b < end:
                split_by_shot.append([cur, b, text, accent])
                cur = b
        split_by_shot.append([cur, end, text, accent])
    merged = [c for c in split_by_shot if c[1] - c[0] >= 0.2]

    # Жёсткий предел: больше MERGE_LIMIT слов в кадре не показываем. Такие
    # карточки появляются после замены «13%» на два слова — режем их надвое.
    normalized = []
    for start, end, text, accent in merged:
        words = text.split()
        if len(words) <= MERGE_LIMIT:
            normalized.append([start, end, text, accent])
            continue
        half = len(words) // 2
        mid = start + (end - start) * half / len(words)
        left, right = " ".join(words[:half]), " ".join(words[half:])
        normalized.append([start, mid, left, accent if accent and accent in left else None])
        normalized.append([mid, end, right, accent if accent and accent in right else None])
    merged = normalized

    # Чистим текст: строчные, знаки в конце не нужны — карточка и так короткая.
    # Одиночное тире выкидываем целиком, иначе от него остаётся пустой хвост.
    final = []
    for start, end, text, accent in merged:
        words = [w for w in text.split() if w not in ("–", "-", "—")]
        clean = " ".join(words).lower().strip(" .,–:")
        acc = accent.lower().strip(" .,–:") if accent else None
        if not clean:
            continue
        final.append((round(start, 2), round(end, 2), clean, acc))
    return final


def avatar_ranges():
    """Диапазоны, где аватар в полный кадр: (старт, конец).
    Строка там уходит вниз, на 62% высоты — на шве она легла бы на лицо."""
    return [(a, b) for a, b, mode, *_ in SEGMENTS if mode == "avatar"]


def full_ranges():
    """Диапазоны вставок с позицией строки: (старт, конец, Y).

    Свои PNG-вставки идут сюда же: фон у них белый, и строка там нужна
    на плашке — иначе белый текст сливается с таблицей.
    """
    out = []
    for s, e, mode, *_rest in SEGMENTS:
        if mode in ("full", "png"):
            out.append((s, e, Y_STROKI))
    return out


if __name__ == "__main__":
    cards = build_cards()
    hvost = SEGMENTS[-1][1]
    print(f"сегментов: {len(SEGMENTS)}, карточек: {len(cards)}, "
          f"крупных титров: {len(CHISLA)}, хвост: {hvost:.2f}с")
    for c in cards:
        print(f"  {c[0]:6.2f}–{c[1]:6.2f}  {c[2]}" + (f"   [{c[3]}]" if c[3] else ""))
