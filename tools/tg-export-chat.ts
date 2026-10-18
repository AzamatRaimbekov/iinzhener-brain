// Полная выгрузка одного чата/группы владельца в JSONL (для сборки базы знаний, не для дайджеста).
// Пишет по строке на сообщение: текст, автор, дата, тема форума, все ссылки (из текста, скрытых
// text-url сущностей и web-превью), сведения о вложении. С --download качает документы-презентации
// (pdf/ppt/pptx/key/docx/xlsx) до 100 МБ в <out>/files. Сессия и apiHash не печатаются.
// Usage: pnpm exec tsx scripts/tg-export-chat.ts <chatId> <outDir> [--download]
import 'dotenv/config';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { TelegramClient, sessions, Api } from 'telegram';

const DOC_EXT = /\.(pdf|pptx?|key|docx?|xlsx?|ipynb|md|txt|zip)$/i;
const MAX_DOWNLOAD = 100 * 1024 * 1024;

interface Row {
  id: number;
  date: string;
  sender: string;
  topicId: number | null;
  replyTo: number | null;
  text: string;
  urls: string[];
  webpage?: { url: string; title?: string; siteName?: string; description?: string };
  media?: { kind: string; fileName?: string; mime?: string; size?: number; savedAs?: string; duration?: number };
}

function senderName(m: Api.Message): string {
  const s = m.sender as { firstName?: string; lastName?: string; title?: string; username?: string } | undefined;
  if (!s) return '';
  return [s.firstName, s.lastName].filter(Boolean).join(' ') || s.title || s.username || '';
}

function extractUrls(m: Api.Message): string[] {
  const out = new Set<string>();
  const text = m.message ?? '';
  for (const e of m.entities ?? []) {
    if (e instanceof Api.MessageEntityTextUrl) out.add(e.url);
    else if (e instanceof Api.MessageEntityUrl) out.add(text.slice(e.offset, e.offset + e.length));
  }
  // Fallback for URLs Telegram didn't mark as entities.
  for (const u of text.match(/https?:\/\/[^\s)\]>"']+/g) ?? []) out.add(u);
  // Inline-кнопки под постом часто несут ссылку на видео/слайды.
  const rm = m.replyMarkup;
  if (rm instanceof Api.ReplyInlineMarkup) {
    for (const row of rm.rows) for (const b of row.buttons) if (b instanceof Api.KeyboardButtonUrl) out.add(b.url);
  }
  return [...out];
}

async function main(): Promise<void> {
  const [chatId, outArg] = process.argv.slice(2);
  const download = process.argv.includes('--download');
  if (!chatId || !outArg) throw new Error('usage: tg-export-chat.ts <chatId> <outDir> [--download]');
  const outDir = resolve(outArg);
  const filesDir = join(outDir, 'files');
  mkdirSync(filesDir, { recursive: true });

  const session = new sessions.StringSession(
    readFileSync(resolve(process.env.TELEGRAM_SESSION_FILE ?? 'data/secrets/telegram.session'), 'utf8').trim(),
  );
  const client = new TelegramClient(session, Number(process.env.TELEGRAM_API_ID), process.env.TELEGRAM_API_HASH ?? '', { connectionRetries: 5 });
  client.setLogLevel('error' as never);
  await client.connect();

  // getDialogs warms the entity cache so a bare numeric id resolves.
  await client.getDialogs({ limit: 2000 });
  const entity = await client.getEntity(chatId);

  // Forum topics (если группа — форум): id → название, чтобы раскладывать по модулям курса.
  const topics: Record<number, string> = {};
  try {
    const res = (await client.invoke(
      new Api.channels.GetForumTopics({ channel: entity as Api.TypeInputChannel, limit: 100 }),
    )) as Api.messages.ForumTopics;
    for (const t of res.topics) if (t instanceof Api.ForumTopic) topics[t.id] = t.title;
  } catch {
    /* not a forum */
  }

  const rows: Row[] = [];
  let n = 0;
  for await (const m of client.iterMessages(entity, { reverse: true })) {
    if (!(m instanceof Api.Message)) continue;
    const rt = m.replyTo as Api.MessageReplyHeader | undefined;
    const topicId = rt?.forumTopic ? (rt.replyToTopId ?? rt.replyToMsgId ?? null) : null;
    const row: Row = {
      id: m.id,
      date: new Date(m.date * 1000).toISOString(),
      sender: senderName(m),
      topicId: topicId ?? null,
      replyTo: rt?.replyToMsgId ?? null,
      text: m.message ?? '',
      urls: extractUrls(m),
    };
    const media = m.media;
    if (media instanceof Api.MessageMediaWebPage && media.webpage instanceof Api.WebPage) {
      const w = media.webpage;
      row.webpage = { url: w.url, title: w.title, siteName: w.siteName, description: w.description };
      if (!row.urls.includes(w.url)) row.urls.push(w.url);
    } else if (media instanceof Api.MessageMediaDocument && media.document instanceof Api.Document) {
      const d = media.document;
      const nameAttr = d.attributes.find((a) => a instanceof Api.DocumentAttributeFilename) as Api.DocumentAttributeFilename | undefined;
      const videoAttr = d.attributes.find((a) => a instanceof Api.DocumentAttributeVideo) as Api.DocumentAttributeVideo | undefined;
      const size = Number(d.size);
      row.media = {
        kind: videoAttr ? 'video' : d.mimeType.startsWith('audio') ? 'audio' : 'document',
        fileName: nameAttr?.fileName,
        mime: d.mimeType,
        size,
        duration: videoAttr?.duration,
      };
      if (download && nameAttr && DOC_EXT.test(nameAttr.fileName) && size <= MAX_DOWNLOAD) {
        const safe = `${m.id}_${nameAttr.fileName.replace(/[\\/:*?"<>|]/g, '_')}`;
        const target = join(filesDir, safe);
        if (!existsSync(target)) {
          const buf = (await client.downloadMedia(m, {})) as Buffer | undefined;
          if (buf) writeFileSync(target, buf);
        }
        row.media.savedAs = `files/${safe}`;
      }
    } else if (media instanceof Api.MessageMediaPhoto) {
      row.media = { kind: 'photo' };
    } else if (media) {
      row.media = { kind: media.className };
    }
    rows.push(row);
    if (++n % 500 === 0) console.log(`…${n} сообщений`);
  }

  writeFileSync(join(outDir, 'messages.jsonl'), rows.map((r) => JSON.stringify(r)).join('\n'), 'utf8');
  writeFileSync(join(outDir, 'topics.json'), JSON.stringify(topics, null, 2), 'utf8');
  const title = (entity as { title?: string }).title ?? chatId;
  console.log(`✅ ${title}: ${rows.length} сообщений, тем: ${Object.keys(topics).length}, со ссылками: ${rows.filter((r) => r.urls.length).length}`);
  await client.disconnect();
}

void main()
  .catch((err: unknown) => {
    console.error('tg-export-chat error:', err instanceof Error ? err.message : err);
    process.exitCode = 1;
  })
  .finally(() => process.exit(process.exitCode ?? 0));
