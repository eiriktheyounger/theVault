import { useNavigate, useLocation } from 'react-router-dom';

export default function TheVaultHeader() {
  const navigate = useNavigate();
  const location = useLocation();

  // Don't show header on home page since it has its own hero
  if (location.pathname === '/') {
    return null;
  }

  return (
    <div className="w-full sticky top-0 z-30 border-b border-border bg-panel/90 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <span className="text-3xl">🗄️</span>
          <span className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-purple-400 via-purple-500 to-purple-600 bg-clip-text text-transparent">
            The Vault
          </span>
        </button>
      </div>
    </div>
  );
}
