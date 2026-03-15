import { useEffect } from 'react';
import { Routes, Route, BrowserRouter } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import TheVaultHeader from './components/TheVaultHeader';
import FooterStatusPills from './components/FooterStatusPills';
import Home from './pages/Home';
import Ask from './pages/Ask';
import Index from './pages/Index';
import Ingest from './pages/Ingest';
import Logs from './pages/Logs';
import Settings from './pages/Settings';
import Workflows from './pages/Workflows';
import Services from './pages/Services';
import Search from './pages/Search';
import Chat from './pages/Chat';
import { verifyContract, useAppStore } from './lib';

export default function App() {
  const { setContract } = useAppStore();

  useEffect(() => {
    document.title = 'The Vault';
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const status = await verifyContract();
        setContract(status);
      } catch {
        setContract('unknown');
      }
    })();
  }, [setContract]);

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />

        <div className="flex-1 flex flex-col overflow-hidden">
          <TheVaultHeader />

          <main className="flex-1 overflow-y-auto bg-bg">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/search" element={<Search />} />
              <Route path="/services" element={<Services />} />
              <Route path="/workflows" element={<Workflows />} />
              <Route path="/ingest" element={<Ingest />} />
              <Route path="/index" element={<Index />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/settings" element={<Settings />} />
              {/* Legacy routes */}
              <Route path="/ask" element={<Ask />} />
            </Routes>
          </main>

          <footer className="border-t border-border bg-panel/90 backdrop-blur">
            <div className="mx-auto flex max-w-7xl items-center justify-end px-4 sm:px-6 lg:px-8 py-2">
              <FooterStatusPills />
            </div>
          </footer>
        </div>
      </div>
    </BrowserRouter>
  );
}
