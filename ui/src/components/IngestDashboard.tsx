import React, { useState, useEffect } from 'react';
import { Play, Pause, RefreshCw, FileText, Mail, FileImage, AlertCircle, CheckCircle, Clock, Users } from 'lucide-react';

interface InboxStats {
  markdown: number;
  email: number;
  pdf: number;
  total: number;
}

interface ProcessingResult {
  success: boolean;
  file: string;
  type: 'markdown' | 'email' | 'pdf';
  tags?: string[];
  glossaryTerms?: number;
  calendarMatch?: string;
  attendees?: string[];
  error?: string;
  warnings?: string[];
}

interface ProcessingSession {
  id: string;
  startTime: Date;
  endTime?: Date;
  status: 'running' | 'completed' | 'failed' | 'paused';
  processed: number;
  total: number;
  results: ProcessingResult[];
  errors: ProcessingResult[];
}

export const IngestDashboard: React.FC = () => {
  const [inboxStats, setInboxStats] = useState<InboxStats>({ markdown: 0, email: 0, pdf: 0, total: 0 });
  const [currentSession, setCurrentSession] = useState<ProcessingSession | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['markdown']));

  // Mock data for development
  useEffect(() => {
    // Simulate fetching inbox stats
    setInboxStats({
      markdown: 23,
      email: 15,
      pdf: 8,
      total: 46
    });
  }, []);

  const startProcessing = async () => {
    setIsProcessing(true);
    const session: ProcessingSession = {
      id: Date.now().toString(),
      startTime: new Date(),
      status: 'running',
      processed: 0,
      total: inboxStats.total,
      results: [],
      errors: []
    };
    setCurrentSession(session);

    // TODO: Call actual processing API
    // For now, simulate processing
    simulateProcessing(session);
  };

  const simulateProcessing = (session: ProcessingSession) => {
    let processed = 0;
    const interval = setInterval(() => {
      processed++;
      
      // Simulate some results
      const mockResult: ProcessingResult = {
        success: Math.random() > 0.1, // 90% success rate
        file: `file-${processed}.md`,
        type: 'markdown',
        tags: ['meeting', 'project', 'planning'],
        glossaryTerms: Math.floor(Math.random() * 8) + 2,
        calendarMatch: Math.random() > 0.3 ? 'Weekly Team Sync' : undefined,
        attendees: Math.random() > 0.5 ? ['John Doe', 'Jane Smith'] : undefined,
        error: Math.random() > 0.9 ? 'LLM timeout' : undefined,
        warnings: Math.random() > 0.7 ? ['No calendar match found'] : undefined
      };

      const updatedSession = { ...session };
      updatedSession.processed = processed;
      
      if (mockResult.success) {
        updatedSession.results.push(mockResult);
      } else {
        updatedSession.errors.push(mockResult);
      }

      setCurrentSession(updatedSession);

      if (processed >= session.total) {
        clearInterval(interval);
        updatedSession.status = 'completed';
        updatedSession.endTime = new Date();
        setCurrentSession(updatedSession);
        setIsProcessing(false);
      }
    }, 500);
  };

  const pauseProcessing = () => {
    setIsProcessing(false);
    if (currentSession) {
      setCurrentSession({ ...currentSession, status: 'paused' });
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'markdown': return <FileText className="w-4 h-4" />;
      case 'email': return <Mail className="w-4 h-4" />;
      case 'pdf': return <FileImage className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const formatDuration = (start: Date, end?: Date) => {
    const duration = (end || new Date()).getTime() - start.getTime();
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Clean Ingest Dashboard</h1>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <RefreshCw className="w-4 h-4" />
          <span>Last updated: {new Date().toLocaleTimeString()}</span>
        </div>
      </div>

      {/* Inbox Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Markdown Files</p>
              <p className="text-2xl font-bold text-blue-600">{inboxStats.markdown}</p>
            </div>
            <FileText className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Email Files</p>
              <p className="text-2xl font-bold text-green-600">{inboxStats.email}</p>
            </div>
            <Mail className="w-8 h-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">PDF Files</p>
              <p className="text-2xl font-bold text-purple-600">{inboxStats.pdf}</p>
            </div>
            <FileImage className="w-8 h-8 text-purple-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Files</p>
              <p className="text-2xl font-bold text-gray-900">{inboxStats.total}</p>
            </div>
            <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
              <span className="text-sm font-bold text-gray-600">∑</span>
            </div>
          </div>
        </div>
      </div>

      {/* Processing Controls */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-semibold mb-4">Processing Controls</h2>
        
        {/* File Type Selection */}
        <div className="mb-4">
          <p className="text-sm font-medium text-gray-700 mb-2">Select file types to process:</p>
          <div className="flex space-x-4">
            {[
              { key: 'markdown', label: 'Markdown', icon: FileText, count: inboxStats.markdown },
              { key: 'email', label: 'Email', icon: Mail, count: inboxStats.email },
              { key: 'pdf', label: 'PDF', icon: FileImage, count: inboxStats.pdf }
            ].map(({ key, label, icon: Icon, count }) => (
              <label key={key} className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedTypes.has(key)}
                  onChange={(e) => {
                    const newTypes = new Set(selectedTypes);
                    if (e.target.checked) {
                      newTypes.add(key);
                    } else {
                      newTypes.delete(key);
                    }
                    setSelectedTypes(newTypes);
                  }}
                  className="rounded border-gray-300"
                />
                <Icon className="w-4 h-4" />
                <span className="text-sm">{label} ({count})</span>
              </label>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-3">
          {!isProcessing ? (
            <button
              onClick={startProcessing}
              disabled={selectedTypes.size === 0 || inboxStats.total === 0}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              <span>Start Processing</span>
            </button>
          ) : (
            <button
              onClick={pauseProcessing}
              className="flex items-center space-x-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              <Pause className="w-4 h-4" />
              <span>Pause</span>
            </button>
          )}
        </div>
      </div>

      {/* Current Session */}
      {currentSession && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Current Session</h2>
            <div className="flex items-center space-x-4 text-sm text-gray-500">
              <div className="flex items-center space-x-1">
                <Clock className="w-4 h-4" />
                <span>{formatDuration(currentSession.startTime, currentSession.endTime)}</span>
              </div>
              <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                currentSession.status === 'running' ? 'bg-blue-100 text-blue-800' :
                currentSession.status === 'completed' ? 'bg-green-100 text-green-800' :
                currentSession.status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {currentSession.status}
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>Progress</span>
              <span>{currentSession.processed} / {currentSession.total}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(currentSession.processed / currentSession.total) * 100}%` }}
              />
            </div>
          </div>

          {/* Session Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              <span className="text-sm">
                <span className="font-medium">{currentSession.results.length}</span> successful
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <span className="text-sm">
                <span className="font-medium">{currentSession.errors.length}</span> failed
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Users className="w-5 h-5 text-blue-500" />
              <span className="text-sm">
                <span className="font-medium">
                  {currentSession.results.filter(r => r.calendarMatch).length}
                </span> calendar matches
              </span>
            </div>
          </div>

          {/* Recent Results */}
          {currentSession.results.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">Recent Results</h3>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {currentSession.results.slice(-5).map((result, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                    <div className="flex items-center space-x-2">
                      {getTypeIcon(result.type)}
                      <span className="text-sm font-medium">{result.file}</span>
                      {result.calendarMatch && (
                        <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                          📅 {result.calendarMatch}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-xs text-gray-500">
                      {result.tags && <span>{result.tags.length} tags</span>}
                      {result.glossaryTerms && <span>{result.glossaryTerms} terms</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Failed Files */}
          {currentSession.errors.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-red-700 mb-2">Failed Files</h3>
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {currentSession.errors.map((error, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-red-50 rounded">
                    <div className="flex items-center space-x-2">
                      {getTypeIcon(error.type)}
                      <span className="text-sm font-medium">{error.file}</span>
                    </div>
                    <span className="text-xs text-red-600">{error.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};