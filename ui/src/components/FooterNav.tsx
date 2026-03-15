import { NavLink } from 'react-router-dom';

export default function FooterNav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 text-sm text-purple-400 hover:text-purple-300 ${isActive ? 'font-bold' : ''}`;

  return (
    <nav className="flex gap-2">
      <NavLink to="/ask" className={linkClass}>
        Ask
      </NavLink>
      <NavLink to="/chat" className={linkClass}>
        Chat
      </NavLink>
      <NavLink to="/search" className={linkClass}>
        Search
      </NavLink>
      <NavLink to="/index" className={linkClass}>
        Index
      </NavLink>
      <NavLink to="/ingest" className={linkClass}>
        Ingest
      </NavLink>
      <NavLink to="/unified-ingest" className={linkClass}>
        Unified
      </NavLink>
      <NavLink to="/workflows" className={linkClass}>
        Workflows
      </NavLink>
      <NavLink to="/logs" className={linkClass}>
        Log Events
      </NavLink>
      <NavLink to="/settings" className={linkClass}>
        Settings
      </NavLink>
    </nav>
  );
}
