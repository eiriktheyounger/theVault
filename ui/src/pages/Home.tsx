import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  PlayCircle,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowRight,
  Sparkles,
  Moon,
  Server,
  FolderInput,
  MessageSquare,
  BarChart3,
} from 'lucide-react';
import { getServicesStatus, startWorkflow, listWorkflows, getInboxInfo, type ServicesStatusResponse } from '../lib/api';

interface ProcessStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'complete' | 'error';
  action?: () => void;
  link?: string;
  icon: React.ReactNode;
  estimatedTime?: string;
}

interface QuickAccessCard {
  title: string;
  description: string;
  icon: React.ReactNode;
  link: string;
  badge?: string;
  color: string;
}

export default function Home() {
  const navigate = useNavigate();
  const [servicesStatus, setServicesStatus] = useState<ServicesStatusResponse | null>(null);
  const [morningWorkflowStatus, setMorningWorkflowStatus] = useState<'not_started' | 'running' | 'complete'>('not_started');
  const [eveningWorkflowStatus, setEveningWorkflowStatus] = useState<'not_started' | 'running' | 'complete'>('not_started');
  const [inboxCounts, setInboxCounts] = useState<Record<string, number>>({});
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update time every minute
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  // Load services status
  useEffect(() => {
    const loadStatus = async () => {
      try {
        const status = await getServicesStatus();
        setServicesStatus(status);
      } catch (error) {
        console.error('Failed to load services status:', error);
      }
    };

    loadStatus();
    const interval = setInterval(loadStatus, 10000); // Poll every 10 seconds
    return () => clearInterval(interval);
  }, []);

  // Load workflow status
  useEffect(() => {
    const loadWorkflows = async () => {
      try {
        const result = await listWorkflows();
        if (result.ok && result.jobs.length > 0) {
          const morningJobs = result.jobs.filter(j => j.workflow_type === 'morning');
          const eveningJobs = result.jobs.filter(j => j.workflow_type === 'evening');

          if (morningJobs.length > 0) {
            const latest = morningJobs[0];
            if (latest.status === 'running') setMorningWorkflowStatus('running');
            else if (latest.status === 'complete') setMorningWorkflowStatus('complete');
          }

          if (eveningJobs.length > 0) {
            const latest = eveningJobs[0];
            if (latest.status === 'running') setEveningWorkflowStatus('running');
            else if (latest.status === 'complete') setEveningWorkflowStatus('complete');
          }
        }
      } catch (error) {
        console.error('Failed to load workflows:', error);
      }
    };

    loadWorkflows();
    const interval = setInterval(loadWorkflows, 15000);
    return () => clearInterval(interval);
  }, []);

  // Load inbox counts
  useEffect(() => {
    const loadInbox = async () => {
      try {
        const info = await getInboxInfo();
        if (info.ok) {
          setInboxCounts(info.counts || {});
        }
      } catch (error) {
        console.error('Failed to load inbox info:', error);
      }
    };

    loadInbox();
    const interval = setInterval(loadInbox, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleStartMorningWorkflow = async () => {
    try {
      setMorningWorkflowStatus('running');
      const result = await startWorkflow({
        workflow_type: 'morning',
        date: new Date().toISOString().split('T')[0],
      });

      if (result.ok) {
        toast.success('Morning workflow started!');
        navigate('/workflows');
      } else {
        toast.error(`Failed to start workflow: ${result.error}`);
        setMorningWorkflowStatus('not_started');
      }
    } catch (error) {
      toast.error('Failed to start morning workflow');
      setMorningWorkflowStatus('not_started');
    }
  };

  const handleStartEveningWorkflow = async () => {
    try {
      setEveningWorkflowStatus('running');
      const result = await startWorkflow({
        workflow_type: 'evening',
        date: new Date().toISOString().split('T')[0],
      });

      if (result.ok) {
        toast.success('Evening workflow started!');
        navigate('/workflows');
      } else {
        toast.error(`Failed to start workflow: ${result.error}`);
        setEveningWorkflowStatus('not_started');
      }
    } catch (error) {
      toast.error('Failed to start evening workflow');
      setEveningWorkflowStatus('not_started');
    }
  };

  const allServicesRunning = servicesStatus?.all_running ?? false;
  const servicesReady = servicesStatus ? !servicesStatus.all_stopped : false;

  const morningSteps: ProcessStep[] = [
    {
      id: 'services',
      title: 'Start Services',
      description: allServicesRunning ? 'All 6 services running' : 'Start Ollama, LLM, RAG, UI servers',
      status: allServicesRunning ? 'complete' : servicesReady ? 'in_progress' : 'pending',
      link: '/services',
      icon: <Server className="w-5 h-5" />,
      estimatedTime: '30s',
    },
    {
      id: 'morning',
      title: 'Run Morning Workflow',
      description: 'Calendar sync, daily dashboard, ingest, organize, TOCs',
      status: morningWorkflowStatus === 'complete' ? 'complete' : morningWorkflowStatus === 'running' ? 'in_progress' : 'pending',
      action: handleStartMorningWorkflow,
      link: '/workflows',
      icon: <Sparkles className="w-5 h-5" />,
      estimatedTime: '10-15s',
    },
    {
      id: 'review',
      title: 'Review Results',
      description: 'Check dashboard, processed files, and TOC updates',
      status: morningWorkflowStatus === 'complete' ? 'complete' : 'pending',
      link: '/workflows',
      icon: <CheckCircle2 className="w-5 h-5" />,
      estimatedTime: '2-3min',
    },
  ];

  const eveningSteps: ProcessStep[] = [
    {
      id: 'review',
      title: 'Generate Day Review',
      description: 'Summarize today\'s work and accomplishments',
      status: eveningWorkflowStatus === 'complete' ? 'complete' : eveningWorkflowStatus === 'running' ? 'in_progress' : 'pending',
      action: handleStartEveningWorkflow,
      link: '/workflows',
      icon: <Moon className="w-5 h-5" />,
      estimatedTime: '30s',
    },
  ];

  const quickAccessCards: QuickAccessCard[] = [
    {
      title: 'Chat with Vault',
      description: 'Fast & Deep AI chat with your knowledge base',
      icon: <MessageSquare className="w-6 h-6" />,
      link: '/chat',
      color: 'from-purple-500 to-purple-600',
    },
    {
      title: 'Services',
      description: `${servicesStatus?.services.filter(s => s.running).length || 0}/6 services running`,
      icon: <Server className="w-6 h-6" />,
      link: '/services',
      badge: allServicesRunning ? '✓' : '!',
      color: allServicesRunning ? 'from-green-500 to-green-600' : 'from-amber-500 to-amber-600',
    },
    {
      title: 'Inbox',
      description: `${inboxCounts.total || 0} files waiting to process`,
      icon: <FolderInput className="w-6 h-6" />,
      link: '/ingest',
      badge: inboxCounts.total > 0 ? String(inboxCounts.total) : undefined,
      color: 'from-blue-500 to-blue-600',
    },
    {
      title: 'RAG Index',
      description: 'Manage your knowledge base index',
      icon: <BarChart3 className="w-6 h-6" />,
      link: '/index',
      color: 'from-indigo-500 to-indigo-600',
    },
  ];

  const getStepStatus = (step: ProcessStep) => {
    switch (step.status) {
      case 'complete':
        return { icon: <CheckCircle2 className="w-6 h-6 text-green-500" />, bg: 'bg-green-500/10', border: 'border-green-500/30' };
      case 'in_progress':
        return { icon: <Clock className="w-6 h-6 text-blue-500 animate-pulse" />, bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
      case 'error':
        return { icon: <AlertCircle className="w-6 h-6 text-red-500" />, bg: 'bg-red-500/10', border: 'border-red-500/30' };
      default:
        return { icon: <PlayCircle className="w-6 h-6 text-muted" />, bg: 'bg-panel2', border: 'border-border' };
    }
  };

  const isEvening = currentTime.getHours() >= 17; // After 5 PM

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Hero Section */}
      <div className="text-center space-y-4 py-8">
        <h1 className="text-5xl md:text-6xl font-bold bg-gradient-to-r from-purple-400 via-purple-500 to-purple-600 bg-clip-text text-transparent">
          🗄️ The Vault
        </h1>
        <p className="text-xl text-muted max-w-2xl mx-auto">
          Your AI-Powered Knowledge Management System
        </p>
        <div className="flex items-center justify-center gap-4 text-sm text-muted">
          <span>{currentTime.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</span>
          <span>•</span>
          <span>{currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>

      {/* Morning Process */}
      <div className="card p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-purple-400" />
              Morning Process
            </h2>
            <p className="text-muted mt-1">Start your day with automated vault management</p>
          </div>
          {morningWorkflowStatus === 'complete' && (
            <span className="text-sm text-green-500 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4" />
              Completed Today
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {morningSteps.map((step, index) => {
            const statusInfo = getStepStatus(step);
            const isClickable = step.action || step.link;

            return (
              <div
                key={step.id}
                onClick={() => {
                  if (step.action) step.action();
                  else if (step.link) navigate(step.link);
                }}
                className={`relative border rounded-xl p-5 transition-all ${statusInfo.border} ${statusInfo.bg} ${
                  isClickable ? 'cursor-pointer hover:scale-105 hover:shadow-lg' : ''
                }`}
              >
                {/* Step Number Badge */}
                <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-panel border-2 border-purple-500 flex items-center justify-center text-sm font-bold text-purple-400">
                  {index + 1}
                </div>

                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {statusInfo.icon}
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      {step.icon}
                      <h3 className="font-semibold">{step.title}</h3>
                    </div>
                    <p className="text-sm text-muted">{step.description}</p>
                    {step.estimatedTime && step.status === 'pending' && (
                      <p className="text-xs text-muted">~{step.estimatedTime}</p>
                    )}
                  </div>
                  {isClickable && (
                    <ArrowRight className="w-5 h-5 text-muted flex-shrink-0" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Evening Process (show after 5 PM or if completed) */}
      {(isEvening || eveningWorkflowStatus === 'complete') && (
        <div className="card p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Moon className="w-6 h-6 text-indigo-400" />
                Evening Process
              </h2>
              <p className="text-muted mt-1">Wrap up your day and prepare for tomorrow</p>
            </div>
            {eveningWorkflowStatus === 'complete' && (
              <span className="text-sm text-green-500 flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" />
                Completed Today
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {eveningSteps.map((step, index) => {
              const statusInfo = getStepStatus(step);
              const isClickable = step.action || step.link;

              return (
                <div
                  key={step.id}
                  onClick={() => {
                    if (step.action) step.action();
                    else if (step.link) navigate(step.link);
                  }}
                  className={`relative border rounded-xl p-5 transition-all ${statusInfo.border} ${statusInfo.bg} ${
                    isClickable ? 'cursor-pointer hover:scale-105 hover:shadow-lg' : ''
                  }`}
                >
                  <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-panel border-2 border-indigo-500 flex items-center justify-center text-sm font-bold text-indigo-400">
                    {index + 1}
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-1">
                      {statusInfo.icon}
                    </div>
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        {step.icon}
                        <h3 className="font-semibold">{step.title}</h3>
                      </div>
                      <p className="text-sm text-muted">{step.description}</p>
                      {step.estimatedTime && step.status === 'pending' && (
                        <p className="text-xs text-muted">~{step.estimatedTime}</p>
                      )}
                    </div>
                    {isClickable && (
                      <ArrowRight className="w-5 h-5 text-muted flex-shrink-0" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Access */}
      <div className="space-y-4">
        <h2 className="text-2xl font-semibold">Quick Access</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quickAccessCards.map((card) => (
            <div
              key={card.title}
              onClick={() => navigate(card.link)}
              className="relative group cursor-pointer"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${card.color} rounded-xl opacity-10 group-hover:opacity-20 transition-opacity`} />
              <div className="relative border border-border rounded-xl p-5 bg-panel hover:bg-panel2 transition-all group-hover:scale-105">
                <div className="flex items-start justify-between mb-3">
                  <div className={`p-2 rounded-lg bg-gradient-to-br ${card.color}`}>
                    {card.icon}
                  </div>
                  {card.badge && (
                    <span className="px-2 py-1 rounded-full bg-panel2 border border-border text-xs font-medium">
                      {card.badge}
                    </span>
                  )}
                </div>
                <h3 className="font-semibold mb-1">{card.title}</h3>
                <p className="text-sm text-muted">{card.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Demo Links */}
      <div className="card p-6">
        <h3 className="font-semibold mb-4">Demo Applications</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => window.open('http://localhost:5173', '_blank')}
            className="btn-outline text-sm"
          >
            🌐 Main Vault UI
          </button>
          <button
            onClick={() => window.open('http://localhost:5181', '_blank')}
            className="btn-outline text-sm"
          >
            📊 Stream Diagnostics
          </button>
        </div>
      </div>
    </div>
  );
}
