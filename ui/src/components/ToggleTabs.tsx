export interface ToggleTab<T extends string> {
  value: T;
  label: string;
}

export default function ToggleTabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: ToggleTab<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex gap-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-lg px-3 py-1.5 text-sm ${
            opt.value === value
              ? 'bg-panel2 text-text'
              : 'text-muted hover:text-text'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
