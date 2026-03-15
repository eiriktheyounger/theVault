import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import {
  Server,
  Play,
  Square,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';
import {
  getServicesStatus,
  startServices,
  stopServices,
  killServices,
  getCurrentProfile,
  listProfiles,
  setProfile,
  type ServicesStatusResponse,
  type SystemProfile,
  type CurrentProfileResponse,
} from '../lib/api';

export default function Services() {
  const [servicesStatus, setServicesStatus] = useState<ServicesStatusResponse | null>(null);
  const [serviceActionLog, setServiceActionLog] = useState<string>('');
  const [serviceActionRunning, setServiceActionRunning] = useState<boolean>(false);
  const [currentProfile, setCurrentProfile] = useState<CurrentProfileResponse | null>(null);
  const [availableProfiles, setAvailableProfiles] = useState<SystemProfile[]>([]);
  const [profileChanging, setProfileChanging] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Load system profile on mount
  useEffect(() => {
    const loadSystemProfile = async () => {
      try {
        const [profileResult, profilesResult] = await Promise.all([
          getCurrentProfile(),
          listProfiles(),
        ]);
        setCurrentProfile(profileResult);
        setAvailableProfiles(profilesResult.profiles);
      } catch (err) {
        console.error('Failed to load system profile:', err);
        toast.error('Failed to load system profile');
      }
    };

    loadSystemProfile();
  }, []);

  // Load services status
  const loadServicesStatus = async () => {
    try {
      const status = await getServicesStatus();
      setServicesStatus(status);
    } catch (err) {
      console.error('Failed to get services status:', err);
    }
  };

  useEffect(() => {
    loadServicesStatus();

    if (!autoRefresh) return;

    const interval = setInterval(loadServicesStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleGetServicesStatus = async () => {
    try {
      const status = await getServicesStatus();
      setServicesStatus(status);
      toast.success('Service status updated');
    } catch (err) {
      const msg = (err as Error).message;
      toast.error(`Failed to get status: ${msg}`);
    }
  };

  const handleStartServices = async () => {
    setServiceActionRunning(true);
    setServiceActionLog('Starting services...\n');
    try {
      const result = await startServices();
      setServiceActionLog(`${result.message}\n\n${result.output}`);
      setServicesStatus({
        services: result.services,
        all_running: result.services.every(s => s.running),
        all_stopped: result.services.every(s => !s.running),
      });
      if (result.success) {
        toast.success('Services started successfully');
      } else {
        toast.warning('Some services failed to start');
      }
    } catch (err) {
      const msg = (err as Error).message;
      setServiceActionLog(`Error: ${msg}`);
      toast.error(`Failed to start services: ${msg}`);
    } finally {
      setServiceActionRunning(false);
    }
  };

  const handleStopServices = async () => {
    setServiceActionRunning(true);
    setServiceActionLog('Stopping services...\n');
    try {
      const result = await stopServices();
      setServiceActionLog(`${result.message}\n\n${result.output}`);
      setServicesStatus({
        services: result.services,
        all_running: result.services.every(s => s.running),
        all_stopped: result.services.every(s => !s.running),
      });
      if (result.success) {
        toast.success('Services stopped successfully');
      } else {
        toast.warning('Some services still running');
      }
    } catch (err) {
      const msg = (err as Error).message;
      setServiceActionLog(`Error: ${msg}`);
      toast.error(`Failed to stop services: ${msg}`);
    } finally {
      setServiceActionRunning(false);
    }
  };

  const handleKillServices = async () => {
    if (!confirm('Force kill all services? This should only be used if graceful shutdown fails.')) {
      return;
    }
    setServiceActionRunning(true);
    setServiceActionLog('Force killing services...\n');
    try {
      const result = await killServices();
      setServiceActionLog(`${result.message}\n\n${result.output}`);
      setServicesStatus({
        services: result.services,
        all_running: result.services.every(s => s.running),
        all_stopped: result.services.every(s => !s.running),
      });
      if (result.success) {
        toast.success('All services killed');
      } else {
        toast.error('Some services may still be running');
      }
    } catch (err) {
      const msg = (err as Error).message;
      setServiceActionLog(`Error: ${msg}`);
      toast.error(`Failed to kill services: ${msg}`);
    } finally {
      setServiceActionRunning(false);
    }
  };

  const handleProfileChange = async (profileId: string) => {
    setProfileChanging(true);
    try {
      const result = await setProfile(profileId);
      setCurrentProfile(prev => ({
        ...prev!,
        current_profile: result.profile_id,
        config: result.config,
      }));
      toast.success(result.message);
    } catch (err) {
      const msg = (err as Error).message;
      toast.error(`Failed to change profile: ${msg}`);
    } finally {
      setProfileChanging(false);
    }
  };

  const serviceGroups = [
    {
      name: 'Core Services',
      services: ['Ollama', 'LLM Server', 'RAG Server'],
    },
    {
      name: 'Frontend Services',
      services: ['Main UI', 'Stream Diagnostics UI'],
    },
    {
      name: 'Backend Services',
      services: ['Stream Diagnostics API'],
    },
  ];

  const getServiceIcon = (running: boolean) => {
    if (running) return <CheckCircle className="w-5 h-5 text-green-500" />;
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const getServiceDot = (running: boolean) => {
    if (running) return <span className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />;
    return <span className="w-3 h-3 rounded-full bg-red-500" />;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Server className="w-8 h-8 text-purple-400" />
            Service Management
          </h1>
          <p className="text-muted mt-2">Control and monitor all theVault system services</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh
          </label>
          <button
            className="btn-outline flex items-center gap-2"
            onClick={handleGetServicesStatus}
            disabled={serviceActionRunning}
          >
            <RefreshCw className={`w-4 h-4 ${serviceActionRunning ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* System Profile Selector */}
      {currentProfile && availableProfiles.length > 0 && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold">System Profile</h2>
              <p className="text-sm text-muted mt-1">
                {currentProfile.hostname} • Current: {currentProfile.current_profile || 'Base Config'}
              </p>
            </div>
            <div className="text-sm text-muted">
              Calendar: {(currentProfile.config.calendars as { source?: string })?.source || 'Not set'} → {(currentProfile.config.calendars as { target?: string })?.target || 'Not set'}
            </div>
          </div>
          <div className="flex gap-3">
            {availableProfiles.map((profile) => (
              <button
                key={profile.id}
                onClick={() => handleProfileChange(profile.id)}
                disabled={profileChanging || currentProfile.current_profile === profile.id}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  currentProfile.current_profile === profile.id
                    ? 'bg-purple-500 text-white'
                    : 'bg-panel2 text-text border border-border hover:bg-panel3'
                } ${profileChanging || currentProfile.current_profile === profile.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                title={profile.description}
              >
                {currentProfile.current_profile === profile.id && '✓ '}
                {profile.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="card p-6">
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            className={`btn-primary flex items-center gap-2 ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleStartServices}
            disabled={serviceActionRunning}
          >
            <Play className="w-4 h-4" />
            {serviceActionRunning ? 'Working...' : 'Start All Services'}
          </button>

          <button
            className={`btn-outline flex items-center gap-2 ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleStopServices}
            disabled={serviceActionRunning}
          >
            <Square className="w-4 h-4" />
            Stop All Services
          </button>

          <button
            className={`btn-outline flex items-center gap-2 text-red-500 hover:bg-red-500/10 border-red-500/30 ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleKillServices}
            disabled={serviceActionRunning}
          >
            <AlertTriangle className="w-4 h-4" />
            Force Kill
          </button>

          <button
            className="btn-outline flex items-center gap-2 ml-auto"
            onClick={() => window.open('http://localhost:5173', '_blank')}
          >
            <ExternalLink className="w-4 h-4" />
            Open Vault
          </button>

          <button
            className="btn-outline flex items-center gap-2"
            onClick={() => window.open('http://localhost:5181', '_blank')}
          >
            <ExternalLink className="w-4 h-4" />
            Stream Diagnostics
          </button>
        </div>
      </div>

      {/* Service Status */}
      {servicesStatus && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">Service Status</h2>
            <div className="flex items-center gap-2 text-sm">
              {servicesStatus.all_running && (
                <span className="flex items-center gap-2 text-green-500">
                  <CheckCircle className="w-4 h-4" />
                  All services running
                </span>
              )}
              {servicesStatus.all_stopped && (
                <span className="flex items-center gap-2 text-red-500">
                  <XCircle className="w-4 h-4" />
                  All services stopped
                </span>
              )}
              {!servicesStatus.all_running && !servicesStatus.all_stopped && (
                <span className="flex items-center gap-2 text-amber-500">
                  <AlertTriangle className="w-4 h-4" />
                  Some services offline
                </span>
              )}
            </div>
          </div>

          <div className="space-y-6">
            {serviceGroups.map((group) => (
              <div key={group.name}>
                <h3 className="text-sm font-semibold text-muted mb-3">{group.name}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {servicesStatus.services
                    .filter(service => group.services.includes(service.name))
                    .map((service) => (
                      <div
                        key={service.name}
                        className={`border rounded-lg p-4 ${
                          service.running
                            ? 'bg-green-500/5 border-green-500/30'
                            : 'bg-red-500/5 border-red-500/30'
                        }`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            {getServiceDot(service.running)}
                            <h4 className="font-semibold">{service.name}</h4>
                          </div>
                          {getServiceIcon(service.running)}
                        </div>
                        <p className="text-sm text-muted">{service.details}</p>
                        {service.pid && (
                          <p className="text-xs text-muted mt-2">PID: {service.pid}</p>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Log */}
      {serviceActionLog && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Action Log</h2>
            <button
              className="btn-outline text-sm"
              onClick={() => setServiceActionLog('')}
            >
              ✕ Clear
            </button>
          </div>
          <div className="bg-panel2 border border-border rounded-lg p-4 max-h-96 overflow-y-auto">
            <pre className="text-sm font-mono whitespace-pre-wrap">{serviceActionLog}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
