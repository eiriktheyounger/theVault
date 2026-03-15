import { RAG_BASE } from '../lib/config';
import { toast } from 'sonner';

export async function persistChatSession(
  mode: 'Fast' | 'Deep',
  cid: string,
  items: Array<Record<string, unknown>>
): Promise<{ path: string; ok: boolean; error?: string }> {
  const now = new Date();
  const yyyy = now.getUTCFullYear();
  const mm = String(now.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(now.getUTCDate()).padStart(2, '0');
  const hh = String(now.getUTCHours()).padStart(2, '0');
  const mi = String(now.getUTCMinutes()).padStart(2, '0');
  const ss = String(now.getUTCSeconds()).padStart(2, '0');
  const stamp = `${yyyy}${mm}${dd}_${hh}${mi}${ss}`;
  const file = `${stamp}_${cid}.jsonl`;
  const path = `ops/Chats/${mode}/${yyyy}/${mm}/${file}`;
  const content = items.map((i) => JSON.stringify(i)).join('\n') + '\n';
  const url = `${RAG_BASE}/vault/write`;
  const attempt = async (): Promise<Response | null> => {
    try {
      return await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content }),
      });
    } catch {
      return null;
    }
  };
  const res = await attempt();
  if (!res || !res.ok) {
    const status = res ? res.status : 0;
    const msg = `${url} → ${status}`;
    toast.error('Persist failed', {
      description: msg,
      action: {
        label: 'Retry last payload',
        onClick: () => persistChatSession(mode, cid, items),
      },
    });
    return { path, ok: false, error: msg };
  }
  toast.success('Saved', { duration: 1200 });
  return { path, ok: true };
}
