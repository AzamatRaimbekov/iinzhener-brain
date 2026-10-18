// Ищет диалоги владельца по подстроке в названии (печатает id, тип, название, кол-во участников).
// Usage: pnpm exec tsx scripts/tg-find-chat.ts "инженер"
import 'dotenv/config';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { TelegramClient, sessions } from 'telegram';

async function main(): Promise<void> {
  const q = (process.argv[2] ?? '').toLowerCase();
  const session = new sessions.StringSession(
    readFileSync(resolve(process.env.TELEGRAM_SESSION_FILE ?? 'data/secrets/telegram.session'), 'utf8').trim(),
  );
  const client = new TelegramClient(session, Number(process.env.TELEGRAM_API_ID), process.env.TELEGRAM_API_HASH ?? '', { connectionRetries: 3 });
  client.setLogLevel('error' as never);
  await client.connect();
  const dialogs = await client.getDialogs({ limit: 2000 });
  for (const d of dialogs) {
    const title = d.title ?? '';
    if (title.toLowerCase().includes(q)) {
      const kind = d.isUser ? 'user' : d.isGroup ? 'group' : d.isChannel ? 'channel' : '?';
      console.log(`${d.id?.toString()}\t${kind}\t${title}`);
    }
  }
  await client.disconnect();
}

void main()
  .catch((err: unknown) => {
    console.error('tg-find-chat error:', err instanceof Error ? err.message : err);
    process.exitCode = 1;
  })
  .finally(() => process.exit(process.exitCode ?? 0));
