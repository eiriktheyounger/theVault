import { useState } from 'react';

interface RefreshResult {
  success: boolean;
  message: string;
  timestamp: string;
  dashboardsCreated?: string[];
  errors?: string[];
}

export default function DashboardRefresh() {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [result, setResult] = useState<RefreshResult | null>(null);

  const handleRefresh = async (dashboardType: string = 'all') => {
    setIsRefreshing(true);
    setResult(null);

    try {
      const response = await fetch('/api/dashboard/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dashboardType,
          targetDate: new Date().toISOString().split('T')[0] // Today's date
        })
      });

      const data = await response.json();

      if (data.success) {
        setLastRefresh(new Date());
        setResult({
          success: true,
          message: 'Dashboard refresh completed successfully!',
          timestamp: data.timestamp,
          dashboardsCreated: data.dashboardsCreated || []
        });
      } else {
        setResult({
          success: false,
          message: data.message || 'Dashboard refresh failed',
          timestamp: new Date().toISOString(),
          errors: data.errors || []
        });
      }
    } catch (error) {
      console.error('Dashboard refresh error:', error);
      setResult({
        success: false,
        message: 'Failed to refresh dashboards - network error',
        timestamp: new Date().toISOString(),
        errors: [error instanceof Error ? error.message : 'Unknown error']
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="dashboard-refresh-section">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        📊 Dashboard Management
      </h3>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {/* Main Refresh Button */}
        <div className="mb-6">
          <button
            onClick={() => handleRefresh('all')}
            disabled={isRefreshing}
            className={`
              w-full py-3 px-4 rounded-md text-white font-medium
              ${isRefreshing
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
              }
              transition-colors duration-200
            `}
          >
            {isRefreshing ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Refreshing All Dashboards...
              </span>
            ) : (
              '🔄 Refresh All Dashboards'
            )}
          </button>
        </div>

        {/* Specific Dashboard Options */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <button
            onClick={() => handleRefresh('work')}
            disabled={isRefreshing}
            className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            💼 Work
          </button>
          <button
            onClick={() => handleRefresh('personal')}
            disabled={isRefreshing}
            className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            🏠 Personal
          </button>
          <button
            onClick={() => handleRefresh('weekly')}
            disabled={isRefreshing}
            className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            📅 Weekly
          </button>
          <button
            onClick={() => handleRefresh('analytics')}
            disabled={isRefreshing}
            className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            📈 Analytics
          </button>
        </div>

        {/* Status Information */}
        {lastRefresh && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md">
            <p className="text-sm text-green-800">
              ✅ Last refresh: {lastRefresh.toLocaleString()}
            </p>
          </div>
        )}

        {/* Result Display */}
        {result && (
          <div className={`p-4 rounded-md ${result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
            <div className={`text-sm font-medium ${result.success ? 'text-green-800' : 'text-red-800'}`}>
              {result.success ? '✅' : '❌'} {result.message}
            </div>

            {result.dashboardsCreated && result.dashboardsCreated.length > 0 && (
              <div className="mt-2 text-sm text-green-700">
                <p className="font-medium">Created dashboards:</p>
                <ul className="list-disc list-inside ml-2 mt-1">
                  {result.dashboardsCreated.map((dashboard, index) => (
                    <li key={index}>{dashboard}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.errors && result.errors.length > 0 && (
              <div className="mt-2 text-sm text-red-700">
                <p className="font-medium">Errors:</p>
                <ul className="list-disc list-inside ml-2 mt-1">
                  {result.errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-2 text-xs text-gray-500">
              {new Date(result.timestamp).toLocaleString()}
            </div>
          </div>
        )}

        {/* Dashboard Information */}
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Dashboard Types</h4>
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex justify-between">
              <span>💼 Work Dashboard:</span>
              <span>Work tasks, meetings, and goals</span>
            </div>
            <div className="flex justify-between">
              <span>🏠 Personal Dashboard:</span>
              <span>Personal tasks, health, and learning</span>
            </div>
            <div className="flex justify-between">
              <span>📅 Weekly Dashboard:</span>
              <span>Weekly overview and progress</span>
            </div>
            <div className="flex justify-between">
              <span>📈 Analytics Dashboard:</span>
              <span>Productivity insights and metrics</span>
            </div>
          </div>
        </div>

        {/* CLI Command Reference */}
        <div className="mt-6 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 mb-3">CLI Commands</h4>
          <div className="bg-gray-50 rounded-md p-3 text-xs font-mono">
            <div className="text-gray-600 mb-2"># Refresh all dashboards</div>
            <div>cd System/Scripts && python dashboard_refresh_system.py --refresh-all</div>
            <div className="text-gray-600 mt-2 mb-2"># Check status</div>
            <div>python dashboard_refresh_system.py --status</div>
            <div className="text-gray-600 mt-2 mb-2"># Refresh specific dashboard</div>
            <div>python dashboard_refresh_system.py --dashboard work</div>
          </div>
        </div>
      </div>
    </div>
  );
}