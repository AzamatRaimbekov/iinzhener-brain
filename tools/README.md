# 🛠 Как пересобрать базу

Скрипты, которыми собрана эта база. Нужны, если в группе появились новые уроки или материалы.

| Шаг | Скрипт | Что делает |
|---|---|---|
| 1 | `tg-find-chat.ts` | находит id Telegram-группы по названию |
| 2 | `tg-export-chat.ts` | выгружает всю историю группы в `messages.jsonl`, `--download` также скачивает pdf/pptx/zip |
| 3 | `yt-dlp` | скачивает русские субтитры записей (`--skip-download --write-auto-subs --sub-langs "ru.*"`) |
| 4 | `build_brain.py` | собирает уроки, каталоги и расшифровки из выгрузки, субтитров и конспектов |
| 5 | `build_ui.py` | собирает `index.html` (сайт) из всех `.md` |

```bash
# 1–2: нужен Node 22 и пакет `telegram`, а также TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SESSION_FILE в .env
npx tsx tg-export-chat.ts <chatId> ../raw --download
# 4–5
python build_brain.py ../raw ..
python build_ui.py ..
```

Ожидаемая структура `raw/`: `messages.jsonl`, `subs/NN.txt` (расшифровки с таймкодами `[ЧЧ:ММ:СС]`), `summaries/NN.md` (конспекты уроков, писал Claude по расшифровкам).

> ⚠️ Папку `raw/` в git не кладите: в выгрузке чата бывают пароли, телефоны и личные файлы участников.
