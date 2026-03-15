import { NavLink } from 'react-router-dom';
import type { Status } from '../lib';

interface StatusLightProps {
  status: Status;
  label: string;
  to: string;
}

export default function StatusLight({ status, label, to }: StatusLightProps) {
  const color =
    status === 'ok'
      ? 'bg-green-500'
      : status === 'fail'
      ? 'bg-red-500'
      : status === 'warn'
      ? 'bg-yellow-500'
      : 'bg-yellow-500';
  return (
    <NavLink
      to={to}
      className="flex items-center gap-1 rounded-full border border-border px-2 py-1 text-xs text-purple-400 hover:text-purple-300 hover:bg-white/5"
      title={`${label}: ${status}`}
    >
      <span className={`h-2 w-2 rounded-full ${color}`}></span>
      <span>{label}</span>
    </NavLink>
  );
}
