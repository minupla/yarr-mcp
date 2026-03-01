"""
MCP Server for Audiobookshelf
Implements tools for browsing libraries, tracking playback progress,
and viewing listening statistics.
Built with FastMCP following best practices from gofastmcp.com
"""

import os
import sys
import time
import httpx
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from dotenv import load_dotenv
from fastmcp import FastMCP

# --- Constants ---
SCRIPT_DIR = Path(__file__).resolve().parent

# --- Environment Variable & .env Loading ---
project_root = SCRIPT_DIR.parent.parent
env_path = project_root / '.env'

print(f"AudiobookshelfMCP: Looking for .env file at: {env_path}")
found_dotenv = load_dotenv(dotenv_path=env_path, override=False)
print(f"AudiobookshelfMCP: load_dotenv found file: {found_dotenv}")

# Also load server-specific .env if present
mcp_server_env_path = SCRIPT_DIR / '.env'
if mcp_server_env_path.exists() and mcp_server_env_path != env_path:
    load_dotenv(dotenv_path=mcp_server_env_path, override=True)

ABS_URL = os.getenv('ABS_URL')
ABS_TOKEN = os.getenv('ABS_TOKEN')

# --- MCP Server Configuration ---
ABS_MCP_LOG_LEVEL = os.getenv('ABS_MCP_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
ABS_MCP_TRANSPORT = os.getenv('ABS_MCP_TRANSPORT', 'sse').lower()
ABS_MCP_HOST = os.getenv('ABS_MCP_HOST', '0.0.0.0')
ABS_MCP_PORT = int(os.getenv('ABS_MCP_PORT', '6977'))

NUMERIC_LOG_LEVEL = getattr(logging, ABS_MCP_LOG_LEVEL, logging.INFO)

# --- Logging Setup ---
logger = logging.getLogger("AudiobookshelfMCPServer")
logger.setLevel(NUMERIC_LOG_LEVEL)
logger.propagate = False

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NUMERIC_LOG_LEVEL)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

log_file_path = SCRIPT_DIR / "audiobookshelf_mcp.log"
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(NUMERIC_LOG_LEVEL)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s'))
logger.addHandler(file_handler)

logger.info(f"Logging initialized. Log level: {ABS_MCP_LOG_LEVEL}")
logger.info(f"Audiobookshelf MCP Transport: {ABS_MCP_TRANSPORT}, Host: {ABS_MCP_HOST}, Port: {ABS_MCP_PORT}")

if not ABS_URL or not ABS_TOKEN:
    if __name__ == "__main__":
        logger.error("ABS_URL and ABS_TOKEN environment variables must be set.")
        sys.exit(1)
    else:
        logger.warning("ABS_URL or ABS_TOKEN not set. Tools will fail at runtime.")

if ABS_URL and ABS_URL.endswith('/'):
    ABS_URL = ABS_URL[:-1]

if ABS_URL and ABS_TOKEN:
    logger.info(f"Audiobookshelf URL: {ABS_URL}")
    logger.info(f"Audiobookshelf Token: {'*' * (len(ABS_TOKEN) - 4) + ABS_TOKEN[-4:] if len(ABS_TOKEN) > 4 else '****'}")

# --- FastMCP Server Initialization ---
mcp = FastMCP(
    name="Audiobookshelf MCP Server",
    instructions="""Provides tools to interact with an Audiobookshelf instance.
Browse libraries, search for audiobooks, track and update playback progress,
and view listening statistics.
Requires ABS_URL and ABS_TOKEN environment variables.
The progress/sync tools are the key feature — they enable syncing playback
position from external players."""
)

# --- Helper Function ---
async def _abs_api_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], List[Any], None]:
    """Helper function to make requests to the Audiobookshelf API."""
    headers = {
        'Authorization': f'Bearer {ABS_TOKEN}',
        'Content-Type': 'application/json'
    }
    url = f"{ABS_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
            logger.debug(f"Request: {method} {url} - Params: {params} - Body: {json_body}")
            response = await client.request(method, url, params=params, json=json_body, headers=headers)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            # Some endpoints return empty body on success
            if not response.content:
                return None
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling Audiobookshelf API: {e.response.status_code} - {e.response.text}")
        error_content = {"error": f"Audiobookshelf API Error: {e.response.status_code}", "details": e.response.text}
        try:
            error_content["details"] = e.response.json()
        except Exception:
            pass
        return error_content
    except httpx.RequestError as e:
        logger.error(f"Request error calling Audiobookshelf API: {e}")
        return {"error": f"Request to Audiobookshelf API failed: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error in Audiobookshelf API request: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}


def _format_duration(seconds: Optional[float]) -> str:
    """Format seconds into human-readable duration."""
    if seconds is None or seconds == 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# --- Library Browsing Tools ---

@mcp.tool()
async def get_libraries() -> Dict[str, Any]:
    """
    List all libraries on the Audiobookshelf server.
    Returns library id, name, and mediaType for each library.
    """
    logger.info("Listing all libraries...")
    response = await _abs_api_request("GET", "/api/libraries")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "libraries" in response:
        libraries = response["libraries"]
        summary = f"Found {len(libraries)} libraries."
        lib_list = []
        for lib in libraries:
            lib_list.append({
                "id": lib.get("id"),
                "name": lib.get("name"),
                "mediaType": lib.get("mediaType"),
                "numItems": lib.get("stats", {}).get("totalItems", "N/A")
            })
            summary += f"\n  - {lib.get('name')} ({lib.get('mediaType')}, ID: {lib.get('id')})"
        return {"summary": summary, "libraries": lib_list}

    # Some API versions return a list directly
    if isinstance(response, list):
        summary = f"Found {len(response)} libraries."
        lib_list = []
        for lib in response:
            lib_list.append({
                "id": lib.get("id"),
                "name": lib.get("name"),
                "mediaType": lib.get("mediaType"),
            })
            summary += f"\n  - {lib.get('name')} ({lib.get('mediaType')}, ID: {lib.get('id')})"
        return {"summary": summary, "libraries": lib_list}

    return {"error": "Unexpected response format from get_libraries."}


@mcp.tool()
async def get_library_items(
    library_id: str,
    limit: int = 50,
    page: int = 0
) -> Dict[str, Any]:
    """
    List items in a specific library with pagination.
    Returns title, author, duration, and progress for each item.

    Args:
        library_id: The ID of the library to browse.
        limit: Number of items per page (default 50).
        page: Page number, 0-indexed (default 0).
    """
    logger.info(f"Getting items for library {library_id}, page={page}, limit={limit}")
    response = await _abs_api_request("GET", f"/api/libraries/{library_id}/items", params={
        "limit": limit,
        "page": page
    })

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "results" in response:
        results = response["results"]
        total = response.get("total", len(results))
        summary = f"Library items: showing {len(results)} of {total} (page {page})."

        items = []
        for item in results:
            media = item.get("media", {})
            metadata = media.get("metadata", {})
            progress_data = item.get("userMediaProgress")

            condensed = {
                "id": item.get("id"),
                "ino": item.get("ino"),
                "mediaType": item.get("mediaType"),
                "title": metadata.get("title"),
                "subtitle": metadata.get("subtitle"),
                "authorName": metadata.get("authorName"),
                "seriesName": metadata.get("seriesName"),
                "publishedYear": metadata.get("publishedYear"),
                "duration": media.get("duration"),
                "numTracks": media.get("numTracks"),
            }
            if progress_data:
                condensed["currentTime"] = progress_data.get("currentTime")
                condensed["progress"] = progress_data.get("progress")
                condensed["isFinished"] = progress_data.get("isFinished")

            items.append(condensed)
            progress_pct = f"{progress_data['progress'] * 100:.1f}%" if progress_data else "not started"
            summary += f"\n  - {metadata.get('title', 'Unknown')} by {metadata.get('authorName', 'Unknown')} ({_format_duration(media.get('duration', 0))}) [{progress_pct}]"

        return {"summary": summary, "items": items, "total": total, "page": page, "limit": limit}

    return {"error": "Unexpected response format from get_library_items."}


@mcp.tool()
async def search_library(library_id: str, query: str) -> Dict[str, Any]:
    """
    Search a library by title or author.

    Args:
        library_id: The ID of the library to search.
        query: Search query string.
    """
    logger.info(f"Searching library {library_id} for '{query}'")
    response = await _abs_api_request("GET", f"/api/libraries/{library_id}/search", params={"q": query})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        book_results = response.get("book", response.get("libraryItems", []))
        if isinstance(book_results, list):
            summary = f"Found {len(book_results)} results for '{query}'."
            items = []
            for result in book_results[:10]:
                # Search results may wrap items in a "libraryItem" key
                item = result.get("libraryItem", result)
                media = item.get("media", {})
                metadata = media.get("metadata", {})
                items.append({
                    "id": item.get("id"),
                    "title": metadata.get("title", "Unknown"),
                    "author": metadata.get("authorName", "Unknown"),
                    "duration": _format_duration(media.get("duration", 0))
                })
                summary += f"\n  - {metadata.get('title', 'Unknown')} by {metadata.get('authorName', 'Unknown')}"
            return {"summary": summary, "results": items}

    return {"error": "Unexpected response format from search_library.", "raw": str(response)[:500]}


@mcp.tool()
async def get_item(item_id: str) -> Dict[str, Any]:
    """
    Get full details for a specific library item, including chapters.

    Args:
        item_id: The ID of the item to retrieve.
    """
    logger.info(f"Getting details for item {item_id}")
    response = await _abs_api_request("GET", f"/api/items/{item_id}")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        media = response.get("media", {})
        metadata = media.get("metadata", {})
        chapters = media.get("chapters", [])
        progress_data = response.get("userMediaProgress")

        chapter_list = []
        for ch in chapters:
            chapter_list.append({
                "id": ch.get("id"),
                "title": ch.get("title", "Untitled"),
                "start": _format_duration(ch.get("start", 0)),
                "end": _format_duration(ch.get("end", 0))
            })

        result = {
            "id": response.get("id"),
            "title": metadata.get("title", "Unknown"),
            "author": metadata.get("authorName", "Unknown"),
            "narrator": metadata.get("narratorName", "Unknown"),
            "description": metadata.get("description", ""),
            "duration": _format_duration(media.get("duration", 0)),
            "durationSeconds": media.get("duration", 0),
            "chapters": chapter_list,
            "numChapters": len(chapters),
        }

        if progress_data:
            result["progress"] = {
                "currentTime": progress_data.get("currentTime", 0),
                "progress": f"{progress_data.get('progress', 0) * 100:.1f}%",
                "isFinished": progress_data.get("isFinished", False),
            }

        summary = (
            f"{result['title']} by {result['author']}\n"
            f"Narrator: {result['narrator']}\n"
            f"Duration: {result['duration']} ({result['numChapters']} chapters)"
        )
        if progress_data:
            summary += f"\nProgress: {result['progress']['progress']} (at {_format_duration(progress_data.get('currentTime', 0))})"

        return {"summary": summary, "item": result}

    return {"error": "Unexpected response format from get_item."}


# --- Progress / Playback Position Tools ---

@mcp.tool()
async def get_progress(item_id: str) -> Dict[str, Any]:
    """
    Get current playback progress for a specific item.
    Returns currentTime, duration, progress percentage, isFinished, and lastUpdate.

    Args:
        item_id: The ID of the library item.
    """
    logger.info(f"Getting progress for item {item_id}")
    response = await _abs_api_request("GET", f"/api/me/progress/{item_id}")

    if isinstance(response, dict) and "error" in response:
        return response

    if response is None:
        return {"summary": "No progress found for this item.", "progress": None}

    if isinstance(response, dict):
        current_time = response.get("currentTime", 0)
        duration = response.get("duration", 0)
        progress = response.get("progress", 0)
        is_finished = response.get("isFinished", False)
        last_update = response.get("lastUpdate")

        summary = (
            f"Position: {_format_duration(current_time)} / {_format_duration(duration)} "
            f"({progress * 100:.1f}%)"
        )
        if is_finished:
            summary += " [FINISHED]"
        if last_update:
            summary += f"\nLast updated: {last_update}"

        return {
            "summary": summary,
            "progress": {
                "currentTime": current_time,
                "duration": duration,
                "progress": progress,
                "isFinished": is_finished,
                "lastUpdate": last_update,
                "currentTimeFormatted": _format_duration(current_time),
                "durationFormatted": _format_duration(duration),
            }
        }

    return {"error": "Unexpected response format from get_progress."}


@mcp.tool()
async def update_progress(
    item_id: str,
    current_time: float,
    duration: float,
    is_finished: bool = False
) -> Dict[str, Any]:
    """
    Update playback position for a library item. This is the key tool for syncing
    progress from external players (e.g., Listen audiobook player on Android).

    Args:
        item_id: The ID of the library item.
        current_time: Current playback position in seconds.
        duration: Total duration of the item in seconds.
        is_finished: Whether the item has been completed (default False).
    """
    logger.info(f"Updating progress for item {item_id}: currentTime={current_time}, duration={duration}, isFinished={is_finished}")

    progress = current_time / duration if duration > 0 else 0.0
    last_update = int(time.time() * 1000)  # epoch milliseconds

    body = {
        "currentTime": current_time,
        "duration": duration,
        "progress": progress,
        "isFinished": is_finished,
        "lastUpdate": last_update
    }

    response = await _abs_api_request("PATCH", f"/api/me/progress/{item_id}", json_body=body)

    if isinstance(response, dict) and "error" in response:
        return response

    # Success — PATCH may return empty or updated progress
    summary = (
        f"Progress updated for item {item_id}:\n"
        f"  Position: {_format_duration(current_time)} / {_format_duration(duration)} ({progress * 100:.1f}%)\n"
        f"  Finished: {is_finished}"
    )
    return {"summary": summary, "status": "success", "updated": body}


@mcp.tool()
async def get_all_progress() -> Dict[str, Any]:
    """
    Get all items currently in progress (being listened to).
    Returns each item with its current playback position.
    """
    logger.info("Getting all in-progress items...")
    response = await _abs_api_request("GET", "/api/me/items-in-progress")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "libraryItems" in response:
        items = response["libraryItems"]
        summary = f"Found {len(items)} items in progress."
        result_items = []
        for item in items:
            media = item.get("media", {})
            metadata = media.get("metadata", {})
            progress_data = item.get("userMediaProgress", item.get("progressLastUpdate", {}))

            entry = {
                "id": item.get("id"),
                "title": metadata.get("title", "Unknown"),
                "author": metadata.get("authorName", "Unknown"),
            }
            if isinstance(progress_data, dict):
                entry["currentTime"] = _format_duration(progress_data.get("currentTime", 0))
                entry["progress"] = f"{progress_data.get('progress', 0) * 100:.1f}%"
                entry["isFinished"] = progress_data.get("isFinished", False)

            result_items.append(entry)
            summary += f"\n  - {entry['title']} by {entry.get('author', '?')} [{entry.get('progress', '?')}]"

        return {"summary": summary, "items": result_items}

    # Handle list response
    if isinstance(response, list):
        summary = f"Found {len(response)} items in progress."
        return {"summary": summary, "items": response}

    return {"error": "Unexpected response format from get_all_progress."}


# --- Listening Sessions & Stats Tools ---

@mcp.tool()
async def get_listening_sessions(items_per_page: int = 50) -> Dict[str, Any]:
    """
    Get recent listening sessions for the authenticated user.

    Args:
        items_per_page: Number of sessions to return (default 50).
    """
    logger.info(f"Getting listening sessions (limit {items_per_page})...")
    response = await _abs_api_request("GET", "/api/me/listening-sessions", params={
        "itemsPerPage": items_per_page
    })

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "sessions" in response:
        sessions = response["sessions"]
        total = response.get("total", len(sessions))
        summary = f"Found {total} listening sessions."

        session_list = []
        for s in sessions[:15]:
            media_metadata = s.get("mediaMetadata", {})
            session_list.append({
                "id": s.get("id"),
                "title": media_metadata.get("title", "Unknown"),
                "author": media_metadata.get("authorName", "Unknown"),
                "duration": _format_duration(s.get("timeListening", 0)),
                "date": s.get("updatedAt", s.get("startedAt", "Unknown")),
                "currentTime": _format_duration(s.get("currentTime", 0)),
            })
            summary += f"\n  - {media_metadata.get('title', '?')}: listened {_format_duration(s.get('timeListening', 0))}"

        return {"summary": summary, "sessions": session_list, "total": total}

    return {"error": "Unexpected response format from get_listening_sessions."}


@mcp.tool()
async def get_listening_stats() -> Dict[str, Any]:
    """
    Get listening statistics for the authenticated user.
    Includes total listen time, books finished, and other stats.
    """
    logger.info("Getting listening stats...")
    response = await _abs_api_request("GET", "/api/me/listening-stats")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        total_time = response.get("totalTime", 0)
        items_finished = response.get("itemsFinished", response.get("booksFinished", 0))
        days_listening = response.get("days", {})

        summary = (
            f"Total listening time: {_format_duration(total_time)}\n"
            f"Items finished: {items_finished}"
        )

        if isinstance(days_listening, dict) and days_listening:
            summary += f"\nDays with listening activity: {len(days_listening)}"

        stats = {
            "totalTime": total_time,
            "totalTimeFormatted": _format_duration(total_time),
            "itemsFinished": items_finished,
            "daysListening": len(days_listening) if isinstance(days_listening, dict) else 0,
        }

        # Include per-author stats if available
        authors = response.get("authorsListening", response.get("authorStats", {}))
        if authors:
            stats["topAuthors"] = authors
            summary += f"\nAuthors listened to: {len(authors)}"

        return {"summary": summary, "stats": stats}

    return {"error": "Unexpected response format from get_listening_stats."}


@mcp.tool()
async def get_in_progress() -> Dict[str, Any]:
    """
    Get all items currently being listened to (shorthand for items-in-progress).
    Convenient way to see what's currently being read/listened to.
    """
    # This is the same endpoint as get_all_progress — just an alias for discoverability
    return await get_all_progress()


# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Audiobookshelf MCP Server...")

    if ABS_MCP_TRANSPORT == 'sse':
        mcp.run(
            transport='sse',
            host=ABS_MCP_HOST,
            port=ABS_MCP_PORT,
            path='/mcp'
        )
    elif ABS_MCP_TRANSPORT == 'stdio':
        mcp.run()
    else:
        logger.error(f"Invalid ABS_MCP_TRANSPORT: '{ABS_MCP_TRANSPORT}'. Defaulting to STDIO.")
        mcp.run()
