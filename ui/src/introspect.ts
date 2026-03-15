export type ActionHint = { selector: string; name: string; action?: string };

function escapeRegExp(s:string){return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}
function slugify(s:string){return s.toLowerCase().trim().replace(/\s+/g,'-').replace(/[^a-z0-9-_]/g,'').slice(0,60);}

export function getActionHints(): ActionHint[] {
  const nodes = Array.from(document.querySelectorAll('[data-test^="btn:"]'));
  return nodes.map((el: Element) => {
    const nameAttr = (el.getAttribute('data-test') || '');
    const name = nameAttr.startsWith('btn:') ? nameAttr.slice(4) : slugify((el.textContent||'').trim()||'control');
    const action = el.getAttribute('data-action') || undefined;
    const text = (el.textContent || '').trim();
    const role = (el as HTMLElement).getAttribute('role');
    const selector = role && text
      ? `getByRole('${role}', { name: /${escapeRegExp(text.slice(0,60))}/i })`
      : `locator('[data-test="btn:${name}"]')`;
    return { selector, name, action };
  });
}

export function autoTagButtonsForLocal() {
/* eslint-disable @typescript-eslint/no-explicit-any */
  const isLocal =
    (typeof window !== 'undefined' && (import.meta as any)?.env?.DEV) ||
    location.hostname === 'localhost';
/* eslint-enable @typescript-eslint/no-explicit-any */
  if (!isLocal) return;
  const candidates = Array.from(document.querySelectorAll('button, [role="button"]')) as HTMLElement[];
  for (const el of candidates) {
    if (el.getAttribute('data-test')) continue;
    const text = (el.textContent || '').trim();
    if (!text) continue;
    el.setAttribute('data-test', `btn:${slugify(text)}`);
  }
}

