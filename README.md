# 🧠 ИИнженер 1.0: второй мозг курса

База знаний курса по вайбкодингу с Claude «ИИнженер 1.0»: 14 уроков, конспекты всех записей с таймкодами, презентации, промпты, инструменты, роадмап, чеклисты и план «что дальше».

## 🌐 Смотреть в браузере
**https://azamatraimbekov.github.io/iinzhener-brain/** — меню, поиск по всем урокам и расшифровкам, кнопки «▶ Смотреть», галочки с прогрессом.

## 🚀 С чего начать
- [00-Начни-здесь.md](00-Начни-здесь.md): оглавление
- [01-Роадмап.md](01-Роадмап.md): путь от нуля до своего ИИ-продукта
- [02-Чеклист.md](02-Чеклист.md): проверка навыков
- [03-Что-дальше.md](03-Что-дальше.md): план на 30 дней после курса

## 🧩 Установить в Claude Code как плагин или скилл

**Плагин** (база курса и 2 скилла, обновляется командой `/plugin update`):
```
/plugin install iinzhener-brain --marketplace AzamatRaimbekov/iinzhener-brain
```
На старых версиях Claude Code ставится в два шага:
```
/plugin marketplace add AzamatRaimbekov/iinzhener-brain
/plugin install iinzhener-brain@iinzhener
```

**Только скиллы** (база скачается в `~/iinzhener-brain` при первом вопросе):
```bash
npx skills add AzamatRaimbekov/iinzhener-brain --skill iinzhener --skill iinzhener-progress -a claude-code -g -y
```

Что внутри:
- **`iinzhener`**: отвечает на вопросы по курсу («в каком уроке про деплой?», «дай промпт для Expo», «где в видео про Superpowers?»), всегда со ссылкой на урок и таймкод.
- **`iinzhener-progress`**: смотрит ваш проект, сверяет с чеклистом курса и говорит, что уже сделано, чего не хватает и какой урок смотреть следующим.

Спрашивайте обычным текстом: скилл включится сам. Можно вызвать и командой: `/iinzhener-brain:iinzhener` и `/iinzhener-brain:iinzhener-progress`, если стоит плагин, или `/iinzhener` и `/iinzhener-progress`, если ставили только скиллы.

## 🤖 Подключить к своему ИИ как папку
```bash
git clone https://github.com/AzamatRaimbekov/iinzhener-brain.git
```
- **Claude Code / Claude Desktop (Cowork):** откройте папку как проект и спрашивайте: «где в уроках про деплой?», «составь мне план на неделю». Claude сам прочитает `CLAUDE.md`.
- **Obsidian:** File → Open folder as vault.
- **NotebookLM / Claude Projects:** загрузите `.md`-файлы как источники.

Не умеете пользоваться git? Нажмите **Code → Download ZIP** и распакуйте.
