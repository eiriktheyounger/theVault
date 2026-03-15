import type { LLMMode } from '../lib';

interface ModeToggleProps {
  mode: LLMMode;
  onChange: (mode: LLMMode) => void;
}

export default function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="inline-flex rounded-full border border-purple-400 p-1">
      <button
        onClick={() => onChange('fast')}
        className={`px-4 py-1.5 rounded-full text-sm ${
          mode === 'fast'
            ? 'bg-purple-400 text-black'
            : 'text-purple-400 hover:text-purple-300'
        }`}
      >
        Fast
      </button>
      <button
        onClick={() => onChange('deep')}
        className={`px-4 py-1.5 rounded-full text-sm ${
          mode === 'deep'
            ? 'bg-purple-400 text-black'
            : 'text-purple-400 hover:text-purple-300'
        }`}
      >
        Deep
      </button>
    </div>
  );
}
