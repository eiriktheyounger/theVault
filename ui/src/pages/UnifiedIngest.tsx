import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Play, 
  RefreshCw, 
  FileText, 
  Mail, 
  FileImage,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle
} from 'lucide-react';

interface InboxStats {
  markdown: number;
  email: number;
  pdf: number;
  total: number;
}

interface ProcessingResult {
  success: number;
  failed: number;
  failedFiles: string[];
  processedFiles: string[];
  errors: { file: string; error: string }[];
}

interface ProcessingSession {
  id: string;
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  currentFile?: string;
  startTime?: Date;
  endTime?: Date;
  results?: ProcessingResult;
}

const UnifiedIngest: React.FC = () => {
  const [inboxStats, setInboxStats] = useState<InboxStats>({ markdown: 0, email: 0, pdf: 0, total: 0 });
  const [session, setSession] = useState<ProcessingSession>({ id: '', status: 'idle', progress: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // Fetch inbox statistics
  const fetchInboxStats = async () => {
    try {
      const response = await fetch('/api/inbox/stats');
      if (response.ok) {
        const stats = await response.json();
        setInboxStats(stats);
        setLastRefresh(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch inbox stats:', error);
    }
  };

  // Start unified processing
  const startProcessing = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/process/unified', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          types: ['markdown', 'email', 'pdf'],
          options: {
            calendar_integration: true,
            smart_naming: true,
            parallel_processing: true
          }
        })
      });

      if (response.ok) {
        const sessionData = await response.json();
        setSession({
          id: sessionData.session_id,
          status: 'running',
          progress: 0,
          startTime: new Date()
        });
        
        // Start polling for progress
        pollProgress(sessionData.session_id);
      }
    } catch (error) {
      console.error('Failed to start processing:', error);
      setSession(prev => ({ ...prev, status: 'error' }));
    } finally {
      setIsLoading(false);
    }
  };

  // Poll processing progress
  const pollProgress = async (sessionId: string) => {
    const poll = async () => {
      try {
        const response = await fetch(`/api/process/status/${sessionId}`);
        if (response.ok) {
          const status = await response.json();
          
          setSession(prev => ({
            ...prev,
            status: status.status,
            progress: status.progress,
            currentFile: status.current_file,
            results: status.results,
            endTime: status.status === 'completed' ? new Date() : undefined
          }));

          if (status.status === 'running') {
            setTimeout(poll, 1000); // Poll every second
          } else {
            // Refresh inbox stats when done
            fetchInboxStats();
          }
        }
      } catch (error) {
        console.error('Failed to poll progress:', error);
      }
    };
    
    poll();
  };

  // Format duration
  const formatDuration = (start: Date, end?: Date) => {
    const endTime = end || new Date();
    const duration = Math.floor((endTime.getTime() - start.getTime()) / 1000);
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Load initial data
  useEffect(() => {
    fetchInboxStats();
    const interval = setInterval(fetchInboxStats, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Unified Content Ingest</h1>
        <Button 
          onClick={fetchInboxStats} 
          variant="outline" 
          size="sm"
          disabled={session.status === 'running'}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Inbox Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Markdown Files</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inboxStats.markdown}</div>
            <p className="text-xs text-muted-foreground">Plaud transcriptions</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Email Files</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inboxStats.email}</div>
            <p className="text-xs text-muted-foreground">EML messages</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">PDF Files</CardTitle>
            <FileImage className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inboxStats.pdf}</div>
            <p className="text-xs text-muted-foreground">Documents</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Files</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{inboxStats.total}</div>
            <p className="text-xs text-muted-foreground">
              Updated {lastRefresh.toLocaleTimeString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Processing Control */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Processing Control
            {session.status === 'running' && <Badge variant="secondary">Running</Badge>}
            {session.status === 'completed' && <Badge variant="default">Completed</Badge>}
            {session.status === 'error' && <Badge variant="destructive">Error</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Button 
              onClick={startProcessing}
              disabled={session.status === 'running' || isLoading || inboxStats.total === 0}
              className="flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Unified Processing
            </Button>
            
            {session.status === 'running' && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Processing {session.currentFile || 'files'}...
              </div>
            )}
          </div>

          {session.status === 'running' && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <span>{session.progress}%</span>
              </div>
              <Progress value={session.progress} className="w-full" />
              {session.startTime && (
                <p className="text-xs text-muted-foreground">
                  Running for {formatDuration(session.startTime)}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Processing Results */}
      {session.results && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Processing Results
              {session.startTime && session.endTime && (
                <Badge variant="outline">
                  {formatDuration(session.startTime, session.endTime)}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <span className="font-medium">{session.results.success} files processed successfully</span>
              </div>
              
              {session.results.failed > 0 && (
                <div className="flex items-center gap-2">
                  <XCircle className="w-5 h-5 text-red-500" />
                  <span className="font-medium">{session.results.failed} files failed</span>
                </div>
              )}
            </div>

            {session.results.processedFiles.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Successfully Processed:</h4>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {session.results.processedFiles.map((file, index) => (
                    <div key={index} className="text-sm text-muted-foreground flex items-center gap-2">
                      <CheckCircle className="w-3 h-3 text-green-500" />
                      {file}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {session.results.errors.length > 0 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  <div className="space-y-2">
                    <p className="font-medium">Failed Files:</p>
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {session.results.errors.map((error, index) => (
                        <div key={index} className="text-sm">
                          <span className="font-medium">{error.file}:</span> {error.error}
                        </div>
                      ))}
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default UnifiedIngest;