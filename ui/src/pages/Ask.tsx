import { useEffect, useState } from 'react';
import AskPanel from '../components/AskPanel';
import ChatTranscript from '../components/ChatTranscript';
import HistorySidebar from '../components/HistorySidebar';
import ModeToggle from '../components/ModeToggle';
import { useAppStore } from '../lib';
import { useSettingsStore } from '../store/settings';
import type { LLMMode } from '../lib';

export default function Ask() {
  const [mode, setMode] = useState<LLMMode>('fast');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const { contractStatus } = useAppStore();
  const { compatibilityBanner } = useSettingsStore();

  const banners: Array<{ type: 'danger' | 'warn'; text: string }> = [];
  if (contractStatus === 'compat' && compatibilityBanner) {
    banners.push({
      type: 'warn',
      text: 'LLM API contract mismatch – compatibility mode',
    });
  }

  useEffect(() => {
    try {
      setShowAdvanced(
        localStorage.getItem(`ask:advanced:${mode}`) === '1'
      );
    } catch {
      setShowAdvanced(false);
    }
  }, [mode]);

  useEffect(() => {
    try {
      localStorage.setItem(
        `ask:advanced:${mode}`,
        showAdvanced ? '1' : '0'
      );
    } catch {
      /* ignore */
    }
  }, [showAdvanced, mode]);

  function toggleAdvanced() {
    setShowAdvanced((v) => !v);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <header className="space-y-4">
        <ModeToggle mode={mode} onChange={setMode} />
        <div className="space-y-2">
          {banners.map((b, i) => (
            <div
              key={i}
              className={`p-2 rounded text-sm ${
                b.type === 'danger'
                  ? 'bg-red-500/10 text-red-500'
                  : 'bg-amber-500/10 text-amber-600'
              }`}
            >
              {b.text}
            </div>
          ))}
        </div>
      </header>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          {mode === 'fast' ? (
            <AskPanel
              mode="fast"
              showAdvanced={showAdvanced}
              onToggleAdvanced={toggleAdvanced}
            />
          ) : (
            <ChatTranscript
              onModeChange={setMode}
              showAdvanced={showAdvanced}
              onToggleAdvanced={toggleAdvanced}
            />
          )}
        </div>
        <aside className="lg:col-span-4">
          <HistorySidebar mode={mode} />
        </aside>
      </div>
    </div>
  );
}

