# Service Management API - theVault

## Overview
REST API endpoints for managing theVault system services (Ollama, LLM Server, RAG Server, UI/Vite).

**Module**: `System/Scripts/RAG/routes/services.py`
**Prefix**: `/services`
**Tags**: `["services"]`

---

## Endpoints

### GET /services/status

**Description**: Get current status of all theVault services

**Response**: `ServicesStatusResponse`
```json
{
  "services": [
    {
      "name": "Ollama",
      "running": true,
      "pid": 12345,
      "details": "PID 12345"
    },
    {
      "name": "LLM Server",
      "running": true,
      "pid": 23456,
      "details": "PID 23456"
    },
    {
      "name": "RAG Server",
      "running": true,
      "pid": 34567,
      "details": "PID 34567"
    },
    {
      "name": "UI (Vite)",
      "running": true,
      "pid": 45678,
      "details": "PID 45678"
    }
  ],
  "all_running": true,
  "all_stopped": false
}
```

**Status Codes**:
- `200 OK` - Successfully retrieved status
- `500 Internal Server Error` - Failed to check services

**Example**:
```bash
curl http://localhost:5055/services/status
```

---

### POST /services/start

**Description**: Start all theVault services using `start_all.py`

**Request**: No body required

**Response**: `ServiceActionResponse`
```json
{
  "success": true,
  "message": "All services started",
  "output": "✅ All Services Started\n\nStatus:\n  ✓ Ollama started (log: /tmp/ollama.log)\n  ✓ LLM Server started (log: /tmp/llm_server.log)\n  ✓ RAG Server started (log: /tmp/rag_server.log)\n  ✓ UI (Vite) started (log: /tmp/ui_(vite).log)\n\nLogs: /tmp/*.log",
  "services": [
    {
      "name": "Ollama",
      "running": true,
      "pid": 12345,
      "details": "PID 12345"
    }
    // ... other services
  ]
}
```

**Status Codes**:
- `200 OK` - Services started (check `success` field)
- `500 Internal Server Error` - Startup failed or timed out

**Timeout**: 30 seconds

**Example**:
```bash
curl -X POST http://localhost:5055/services/start
```

**Implementation**:
- Calls `System/Scripts/Services/start_all.py` via venv python
- Captures stdout/stderr output
- Returns updated service statuses
- Times out after 30 seconds

---

### POST /services/stop

**Description**: Gracefully stop all theVault services using `stop_all.py`

**Request**: No body required

**Response**: `ServiceActionResponse`
```json
{
  "success": true,
  "message": "All services stopped",
  "output": "✅ All Services Stopped\n\nStatus:\n  ✓ UI (Vite) stopped\n  ✓ RAG Server stopped\n  ✓ LLM Server stopped\n  ✓ Ollama stopped",
  "services": [
    {
      "name": "Ollama",
      "running": false,
      "pid": null,
      "details": "Not running"
    }
    // ... other services
  ]
}
```

**Status Codes**:
- `200 OK` - Services stopped (check `success` field)
- `500 Internal Server Error` - Shutdown failed or timed out

**Timeout**: 30 seconds

**Example**:
```bash
curl -X POST http://localhost:5055/services/stop
```

**Implementation**:
- Calls `System/Scripts/Services/stop_all.py` via venv python
- Attempts graceful SIGTERM shutdown
- Returns updated service statuses
- Times out after 30 seconds

---

### POST /services/kill

**Description**: Force kill all NeroSpicy services using `emergency_kill.py`

**Request**: No body required

**Response**: `ServiceActionResponse`
```json
{
  "success": true,
  "message": "All services killed",
  "output": "✅ Emergency Kill Complete: 3 processes terminated\n\nYou can now restart services safely",
  "services": [
    {
      "name": "Ollama",
      "running": false,
      "pid": null,
      "details": "Not running"
    }
    // ... other services
  ]
}
```

**Status Codes**:
- `200 OK` - Services killed (check `success` field)
- `500 Internal Server Error` - Kill failed or timed out

**Timeout**: 30 seconds

**Example**:
```bash
curl -X POST http://localhost:5055/services/kill
```

**Implementation**:
- Calls `System/Scripts/Services/emergency_kill.py` via venv python
- Sends SIGTERM, then SIGKILL if needed
- Also kills Ollama.app to prevent auto-restart
- Returns updated service statuses
- Times out after 30 seconds

**⚠️  Warning**: This is a destructive operation. Use only when graceful shutdown fails.

---

## Data Models

### ServiceStatus
```python
class ServiceStatus(BaseModel):
    name: str              # Service name (e.g., "Ollama")
    running: bool          # True if process is running
    pid: int | None        # Process ID (null if not running)
    details: str           # Human-readable status (e.g., "PID 12345")
```

### ServicesStatusResponse
```python
class ServicesStatusResponse(BaseModel):
    services: List[ServiceStatus]  # Array of service statuses
    all_running: bool              # True if all services running
    all_stopped: bool              # True if all services stopped
```

### ServiceActionResponse
```python
class ServiceActionResponse(BaseModel):
    success: bool              # True if action succeeded
    message: str               # Human-readable message
    output: str                # stdout/stderr from script
    services: List[ServiceStatus]  # Updated service statuses
```

---

## Process Detection

**Method**: `pgrep -f <pattern>`

**Patterns**:
- **Ollama**: `"ollama serve"`
- **LLM Server**: `"uvicorn.*llm.server"`
- **RAG Server**: `"uvicorn.*rag.server"`
- **UI (Vite)**: `"node.*vite"`

**Returns**: `(is_running: bool, pid: int | None)`

---

## Script Locations

All service management scripts are in `System/Scripts/Services/`:

- **start_all.py** - Start all services
- **stop_all.py** - Graceful shutdown
- **emergency_kill.py** - Force kill

**Execution**:
```python
project_root = Path.home() / "NeroSpicy"
venv_python = project_root / ".venv" / "bin" / "python"
script = project_root / "System" / "Scripts" / "Services" / "start_all.py"

result = subprocess.run(
    [str(venv_python), str(script)],
    capture_output=True,
    text=True,
    timeout=30
)
```

---

## Frontend Integration

**UI Location**: `ui/src/pages/Workflows.tsx` (Service Management section)

**API Client** (`ui/src/lib/api.ts`):
```typescript
export async function getServicesStatus(): Promise<ServicesStatusResponse>
export async function startServices(): Promise<ServiceActionResponse>
export async function stopServices(): Promise<ServiceActionResponse>
export async function killServices(): Promise<ServiceActionResponse>
```

**Usage Example**:
```typescript
// Get status
const status = await getServicesStatus();
console.log(status.all_running);

// Start services
const result = await startServices();
if (result.success) {
  console.log("Services started");
} else {
  console.error(result.output);
}

// Stop services
await stopServices();

// Force kill (emergency)
await killServices();
```

---

## Error Handling

### Common Errors

**Script not found** (500):
```json
{
  "detail": "Start script not found: /path/to/start_all.py"
}
```

**Timeout** (500):
```json
{
  "detail": "Service startup timed out"
}
```

**Script execution error** (500):
```json
{
  "detail": "Error message from exception"
}
```

### Handling in Frontend
```typescript
try {
  const result = await startServices();
  if (!result.success) {
    // Some services failed - check result.output
    toast.warning(result.message);
  } else {
    toast.success(result.message);
  }
} catch (err) {
  // HTTP error or network issue
  toast.error(`Failed: ${err.message}`);
}
```

---

## Logging

**Service logs** are written to `/tmp/`:
- `/tmp/ollama.log`
- `/tmp/llm_server.log`
- `/tmp/rag_server.log`
- `/tmp/ui_(vite).log`

**API logs** use standard FastAPI logging:
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Starting services...")
logger.error(f"Error: {str(e)}")
```

---

## Testing

### Manual API Tests
```bash
# Get status
curl http://localhost:5055/services/status | jq

# Start services
curl -X POST http://localhost:5055/services/start | jq

# Stop services
curl -X POST http://localhost:5055/services/stop | jq

# Force kill
curl -X POST http://localhost:5055/services/kill | jq
```

### UI Testing
1. Open http://localhost:5173/workflows
2. Scroll to "Service Management" section
3. Click "🔄 Refresh Status"
4. Test each control button
5. Verify logs and status updates

---

## Security Considerations

1. **No authentication** - Assumes localhost-only access
2. **Command injection** - Uses fixed script paths, not user input
3. **Process control** - Limited to NeroSpicy services only
4. **Force kill** - Can terminate critical services, use with caution

**Production recommendations**:
- Add authentication/authorization
- Rate limit service control endpoints
- Audit log all service actions
- Restrict to admin users only

---

## Version History

- **v1.0.0** (2025-11-30): Initial implementation
  - Service status endpoint with PID tracking
  - Start/stop/kill endpoints
  - Integration with existing service scripts
  - Frontend UI integration

---

## See Also

- `System/Scripts/Services/CLAUDE.md` - Service scripts documentation
- `System/Scripts/Workflows/CLAUDE.md` - Workflows system
- `ui/src/pages/Workflows.tsx` - Frontend implementation
- `ui/src/lib/api.ts` - API client functions
