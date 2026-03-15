# Notes.app Integration API - NeroSpicy

## Overview
REST API endpoints for accessing and searching Apple Notes.app data via AppleScript.

**Module**: `System/Scripts/RAG/routes/notes.py`
**Prefix**: `/notes`
**Tags**: `["notes"]`

---

## Endpoints

### GET /notes/folders

**Description**: Get all folders from Notes.app with note counts

**Response**: `NotesFolderListResponse`
```json
{
  "folders": [
    {
      "name": "NBCU - Master Workflow",
      "note_count": 45
    },
    {
      "name": "Daily notes",
      "note_count": 312
    }
  ],
  "total_folders": 200,
  "total_notes": 1437
}
```

**Status Codes**:
- `200 OK` - Successfully retrieved folders
- `500 Internal Server Error` - AppleScript execution failed

**Example**:
```bash
curl http://localhost:5055/notes/folders
```

**Implementation**:
- Uses AppleScript to enumerate all folders in Notes.app
- Counts notes in each folder
- Returns summary statistics

---

### GET /notes/list

**Description**: List notes from Notes.app, optionally filtered by folder

**Query Parameters**:
- `folder` (optional): Filter by folder name
- `limit` (optional, default=50, max=500): Maximum notes to return

**Response**: `NotesListResponse`
```json
{
  "notes": [
    {
      "id": "x-coredata://ABC123/Note/p456",
      "name": "Meeting Notes - Q4 Planning",
      "body": "Discussed goals for Q4...",
      "folder": "Work",
      "creation_date": "Monday, December 11, 2023 at 2:30:00 PM",
      "modification_date": "Monday, December 11, 2023 at 4:15:00 PM"
    }
  ],
  "total_count": 1437,
  "folder": "Work"
}
```

**Status Codes**:
- `200 OK` - Successfully retrieved notes
- `500 Internal Server Error` - AppleScript execution failed

**Examples**:
```bash
# List all notes (default limit: 50)
curl http://localhost:5055/notes/list

# List notes from specific folder
curl "http://localhost:5055/notes/list?folder=Work&limit=100"
```

**Note**: Body content is truncated to 500 characters in list view. Use GET /notes/note/{id} to retrieve full content.

---

### GET /notes/note/{note_id}

**Description**: Get a single note by ID with full content

**Path Parameters**:
- `note_id`: The x-coredata URL identifier for the note

**Response**: `Note`
```json
{
  "id": "x-coredata://ABC123/Note/p456",
  "name": "Meeting Notes - Q4 Planning",
  "body": "<html><body><div>Full HTML content of the note...</div></body></html>",
  "folder": "Work",
  "creation_date": "Monday, December 11, 2023 at 2:30:00 PM",
  "modification_date": "Monday, December 11, 2023 at 4:15:00 PM"
}
```

**Status Codes**:
- `200 OK` - Successfully retrieved note
- `404 Not Found` - Note ID does not exist
- `500 Internal Server Error` - AppleScript execution failed

**Example**:
```bash
curl "http://localhost:5055/notes/note/x-coredata%3A%2F%2FABC123%2FNote%2Fp456"
```

**Note**: The body contains full HTML content as stored by Notes.app.

---

### POST /notes/search

**Description**: Search notes by text content (case-insensitive)

**Request Body**: `NoteSearchRequest`
```json
{
  "query": "meeting",
  "folder": "Work"
}
```

**Request Fields**:
- `query` (required): Search term to find in note titles and bodies
- `folder` (optional): Limit search to specific folder

**Response**: `NoteSearchResponse`
```json
{
  "results": [
    {
      "id": "x-coredata://ABC123/Note/p456",
      "name": "Meeting Notes - Q4 Planning",
      "body": "Discussed goals for Q4...",
      "folder": "Work",
      "creation_date": "Monday, December 11, 2023 at 2:30:00 PM",
      "modification_date": "Monday, December 11, 2023 at 4:15:00 PM"
    }
  ],
  "query": "meeting",
  "result_count": 23
}
```

**Status Codes**:
- `200 OK` - Search completed (even if 0 results)
- `500 Internal Server Error` - AppleScript execution failed

**Example**:
```bash
curl -X POST http://localhost:5055/notes/search \
  -H "Content-Type: application/json" \
  -d '{"query": "meeting", "folder": "Work"}'
```

**Implementation**:
- Retrieves all notes (or notes in folder if specified)
- Performs case-insensitive string matching on name and body
- Body content truncated to 300 characters in results

**Performance Note**: Search is implemented in AppleScript by iterating all notes. For large note collections (>1000 notes), searches may take several seconds. Future optimization could use Spotlight/mdfind.

---

## Data Models

### Note
```python
class Note(BaseModel):
    id: str                     # x-coredata URL identifier
    name: str                   # Note title
    body: str                   # HTML content (may be truncated in lists)
    folder: str                 # Parent folder name
    creation_date: str | None   # Human-readable creation date
    modification_date: str | None  # Human-readable modification date
```

### NotesFolder
```python
class NotesFolder(BaseModel):
    name: str          # Folder name
    note_count: int    # Number of notes in folder
```

### NotesListResponse
```python
class NotesListResponse(BaseModel):
    notes: List[Note]       # Array of notes (body truncated to 500 chars)
    total_count: int        # Total notes in Notes.app
    folder: str | None      # Filter folder if specified
```

### NotesFolderListResponse
```python
class NotesFolderListResponse(BaseModel):
    folders: List[NotesFolder]  # Array of folders with counts
    total_folders: int          # Total number of folders
    total_notes: int            # Total notes across all folders
```

### NoteSearchRequest
```python
class NoteSearchRequest(BaseModel):
    query: str           # Search term (case-insensitive)
    folder: str | None   # Optional folder filter
```

### NoteSearchResponse
```python
class NoteSearchResponse(BaseModel):
    results: List[Note]  # Matching notes (body truncated to 300 chars)
    query: str           # Original search query
    result_count: int    # Number of results found
```

---

## AppleScript Integration

### Architecture

All Notes.app access goes through AppleScript via `osascript` subprocess calls:

```python
def run_applescript(script: str) -> str:
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True,
        timeout=30
    )
    return result.stdout.strip()
```

### Timeout Handling
- Default timeout: 30 seconds
- Applies to all AppleScript operations
- Large note collections may approach timeout on first load

### Data Serialization

AppleScript doesn't have native JSON support, so data is serialized using custom delimiters:

**Folder List**: `count:::total:::folder1:::count1|folder2:::count2|...`

**Note List**: Each note separated by `:::`, fields within note separated by `|||`:
```
noteId|||noteName|||noteBody|||noteFolder|||creationDate|||modDate:::...
```

**Delimiter Escaping**: Content containing delimiters is sanitized (replaced with spaces).

### Permission Requirements

**First Run**: macOS will prompt for Accessibility permissions:
1. System Settings → Privacy & Security → Automation
2. Allow Terminal/Python to control Notes.app

**Without Permission**: All endpoints return 500 errors with "operation not permitted" messages.

---

## Frontend Integration

**UI Location**: `ui/src/pages/Workflows.tsx` (Notes.app Integration section)

**API Client** (`ui/src/lib/api.ts`):
```typescript
export async function getNotesFolders(): Promise<NotesFolderListResponse>
export async function listNotes(folder?: string, limit?: number): Promise<NotesListResponse>
export async function getNote(noteId: string): Promise<Note>
export async function searchNotes(request: NoteSearchRequest): Promise<NoteSearchResponse>
```

**Usage Example**:
```typescript
// Load folders
const folders = await getNotesFolders();
console.log(`${folders.total_folders} folders with ${folders.total_notes} notes`);

// List notes from specific folder
const notes = await listNotes("Work", 50);
console.log(`Loaded ${notes.notes.length} notes`);

// Search notes
const results = await searchNotes({ query: "meeting", folder: "Work" });
console.log(`Found ${results.result_count} notes`);

// View full note
const note = await getNote(noteId);
console.log(note.body); // Full HTML content
```

---

## UI Features

### Folder Browser
- Load all folders with note counts
- Filter notes by folder with clickable buttons
- "All Notes" option to view across folders

### Search Interface
- Text input with Enter key support
- Search across all notes or within selected folder
- Results display with preview snippets

### Notes List
- Scrollable list with hover effects
- Shows: title, folder, modification date, preview
- Click to open full note viewer

### Note Viewer
- Full HTML content rendering
- Metadata display (folder, dates)
- Close button to return to list

### Loading States
- Disabled buttons during operations
- "Loading notes..." message
- Toast notifications for success/errors

---

## Error Handling

### Common Errors

**AppleScript Permission Denied** (500):
```json
{
  "detail": "AppleScript failed: operation not permitted"
}
```
**Fix**: Grant Automation permission in System Settings

**AppleScript Timeout** (500):
```json
{
  "detail": "AppleScript execution timed out"
}
```
**Fix**: Reduce query size or increase timeout

**Note Not Found** (404):
```json
{
  "detail": "Note not found: x-coredata://..."
}
```
**Fix**: Note may have been deleted; refresh folder list

### Handling in Frontend
```typescript
try {
  const notes = await listNotes("Work");
  toast.success(`Loaded ${notes.notes.length} notes`);
} catch (err) {
  toast.error(`Failed to load notes: ${err.message}`);
}
```

---

## Performance Considerations

### Retrieval Speed
- **Folders**: ~1-2 seconds for 200 folders
- **List 50 notes**: ~2-3 seconds
- **Search all notes**: ~5-10 seconds for 1000+ notes
- **Single note**: <1 second

### Optimization Strategies
1. **Limit results**: Use `limit` parameter (default: 50, max: 500)
2. **Filter by folder**: Reduces search space significantly
3. **Cache folder list**: Folders rarely change, cache client-side
4. **Pagination**: For large result sets, implement offset/limit pattern

### Future Improvements
- **Spotlight integration**: Use `mdfind` for faster full-text search
- **Incremental loading**: Lazy load note bodies on demand
- **WebSocket streaming**: Stream results as they're found
- **Background indexing**: Pre-cache note metadata

---

## Security Considerations

1. **No authentication** - Assumes localhost-only access
2. **HTML injection risk** - Note bodies contain HTML, rendered with `dangerouslySetInnerHTML`
3. **Note ID exposure** - x-coredata URLs may leak internal database structure
4. **AppleScript execution** - Fixed scripts only, no user input in scripts

**Production Recommendations**:
- Add authentication/authorization
- Sanitize HTML content before rendering
- Rate limit search endpoints
- Audit log all Notes.app access
- Restrict to read-only operations (no create/update/delete)

---

## Limitations

1. **Read-Only**: Cannot create, edit, or delete notes
2. **No Attachments**: Images and attachments not accessible via this API
3. **HTML Only**: Note formatting is Apple's HTML representation
4. **Case-Insensitive Search**: No regex or advanced query syntax
5. **Full Text Search**: Must load all notes, no indexed search
6. **macOS Only**: AppleScript requires macOS with Notes.app

---

## Testing

### Manual API Tests
```bash
# Get all folders
curl http://localhost:5055/notes/folders | jq

# List notes from specific folder
curl "http://localhost:5055/notes/list?folder=Work&limit=10" | jq

# Get single note (replace with real ID)
curl "http://localhost:5055/notes/note/x-coredata://..." | jq

# Search notes
curl -X POST http://localhost:5055/notes/search \
  -H "Content-Type: application/json" \
  -d '{"query":"meeting"}' | jq
```

### UI Testing
1. Open http://localhost:5173/workflows
2. Scroll to "Notes.app Integration" section
3. Click "📂 Load Folders"
4. Click on folder buttons to filter notes
5. Enter search query and click "🔍 Search"
6. Click on a note to view full content
7. Verify all UI states and error handling

---

## Version History

- **v1.0.0** (2025-12-11): Initial implementation
  - AppleScript-based Notes.app access
  - Folder browsing and note listing
  - Full-text search functionality
  - HTML note viewer
  - Frontend UI integration in Workflows page

---

## See Also

- `System/Scripts/RAG/routes/SERVICES_API.md` - Service management API
- `System/Scripts/Workflows/CLAUDE.md` - Workflows system
- `ui/src/pages/Workflows.tsx` - Frontend implementation
- `ui/src/lib/api.ts` - API client functions
