import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import {
  startWorkflow,
  getWorkflowStatus,
  streamWorkflowWs,
  listWorkflows,
  resetIngest,
  getServicesStatus,
  startServices,
  stopServices,
  killServices,
  getCurrentProfile,
  listProfiles,
  setProfile,
  type WorkflowStatus,
  type WorkflowStep,
  type ServicesStatusResponse,
  type ServiceActionResponse,
  type SystemProfile,
  type CurrentProfileResponse,
} from '../lib/api';

interface ExpandedSteps {
  [stepNum: number]: boolean;
}

interface WorkflowJobState {
  job_id: string;
  workflow_type: 'morning' | 'evening';
  status: WorkflowStatus | null;
  websocket: WebSocket | null;
}

export default function Workflows() {
  const [morningJob, setMorningJob] = useState<WorkflowJobState | null>(null);
  const [eveningJob, setEveningJob] = useState<WorkflowJobState | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [expandedMorningSteps, setExpandedMorningSteps] = useState<ExpandedSteps>({});
  const [expandedEveningSteps, setExpandedEveningSteps] = useState<ExpandedSteps>({});

  // Reset state
  const [resetHours, setResetHours] = useState<number>(1);
  const [resetLog, setResetLog] = useState<string>('');
  const [resetRunning, setResetRunning] = useState<boolean>(false);

  // Status check state
  const [statusCheckResult, setStatusCheckResult] = useState<string>('');

  // Service management state
  const [servicesStatus, setServicesStatus] = useState<ServicesStatusResponse | null>(null);
  const [serviceActionLog, setServiceActionLog] = useState<string>('');
  const [serviceActionRunning, setServiceActionRunning] = useState<boolean>(false);

  // System profile state
  const [currentProfile, setCurrentProfile] = useState<CurrentProfileResponse | null>(null);
  const [availableProfiles, setAvailableProfiles] = useState<SystemProfile[]>([]);
  const [profileChanging, setProfileChanging] = useState<boolean>(false);

  const morningWsRef = useRef<WebSocket | null>(null);
  const eveningWsRef = useRef<WebSocket | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Step names for placeholders
  const MORNING_STEPS = [
    'Start Services',
    'Sync Calendar (Harmonic → Work)',
    'Create Daily Dashboard',
    'Run Ingest',
    'Organize Files',
    'Map to Calendar',
    'Update TOCs',
  ];

  const EVENING_STEPS = [
    'Generate Day Review',
    'Highlight Tomorrow Focus',
    'Queue Overnight Jobs',
  ];

  // Create placeholder steps for immediate display
  const createPlaceholderSteps = (workflowType: 'morning' | 'evening'): WorkflowStep[] => {
    const stepNames = workflowType === 'morning' ? MORNING_STEPS : EVENING_STEPS;
    return stepNames.map((name, idx) => ({
      step_num: idx + 1,
      name,
      status: 'pending' as const,
      progress: 0,
      summary_lines: ['Waiting to start...'],
      errors: [],
    }));
  };

  // Cleanup WebSockets and polling on unmount
  useEffect(() => {
    return () => {
      if (morningWsRef.current) {
        morningWsRef.current.close();
      }
      if (eveningWsRef.current) {
        eveningWsRef.current.close();
      }
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Load running/recent workflows on mount
  useEffect(() => {
    const loadExistingWorkflows = async () => {
      try {
        const result = await listWorkflows();
        if (result.ok && result.jobs.length > 0) {
          // Find most recent morning and evening workflows
          const morningJobs = result.jobs.filter(j => j.workflow_type === 'morning');
          const eveningJobs = result.jobs.filter(j => j.workflow_type === 'evening');

          if (morningJobs.length > 0) {
            const latestMorning = morningJobs[0]; // Already sorted by started_at desc
            const status = await getWorkflowStatus(latestMorning.job_id);
            if (status) {
              setMorningJob({
                job_id: latestMorning.job_id,
                workflow_type: 'morning',
                status,
                websocket: null,
              });
              // If running, start polling
              if (status.status === 'running' || status.status === 'queued') {
                startPolling(latestMorning.job_id, 'morning');
              }
            }
          }

          if (eveningJobs.length > 0) {
            const latestEvening = eveningJobs[0];
            const status = await getWorkflowStatus(latestEvening.job_id);
            if (status) {
              setEveningJob({
                job_id: latestEvening.job_id,
                workflow_type: 'evening',
                status,
                websocket: null,
              });
              if (status.status === 'running' || status.status === 'queued') {
                startPolling(latestEvening.job_id, 'evening');
              }
            }
          }
        }
      } catch (err) {
        console.error('Failed to load existing workflows:', err);
      }
    };

    loadExistingWorkflows();
  }, []);

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

  // Start polling for a workflow
  const startPolling = (jobId: string, workflowType: 'morning' | 'evening') => {
    const setJob = workflowType === 'morning' ? setMorningJob : setEveningJob;

    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    pollingRef.current = setInterval(async () => {
      try {
        const status = await getWorkflowStatus(jobId);
        if (status) {
          setJob(prev => ({
            ...prev!,
            status,
          }));
          if (status.status === 'complete' || status.status === 'error') {
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 5000);
  };

  // Clear a completed workflow from display
  const handleClearWorkflow = (workflowType: 'morning' | 'evening') => {
    if (workflowType === 'morning') {
      setMorningJob(null);
    } else {
      setEveningJob(null);
    }
  };

  // Handle reset ingest
  const handleResetIngest = async (dryRun: boolean = false) => {
    setResetRunning(true);
    setResetLog(`${dryRun ? '🧪 DRY RUN - ' : ''}Starting reset for last ${resetHours} hour(s)...\n`);

    try {
      const result = await resetIngest(resetHours, dryRun);

      if (result.ok) {
        setResetLog(result.log || 'Reset complete');
        if (!dryRun) {
          toast.success('Reset complete');
        }
      } else {
        setResetLog(result.log || result.error || 'Reset failed');
        toast.error(`Reset failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err) {
      const errorMsg = (err as Error).message;
      setResetLog(`Error: ${errorMsg}`);
      toast.error(`Reset failed: ${errorMsg}`);
    } finally {
      setResetRunning(false);
    }
  };

  // Check current workflow status from server
  const handleCheckStatus = async () => {
    try {
      const result = await listWorkflows();
      if (result.ok && result.jobs.length > 0) {
        const lines: string[] = [`Found ${result.jobs.length} workflow(s):\n`];

        for (const job of result.jobs) {
          const duration = job.duration ? `${job.duration.toFixed(1)}s` : 'running...';
          const started = new Date(job.started_at * 1000).toLocaleTimeString();
          lines.push(`• ${job.workflow_type} (${job.status})`);
          lines.push(`  Started: ${started}, Duration: ${duration}`);
          lines.push(`  Progress: ${job.overall_progress}%`);
          lines.push('');

          // If there's a running job, restore it to the UI
          if (job.status === 'running' || job.status === 'queued') {
            const status = await getWorkflowStatus(job.job_id);
            if (status) {
              const setJob = job.workflow_type === 'morning' ? setMorningJob : setEveningJob;
              setJob({
                job_id: job.job_id,
                workflow_type: job.workflow_type as 'morning' | 'evening',
                status,
                websocket: null,
              });
              startPolling(job.job_id, job.workflow_type as 'morning' | 'evening');
              lines.push(`  → Restored to UI and started polling`);
            }
          } else if (job.status === 'complete' || job.status === 'error') {
            // Also restore completed jobs
            const status = await getWorkflowStatus(job.job_id);
            if (status) {
              const setJob = job.workflow_type === 'morning' ? setMorningJob : setEveningJob;
              setJob({
                job_id: job.job_id,
                workflow_type: job.workflow_type as 'morning' | 'evening',
                status,
                websocket: null,
              });
              lines.push(`  → Restored to UI`);
            }
          }
        }

        setStatusCheckResult(lines.join('\n'));
        toast.success(`Found ${result.jobs.length} workflow(s)`);
      } else {
        setStatusCheckResult('No workflows found on server.');
        toast.info('No workflows found');
      }
    } catch (err) {
      const msg = (err as Error).message;
      setStatusCheckResult(`Error checking status: ${msg}`);
      toast.error(`Failed to check status: ${msg}`);
    }
  };

  // Service Management Handlers
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
      setServicesStatus({ services: result.services, all_running: result.services.every(s => s.running), all_stopped: result.services.every(s => !s.running) });
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
      setServicesStatus({ services: result.services, all_running: result.services.every(s => s.running), all_stopped: result.services.every(s => !s.running) });
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
      setServicesStatus({ services: result.services, all_running: result.services.every(s => s.running), all_stopped: result.services.every(s => !s.running) });
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

  const connectWebSocket = (jobId: string, workflowType: 'morning' | 'evening') => {
    const ws = streamWorkflowWs(jobId);
    const wsRef = workflowType === 'morning' ? morningWsRef : eveningWsRef;
    const setJob = workflowType === 'morning' ? setMorningJob : setEveningJob;

    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`WebSocket connected for ${workflowType} workflow`);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'initial_state') {
          // Set initial state
          setJob((prev) => ({
            ...prev!,
            status: {
              job_id: message.job_id,
              workflow_type: message.workflow_type,
              status: message.status,
              date: message.date,
              overall_progress: message.overall_progress,
              current_step: message.current_step,
              total_steps: message.total_steps,
              started_at: message.started_at,
              steps: message.steps || [],
            },
          }));
        } else if (message.type === 'step_progress') {
          // Update step progress
          setJob((prev) => {
            if (!prev || !prev.status) return prev;

            const updatedSteps = [...prev.status.steps];
            const stepIndex = message.step - 1;

            if (stepIndex >= 0 && stepIndex < updatedSteps.length) {
              updatedSteps[stepIndex] = {
                ...updatedSteps[stepIndex],
                status: message.status,
                progress: message.progress,
                summary_lines: message.summary_lines,
              };
            }

            return {
              ...prev,
              status: {
                ...prev.status,
                steps: updatedSteps,
                current_step: message.step,
              },
            };
          });
        } else if (message.type === 'workflow_complete') {
          // Workflow complete
          toast.success(`${workflowType} workflow completed!`);

          // Fetch final status
          getWorkflowStatus(jobId).then((status) => {
            if (status) {
              setJob((prev) => ({ ...prev!, status }));
            }
          });

          // Close WebSocket
          ws.close();
        } else if (message.type === 'workflow_error') {
          toast.error(`${workflowType} workflow failed: ${message.error}`);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      toast.error(`WebSocket connection failed for ${workflowType} workflow`);
    };

    ws.onclose = () => {
      console.log(`WebSocket closed for ${workflowType} workflow`);
    };
  };

  const handleStartWorkflow = async (workflowType: 'morning' | 'evening') => {
    try {
      const setJob = workflowType === 'morning' ? setMorningJob : setEveningJob;
      const totalSteps = workflowType === 'morning' ? 7 : 3;

      // Show full placeholder state immediately with all steps
      const placeholderJob: WorkflowJobState = {
        job_id: 'pending',
        workflow_type: workflowType,
        status: {
          job_id: 'pending',
          workflow_type: workflowType,
          status: 'running',
          date: selectedDate,
          overall_progress: 0,
          current_step: 0,
          total_steps: totalSteps,
          started_at: Date.now() / 1000,
          steps: createPlaceholderSteps(workflowType),
        },
        websocket: null,
      };

      setJob(placeholderJob);

      const result = await startWorkflow({
        workflow_type: workflowType,
        date: selectedDate,
      });

      if (!result.ok || !result.job_id) {
        const errorMsg = result.error || 'Unknown error';
        toast.error(`Failed to start ${workflowType} workflow: ${errorMsg}`);
        // Keep the job visible with error status instead of clearing
        setJob(prev => prev ? {
          ...prev,
          status: {
            ...prev.status!,
            status: 'error',
            error: errorMsg,
            steps: prev.status?.steps?.map((s, idx) =>
              idx === 0 ? { ...s, status: 'error' as const, summary_lines: [`Error: ${errorMsg}`] } : s
            ) || [],
          },
        } : null);
        return;
      }

      // Update with real job_id but keep the placeholder steps visible
      setJob(prev => ({
        ...prev!,
        job_id: result.job_id,
      }));

      toast.success(`${workflowType} workflow started`);

      // Connect WebSocket for real-time updates
      connectWebSocket(result.job_id, workflowType);

      // Also start polling as backup (every 5 seconds)
      startPolling(result.job_id, workflowType);

    } catch (error) {
      const errorMsg = (error as Error).message;
      console.error('Failed to start workflow:', error);
      toast.error(`Failed to start ${workflowType} workflow: ${errorMsg}`);
      // Keep the job visible with error status instead of clearing
      setJob(prev => prev ? {
        ...prev,
        status: {
          ...prev.status!,
          status: 'error',
          error: errorMsg,
          steps: prev.status?.steps?.map((s, idx) =>
            idx === 0 ? { ...s, status: 'error' as const, summary_lines: [`Network error: ${errorMsg}`] } : s
          ) || [],
        },
      } : null);
    }
  };

  const renderStep = (step: WorkflowStep, workflowType: 'morning' | 'evening') => {
    const statusIcon = {
      pending: '⏳',
      running: '⏳',
      complete: '✓',
      error: '✗',
    }[step.status];

    const statusColor = {
      pending: 'text-gray-400',
      running: 'text-blue-500',
      complete: 'text-green-500',
      error: 'text-red-500',
    }[step.status];

    const progressBarColor = {
      pending: 'bg-gray-300',
      running: 'bg-blue-500',
      complete: 'bg-green-500',
      error: 'bg-red-500',
    }[step.status];

    const expandedSteps = workflowType === 'morning' ? expandedMorningSteps : expandedEveningSteps;
    const setExpandedSteps = workflowType === 'morning' ? setExpandedMorningSteps : setExpandedEveningSteps;
    const isExpanded = expandedSteps[step.step_num] ?? true; // Default expanded

    const toggleExpanded = () => {
      setExpandedSteps(prev => ({ ...prev, [step.step_num]: !prev[step.step_num] }));
    };

    const summaryLineCount = step.summary_lines?.length || 0;

    return (
      <div key={step.step_num} className="border border-border rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold">
            Step {step.step_num}: {step.name}
          </h3>
          <span className={`${statusColor} font-bold`}>
            [{statusIcon} {step.status.charAt(0).toUpperCase() + step.status.slice(1)}]
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-panel2 rounded-full h-2 mb-3">
          <div
            className={`${progressBarColor} h-2 rounded-full transition-all duration-300`}
            style={{ width: `${step.progress}%` }}
          />
        </div>

        {/* Summary lines - Expandable */}
        {step.summary_lines && step.summary_lines.length > 0 && (
          <div>
            {summaryLineCount > 5 && (
              <button
                onClick={toggleExpanded}
                className="text-xs text-primary hover:text-primary-hover mb-1 font-medium"
              >
                {isExpanded ? `▼ Hide details (${summaryLineCount} lines)` : `▶ Show all details (${summaryLineCount} lines)`}
              </button>
            )}
            <div className="text-sm font-mono space-y-1 mb-2">
              {(isExpanded ? step.summary_lines : step.summary_lines.slice(0, 5)).map((line, idx) => (
                <div key={idx} className="text-muted">
                  {line.startsWith('├─') || line.startsWith('└─') || line.startsWith('---') || line.startsWith('  ') ? (
                    <span className="text-muted">{line}</span>
                  ) : (
                    <span>├─ {line}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Errors */}
        {step.errors && step.errors.length > 0 && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2 mt-2">
            <div className="text-sm text-red-600 dark:text-red-400 font-semibold mb-1">
              ❌ Errors:
            </div>
            {step.errors.map((error, idx) => (
              <div key={idx} className="text-sm text-red-600 dark:text-red-400">
                • {error}
              </div>
            ))}
          </div>
        )}

        {/* Duration */}
        {step.duration && (
          <div className="text-xs text-muted mt-2">
            Duration: {step.duration.toFixed(1)}s
          </div>
        )}
      </div>
    );
  };

  const renderWorkflowCard = (
    title: string,
    workflowType: 'morning' | 'evening',
    jobState: WorkflowJobState | null,
    totalSteps: number
  ) => {
    const isRunning = jobState && jobState.status?.status === 'running';
    const isComplete = jobState && jobState.status?.status === 'complete';
    const hasError = jobState && jobState.status?.status === 'error';

    return (
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{title}</h2>
          <div className="flex gap-2">
            {/* Clear button - show when complete or error */}
            {(isComplete || hasError) && (
              <button
                className="btn-outline text-sm"
                onClick={() => handleClearWorkflow(workflowType)}
              >
                ✕ Clear
              </button>
            )}
            <button
              className={`btn-primary ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={() => handleStartWorkflow(workflowType)}
              disabled={isRunning}
            >
              {isRunning ? 'Running...' : `▶ Start ${title}`}
            </button>
          </div>
        </div>

        {!jobState && (
          <div className="text-muted text-center py-8">
            Click "Start {title}" to begin the workflow
          </div>
        )}

        {jobState && jobState.status && (
          <>
            {/* Overall progress */}
            <div className="mb-6">
              <div className="flex justify-between text-sm text-muted mb-1">
                <span>Overall Progress</span>
                <span>
                  {jobState.status.overall_progress}% ({jobState.status.current_step}/{jobState.status.total_steps} steps)
                </span>
              </div>
              <div className="w-full bg-panel2 rounded-full h-3">
                <div
                  className={`h-3 rounded-full transition-all duration-300 ${
                    hasError
                      ? 'bg-red-500'
                      : isComplete
                      ? 'bg-green-500'
                      : 'bg-blue-500'
                  }`}
                  style={{ width: `${jobState.status.overall_progress}%` }}
                />
              </div>
            </div>

            {/* Status message */}
            {hasError && jobState.status.error && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
                <div className="font-semibold text-red-600 dark:text-red-400 mb-1">
                  ❌ Workflow Failed
                </div>
                <div className="text-sm text-red-600 dark:text-red-400">
                  {jobState.status.error}
                </div>
              </div>
            )}

            {isComplete && (
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 mb-4">
                <div className="font-semibold text-green-600 dark:text-green-400">
                  ✅ Workflow Complete
                </div>
                {jobState.status.duration && (
                  <div className="text-sm text-green-600 dark:text-green-400">
                    Total duration: {jobState.status.duration.toFixed(1)}s
                  </div>
                )}
              </div>
            )}

            {/* Steps */}
            <div className="space-y-4">
              {jobState.status.steps.map((step) => renderStep(step, workflowType))}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text mb-2">Workflows</h1>
        <p className="text-muted">
          Automated morning and evening workflows with real-time progress tracking
        </p>
      </div>

      {/* Date selector */}
      <div className="card p-4 mb-6">
        <label className="block text-sm font-medium text-text mb-2">
          Target Date
        </label>
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="px-3 py-2 border border-border rounded-md bg-panel focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* System Profile Selector */}
      {currentProfile && availableProfiles.length > 0 && (
        <div className="card p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                System Profile
              </label>
              <p className="text-xs text-muted">
                {currentProfile.hostname} • Current: {currentProfile.current_profile || 'Base Config'}
              </p>
            </div>
            <div className="text-xs text-muted">
              Calendar: {(currentProfile.config.calendars as { source?: string })?.source || 'Not set'} → {(currentProfile.config.calendars as { target?: string })?.target || 'Not set'}
            </div>
          </div>
          <div className="flex gap-2">
            {availableProfiles.map((profile) => (
              <button
                key={profile.id}
                onClick={() => handleProfileChange(profile.id)}
                disabled={profileChanging || currentProfile.current_profile === profile.id}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentProfile.current_profile === profile.id
                    ? 'bg-primary text-white'
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

      {/* Morning workflow */}
      {renderWorkflowCard('Morning Workflow', 'morning', morningJob, 7)}

      {/* Evening workflow */}
      {renderWorkflowCard('Evening Workflow', 'evening', eveningJob, 3)}

      {/* Status Check */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Workflow Status</h2>
            <p className="text-sm text-muted">Check server for running or completed workflows</p>
          </div>
          <button
            className="btn-primary text-sm"
            onClick={handleCheckStatus}
          >
            🔍 Check Status
          </button>
        </div>

        {statusCheckResult && (
          <div className="bg-panel2 border border-border rounded-lg p-4 max-h-48 overflow-y-auto">
            <pre className="text-sm font-mono whitespace-pre-wrap">{statusCheckResult}</pre>
          </div>
        )}
      </div>

      {/* Service Management */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Service Management</h2>
            <p className="text-sm text-muted">Control and monitor all theVault system services</p>
          </div>
          <div className="flex gap-2">
            <button
              className="btn-outline text-sm"
              onClick={() => window.open('http://localhost:5173', '_blank')}
            >
              🌐 Open Vault
            </button>
            <button
              className="btn-outline text-sm"
              onClick={() => window.open('http://localhost:5181', '_blank')}
            >
              📊 Open Stream Diagnostics
            </button>
            <button
              className="btn-outline text-sm"
              onClick={handleGetServicesStatus}
              disabled={serviceActionRunning}
            >
              🔄 Refresh Status
            </button>
          </div>
        </div>

        {/* Service Status Display */}
        {servicesStatus && (
          <div className="bg-panel2 border border-border rounded-lg p-4 mb-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {servicesStatus.services.map((service) => (
                <div key={service.name} className="flex items-center gap-2">
                  <span className={`text-lg ${service.running ? 'text-green-500' : 'text-red-500'}`}>
                    {service.running ? '●' : '○'}
                  </span>
                  <div>
                    <div className="text-sm font-medium">{service.name}</div>
                    <div className="text-xs text-muted">{service.details}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-border text-sm text-muted">
              {servicesStatus.all_running && '✅ All services running'}
              {servicesStatus.all_stopped && '⛔ All services stopped'}
              {!servicesStatus.all_running && !servicesStatus.all_stopped && '⚠️  Some services offline'}
            </div>
          </div>
        )}

        {/* Control Buttons */}
        <div className="flex items-center gap-3 mb-4">
          <button
            className={`btn-primary text-sm ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleStartServices}
            disabled={serviceActionRunning}
          >
            {serviceActionRunning ? '⏳ Working...' : '▶️  Start All'}
          </button>

          <button
            className={`btn-outline text-sm ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleStopServices}
            disabled={serviceActionRunning}
          >
            ⏸️ Stop All
          </button>

          <button
            className={`btn-outline text-sm text-red-500 hover:bg-red-500/10 ${serviceActionRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={handleKillServices}
            disabled={serviceActionRunning}
          >
            ⚠️  Force Kill
          </button>

          {serviceActionLog && (
            <button
              className="btn-outline text-sm ml-auto"
              onClick={() => setServiceActionLog('')}
            >
              ✕ Clear Log
            </button>
          )}
        </div>

        {/* Action Log */}
        {serviceActionLog && (
          <div className="bg-panel2 border border-border rounded-lg p-4 max-h-96 overflow-y-auto">
            <pre className="text-sm font-mono whitespace-pre-wrap">{serviceActionLog}</pre>
          </div>
        )}
      </div>

      {/* Reset Ingest */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Reset Ingest</h2>
            <p className="text-sm text-muted">Move processed files back to inbox for reprocessing</p>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted">Hours:</label>
            <input
              type="number"
              min="0.5"
              max="336"
              step="0.5"
              value={resetHours}
              onChange={(e) => setResetHours(Math.min(336, Math.max(0.5, parseFloat(e.target.value) || 1)))}
              className="w-20 px-2 py-1 border border-border rounded-md bg-panel text-sm"
              disabled={resetRunning}
            />
          </div>

          <button
            className="btn-outline text-sm"
            onClick={() => handleResetIngest(true)}
            disabled={resetRunning}
          >
            🧪 Dry Run
          </button>

          <button
            className={`btn-primary text-sm ${resetRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={() => handleResetIngest(false)}
            disabled={resetRunning}
          >
            {resetRunning ? 'Running...' : '🔄 Reset'}
          </button>

          {resetLog && (
            <button
              className="btn-outline text-sm"
              onClick={() => setResetLog('')}
            >
              ✕ Clear Log
            </button>
          )}
        </div>

        {/* Log output */}
        {resetLog && (
          <div className="bg-panel2 border border-border rounded-lg p-4 max-h-96 overflow-y-auto">
            <pre className="text-sm font-mono whitespace-pre-wrap">{resetLog}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
