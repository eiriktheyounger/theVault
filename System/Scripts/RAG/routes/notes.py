"""Notes.app integration API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import subprocess
import json
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])


class Note(BaseModel):
    """A single note from Notes.app"""
    id: str
    name: str
    body: str
    folder: str
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None


class NotesFolder(BaseModel):
    """A folder in Notes.app"""
    name: str
    note_count: int


class NotesListResponse(BaseModel):
    """Response for listing notes"""
    notes: List[Note]
    total_count: int
    folder: Optional[str] = None


class NotesFolderListResponse(BaseModel):
    """Response for listing folders"""
    folders: List[NotesFolder]
    total_folders: int
    total_notes: int


class NoteSearchRequest(BaseModel):
    """Request for searching notes"""
    query: str
    folder: Optional[str] = None


class NoteSearchResponse(BaseModel):
    """Response for searching notes"""
    results: List[Note]
    query: str
    result_count: int


def run_applescript(script: str) -> str:
    """Execute AppleScript and return result."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.error(f"AppleScript error: {result.stderr}")
            raise Exception(f"AppleScript failed: {result.stderr}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("AppleScript timed out")
        raise Exception("AppleScript execution timed out")
    except Exception as e:
        logger.error(f"AppleScript execution error: {e}")
        raise


@router.get("/folders", response_model=NotesFolderListResponse)
async def get_folders():
    """Get all folders from Notes.app with note counts."""
    logger.info("Retrieving Notes.app folders")

    script = '''
    tell application "Notes"
        set folderList to {}
        set totalNotes to count of notes
        repeat with aFolder in folders
            set folderName to name of aFolder
            set noteCount to count of notes in aFolder
            set end of folderList to {folderName:folderName, noteCount:noteCount}
        end repeat

        set AppleScript's text item delimiters to "|"
        set folderJSON to ""
        repeat with folderInfo in folderList
            set folderName to folderName of folderInfo
            set noteCount to noteCount of folderInfo
            set folderJSON to folderJSON & folderName & ":::" & noteCount & "|"
        end repeat

        return (count of folderList) & ":::" & totalNotes & ":::" & folderJSON
    end tell
    '''

    try:
        output = run_applescript(script)
        parts = output.split(":::")
        folder_count = int(parts[0])
        total_notes = int(parts[1])
        folder_data = parts[2].rstrip("|").split("|") if len(parts) > 2 and parts[2] else []

        folders = []
        for folder_str in folder_data:
            if folder_str:
                folder_parts = folder_str.split(":::")
                if len(folder_parts) == 2:
                    folders.append(NotesFolder(
                        name=folder_parts[0],
                        note_count=int(folder_parts[1])
                    ))

        return NotesFolderListResponse(
            folders=folders,
            total_folders=folder_count,
            total_notes=total_notes
        )
    except Exception as e:
        logger.error(f"Failed to get folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=NotesListResponse)
async def list_notes(
    folder: Optional[str] = Query(None, description="Filter by folder name"),
    limit: int = Query(50, description="Maximum number of notes to return", ge=1, le=500)
):
    """List notes from Notes.app, optionally filtered by folder."""
    logger.info(f"Listing notes (folder={folder}, limit={limit})")

    if folder:
        script = f'''
        tell application "Notes"
            set targetFolder to folder "{folder}"
            set noteList to notes in targetFolder
            set noteCount to count of noteList

            set output to ""
            set counter to 0
            repeat with aNote in noteList
                if counter >= {limit} then exit repeat
                set noteId to id of aNote
                set noteName to name of aNote
                set noteBody to body of aNote
                set noteFolder to name of container of aNote
                set creationDate to creation date of aNote as string
                set modDate to modification date of aNote as string

                -- Escape delimiters in content
                set noteName to my replaceText(noteName, "|||", " ")
                set noteBody to my replaceText(noteBody, "|||", " ")
                set noteFolder to my replaceText(noteFolder, "|||", " ")

                set output to output & noteId & "|||" & noteName & "|||" & noteBody & "|||" & noteFolder & "|||" & creationDate & "|||" & modDate & ":::"
                set counter to counter + 1
            end repeat

            return (noteCount as string) & "||" & output
        end tell

        on replaceText(theText, oldDelim, newDelim)
            set AppleScript's text item delimiters to oldDelim
            set textItems to text items of theText
            set AppleScript's text item delimiters to newDelim
            set newText to textItems as string
            set AppleScript's text item delimiters to ""
            return newText
        end replaceText
        '''
    else:
        script = f'''
        tell application "Notes"
            set noteList to notes
            set noteCount to count of noteList

            set output to ""
            set counter to 0
            repeat with aNote in noteList
                if counter >= {limit} then exit repeat
                set noteId to id of aNote
                set noteName to name of aNote
                set noteBody to body of aNote
                set noteFolder to name of container of aNote
                set creationDate to creation date of aNote as string
                set modDate to modification date of aNote as string

                -- Escape delimiters in content
                set noteName to my replaceText(noteName, "|||", " ")
                set noteBody to my replaceText(noteBody, "|||", " ")
                set noteFolder to my replaceText(noteFolder, "|||", " ")

                set output to output & noteId & "|||" & noteName & "|||" & noteBody & "|||" & noteFolder & "|||" & creationDate & "|||" & modDate & ":::"
                set counter to counter + 1
            end repeat

            return (noteCount as string) & "||" & output
        end tell

        on replaceText(theText, oldDelim, newDelim)
            set AppleScript's text item delimiters to oldDelim
            set textItems to text items of theText
            set AppleScript's text item delimiters to newDelim
            set newText to textItems as string
            set AppleScript's text item delimiters to ""
            return newText
        end replaceText
        '''

    try:
        output = run_applescript(script)
        parts = output.split("||")
        total_count = int(parts[0])
        note_data = parts[1].rstrip(":::").split(":::") if len(parts) > 1 and parts[1] else []

        notes = []
        for note_str in note_data:
            if note_str:
                note_parts = note_str.split("|||")
                if len(note_parts) == 6:
                    # Truncate body to first 500 chars for list view
                    body = note_parts[2][:500] + "..." if len(note_parts[2]) > 500 else note_parts[2]
                    notes.append(Note(
                        id=note_parts[0],
                        name=note_parts[1],
                        body=body,
                        folder=note_parts[3],
                        creation_date=note_parts[4],
                        modification_date=note_parts[5]
                    ))

        return NotesListResponse(
            notes=notes,
            total_count=total_count,
            folder=folder
        )
    except Exception as e:
        logger.error(f"Failed to list notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/note/{note_id}", response_model=Note)
async def get_note(note_id: str):
    """Get a single note by ID with full content."""
    logger.info(f"Retrieving note {note_id}")

    script = f'''
    tell application "Notes"
        set targetNote to note id "{note_id}"
        set noteId to id of targetNote
        set noteName to name of targetNote
        set noteBody to body of targetNote
        set noteFolder to name of container of targetNote
        set creationDate to creation date of targetNote as string
        set modDate to modification date of targetNote as string

        return noteId & "|||" & noteName & "|||" & noteBody & "|||" & noteFolder & "|||" & creationDate & "|||" & modDate
    end tell
    '''

    try:
        output = run_applescript(script)
        parts = output.split("|||")

        if len(parts) != 6:
            raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")

        return Note(
            id=parts[0],
            name=parts[1],
            body=parts[2],
            folder=parts[3],
            creation_date=parts[4],
            modification_date=parts[5]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=NoteSearchResponse)
async def search_notes(request: NoteSearchRequest):
    """Search notes by text content."""
    logger.info(f"Searching notes for: {request.query}")

    # AppleScript doesn't have great search, so we'll retrieve all notes and filter
    # For better performance, could use Spotlight/mdfind in future
    folder_filter = f'in folder "{request.folder}"' if request.folder else ""

    script = f'''
    tell application "Notes"
        set searchQuery to "{request.query}"
        set noteList to notes {folder_filter}

        set matchingNotes to {{}}
        repeat with aNote in noteList
            set noteName to name of aNote
            set noteBody to body of aNote

            -- Simple case-insensitive search
            if noteName contains searchQuery or noteBody contains searchQuery then
                set end of matchingNotes to aNote
            end if
        end repeat

        set output to ""
        repeat with aNote in matchingNotes
            set noteId to id of aNote
            set noteName to name of aNote
            set noteBody to body of aNote
            set noteFolder to name of container of aNote
            set creationDate to creation date of aNote as string
            set modDate to modification date of aNote as string

            -- Escape delimiters
            set noteName to my replaceText(noteName, "|||", " ")
            set noteBody to my replaceText(noteBody, "|||", " ")
            set noteFolder to my replaceText(noteFolder, "|||", " ")

            set output to output & noteId & "|||" & noteName & "|||" & noteBody & "|||" & noteFolder & "|||" & creationDate & "|||" & modDate & ":::"
        end repeat

        return (count of matchingNotes) & "||" & output
    end tell

    on replaceText(theText, oldDelim, newDelim)
        set AppleScript's text item delimiters to oldDelim
        set textItems to text items of theText
        set AppleScript's text item delimiters to newDelim
        set newText to textItems as string
        set AppleScript's text item delimiters to ""
        return newText
    end replaceText
    '''

    try:
        output = run_applescript(script)
        parts = output.split("||")
        result_count = int(parts[0])
        note_data = parts[1].rstrip(":::").split(":::") if len(parts) > 1 and parts[1] else []

        results = []
        for note_str in note_data:
            if note_str:
                note_parts = note_str.split("|||")
                if len(note_parts) == 6:
                    # Truncate body for search results
                    body = note_parts[2][:300] + "..." if len(note_parts[2]) > 300 else note_parts[2]
                    results.append(Note(
                        id=note_parts[0],
                        name=note_parts[1],
                        body=body,
                        folder=note_parts[3],
                        creation_date=note_parts[4],
                        modification_date=note_parts[5]
                    ))

        return NoteSearchResponse(
            results=results,
            query=request.query,
            result_count=result_count
        )
    except Exception as e:
        logger.error(f"Failed to search notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
