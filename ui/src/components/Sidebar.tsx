import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Home,
  MessageSquare,
  Server,
  Workflow,
  FolderInput,
  BarChart3,
  FileText,
  Settings,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  badge?: () => string | number | null;
}

interface SidebarProps {
  className?: string;
}

export default function Sidebar({ className = '' }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const location = useLocation();

  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) setIsOpen(false); // Close sidebar on mobile by default
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close sidebar on mobile when route changes
  useEffect(() => {
    if (isMobile) {
      setIsOpen(false);
    }
  }, [location.pathname, isMobile]);

  const navItems: NavItem[] = [
    {
      to: '/',
      icon: <Home className="w-5 h-5" />,
      label: 'Home',
    },
    {
      to: '/chat',
      icon: <MessageSquare className="w-5 h-5" />,
      label: 'Chat',
    },
    {
      to: '/services',
      icon: <Server className="w-5 h-5" />,
      label: 'Services',
    },
    {
      to: '/workflows',
      icon: <Workflow className="w-5 h-5" />,
      label: 'Workflows',
    },
    {
      to: '/ingest',
      icon: <FolderInput className="w-5 h-5" />,
      label: 'Ingest',
    },
    {
      to: '/index',
      icon: <BarChart3 className="w-5 h-5" />,
      label: 'RAG Index',
    },
    {
      to: '/logs',
      icon: <FileText className="w-5 h-5" />,
      label: 'Logs',
    },
    {
      to: '/settings',
      icon: <Settings className="w-5 h-5" />,
      label: 'Settings',
    },
  ];

  const linkClass = (isActive: boolean) =>
    `flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
      isActive
        ? 'bg-purple-500/20 text-purple-400 font-semibold'
        : 'text-muted hover:bg-panel2 hover:text-text'
    }`;

  return (
    <>
      {/* Mobile Overlay */}
      {isMobile && isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full
          bg-panel border-r border-border
          transition-all duration-300 ease-in-out
          z-50
          ${isOpen ? (isMobile ? 'w-64' : 'w-64') : 'w-0 md:w-16'}
          ${!isOpen && 'overflow-hidden'}
          ${className}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border h-16">
            {isOpen && (
              <div className="flex items-center gap-2">
                <span className="text-2xl">🗄️</span>
                <span className="font-bold text-lg bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">
                  The Vault
                </span>
              </div>
            )}
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-1 rounded-md hover:bg-panel2 transition-colors ml-auto"
              aria-label={isOpen ? 'Close sidebar' : 'Open sidebar'}
            >
              {isOpen ? (
                <ChevronLeft className="w-5 h-5" />
              ) : (
                <ChevronRight className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-3 space-y-1">
            {navItems.map((item) => {
              const isActive = item.to === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.to);

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={() => linkClass(isActive)}
                  title={!isOpen ? item.label : undefined}
                >
                  <span className="flex-shrink-0">{item.icon}</span>
                  {isOpen && (
                    <>
                      <span className="flex-1">{item.label}</span>
                      {item.badge && item.badge() && (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-panel2 border border-border">
                          {item.badge()}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="border-t border-border p-4">
            {isOpen ? (
              <div className="text-xs text-muted space-y-1">
                <div className="font-semibold text-text">theVault</div>
                <div>v1.5.1</div>
              </div>
            ) : (
              <div className="text-xs text-muted text-center">v1.5</div>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile Menu Button */}
      {isMobile && !isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed top-4 left-4 z-40 p-2 rounded-lg bg-panel border border-border hover:bg-panel2 transition-colors"
          aria-label="Open menu"
        >
          <Menu className="w-6 h-6" />
        </button>
      )}

      {/* Spacer for desktop layout */}
      {!isMobile && (
        <div
          className={`transition-all duration-300 ${isOpen ? 'w-64' : 'w-16'}`}
        />
      )}
    </>
  );
}
