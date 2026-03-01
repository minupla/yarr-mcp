"""
MCP Server for Radarr
Implements tools for Radarr movie management using SSE transport.
Built with FastMCP following best practices from gofastmcp.com
Based on Radarr API v3
"""

import os
import sys
import httpx
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from dotenv import load_dotenv
from fastmcp import FastMCP

# --- Constants ---
API_VERSION = "v3"

# --- Logging Setup ---
RADARR_MCP_LOG_LEVEL = os.getenv('RADARR_MCP_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
RADARR_MCP_LOG_FILE = os.getenv('RADARR_MCP_LOG_FILE', "radarr_mcp.log")
RADARR_MCP_TRANSPORT = os.getenv('RADARR_MCP_TRANSPORT', 'sse').lower()
RADARR_MCP_HOST = os.getenv('RADARR_MCP_HOST', '0.0.0.0')
RADARR_MCP_PORT = int(os.getenv('RADARR_MCP_PORT', '6975'))

NUMERIC_LOG_LEVEL = getattr(logging, RADARR_MCP_LOG_LEVEL, logging.INFO)
SCRIPT_DIR = Path(__file__).resolve().parent

# --- Environment Variable & API Client Setup ---
project_root = SCRIPT_DIR.parent.parent
env_path = project_root / '.env'

print(f"RadarrMCP: Looking for .env file at: {env_path}")
found_dotenv = load_dotenv(dotenv_path=env_path, override=False)
print(f"RadarrMCP: load_dotenv found file: {found_dotenv}")

RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')

logger = logging.getLogger("RadarrMCPServer")
logger.setLevel(NUMERIC_LOG_LEVEL)
logger.propagate = False

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NUMERIC_LOG_LEVEL)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File Handler
log_file_path = SCRIPT_DIR / RADARR_MCP_LOG_FILE
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(NUMERIC_LOG_LEVEL)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging initialized (console and file: {log_file_path}). Log level: {RADARR_MCP_LOG_LEVEL}")
logger.info(f"Radarr MCP Transport: {RADARR_MCP_TRANSPORT}, Host: {RADARR_MCP_HOST}, Port: {RADARR_MCP_PORT}")

if not RADARR_URL or not RADARR_API_KEY:
    if __name__ == "__main__":
        logger.error("RADARR_URL and RADARR_API_KEY environment variables must be set.")
        sys.exit(1)
    else:
        logger.warning("RADARR_URL or RADARR_API_KEY not set. Tools will fail at runtime.")

if RADARR_URL and RADARR_URL.endswith('/'):
    RADARR_URL = RADARR_URL[:-1]

if RADARR_URL and RADARR_API_KEY:
    logger.info(f"Radarr API URL: {RADARR_URL}")
    logger.info(f"Radarr API Key: {'*' * (len(RADARR_API_KEY) - 4) + RADARR_API_KEY[-4:]}")

# --- FastMCP Server Initialization ---
mcp = FastMCP(
    name="Radarr MCP Server",
    instructions="""Provides tools to interact with a Radarr instance.
Manages movies, quality profiles, and monitors download queues.
Requires RADARR_URL and RADARR_API_KEY environment variables.
API interactions are based on Radarr API v3."""
)

# --- Helper Functions ---
async def _radarr_api_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], List[Any], None]:
    """Helper function to make requests to the Radarr API."""
    headers = {'X-Api-Key': RADARR_API_KEY}
    url = f"{RADARR_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.debug(f"Request: {method} {url} - Params: {params} - Body: {json_body}")
            response = await client.request(method, url, params=params, json=json_body, headers=headers)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling Radarr API: {e.response.status_code} - {e.response.text}")
        error_content = {"error": f"Radarr API Error: {e.response.status_code}", "details": e.response.text}
        try:
            error_content["details"] = e.response.json()
        except Exception:
            pass
        return error_content
    except httpx.RequestError as e:
        logger.error(f"Request error calling Radarr API: {e}")
        return {"error": f"Request to Radarr API failed: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error in Radarr API request: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}

# --- Core Tools ---

@mcp.tool()
async def get_movies() -> Dict[str, Any]:
    """
    Retrieves a list of all movies in the Radarr library.
    Returns a summary and the full list of movie objects.
    """
    logger.info("Listing all movies...")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/movie")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        monitored = [m for m in response if m.get('monitored', False)]
        has_file = [m for m in response if m.get('hasFile', False)]
        summary = f"Found {len(response)} movies ({len(monitored)} monitored, {len(has_file)} downloaded)."
        if response:
            summary += " First few: " + ", ".join(
                [f"{m.get('title', 'N/A')} ({m.get('year', 'N/A')}, ID: {m.get('id', 'N/A')})"
                 for m in response[:5]]
            )
        condensed = [{
            "id": m.get("id"),
            "tmdbId": m.get("tmdbId"),
            "title": m.get("title"),
            "year": m.get("year"),
            "status": m.get("status"),
            "monitored": m.get("monitored"),
            "hasFile": m.get("hasFile"),
            "sizeOnDisk": m.get("sizeOnDisk"),
            "path": m.get("path"),
            "overview": (m.get("overview") or "")[:200],
            "genres": m.get("genres", []),
        } for m in response]
        return {"summary": summary, "movies": condensed}

    return {"error": "Failed to list movies due to unexpected API response."}


@mcp.tool()
async def lookup_movie(term: str) -> Dict[str, Any]:
    """
    Searches for movies on TMDB via Radarr.
    Returns matching movies with TMDB IDs for use with add_movie.
    """
    logger.info(f"Looking up movie: '{term}'")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/movie/lookup", params={"term": term})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} results for '{term}'."
        if response:
            summary += " Top results: " + ", ".join(
                [f"{m.get('title', 'N/A')} ({m.get('year', 'N/A')}, TMDB: {m.get('tmdbId', 'N/A')})"
                 for m in response[:5]]
            )
        condensed = [{
            "title": m.get("title"),
            "year": m.get("year"),
            "tmdbId": m.get("tmdbId"),
            "overview": (m.get("overview") or "")[:200],
            "status": m.get("status"),
            "studio": m.get("studio"),
        } for m in response]
        return {"summary": summary, "results": condensed}

    return {"error": "Failed to lookup movie due to unexpected API response."}


@mcp.tool()
async def add_movie(
    tmdb_id: int,
    title: str,
    quality_profile_id: int,
    root_folder_path: str,
    monitored: bool = True,
    search_for_movie: bool = True,
    minimum_availability: str = "released"
) -> Dict[str, Any]:
    """
    Adds a new movie to Radarr.
    Use lookup_movie to find the tmdb_id, and get_quality_profiles/get_root_folders for valid IDs/paths.
    minimum_availability options: announced, inCinemas, released, preDB
    """
    logger.info(f"Adding movie: '{title}' (TMDB: {tmdb_id})")

    # First lookup to get full movie data
    lookup = await _radarr_api_request("GET", f"/api/{API_VERSION}/movie/lookup/tmdb", params={"tmdbId": tmdb_id})
    if isinstance(lookup, dict) and "error" in lookup:
        return lookup
    if not isinstance(lookup, dict) or "title" not in lookup:
        return {"error": f"Could not find movie with TMDB ID {tmdb_id}"}

    movie_data = lookup
    movie_data.update({
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": monitored,
        "minimumAvailability": minimum_availability,
        "addOptions": {
            "searchForMovie": search_for_movie
        }
    })

    response = await _radarr_api_request("POST", f"/api/{API_VERSION}/movie", json_body=movie_data)

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "id" in response:
        return {"summary": f"Successfully added '{response.get('title', title)}' (ID: {response.get('id')}).", "movie": response}

    return {"error": "Failed to add movie due to unexpected API response."}


@mcp.tool()
async def get_queue() -> Dict[str, Any]:
    """
    Retrieves the current download queue from Radarr.
    Shows active downloads with progress information.
    """
    logger.info("Getting Radarr download queue...")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/queue", params={"pageSize": 100})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "records" in response:
        records = response.get("records", [])
        total = response.get("totalRecords", 0)
        summary = f"Queue has {total} items."
        if records:
            summary += " Active downloads:"
            for rec in records[:5]:
                title = rec.get("title", "N/A")
                status = rec.get("status", "N/A")
                sizeleft = rec.get("sizeleft", 0)
                size = rec.get("size", 0)
                pct = ((size - sizeleft) / size * 100) if size > 0 else 0
                summary += f"\n  - {title}: {status} ({pct:.1f}%)"
        return {"summary": summary, "queue": response}

    return {"error": "Failed to get queue due to unexpected API response."}


@mcp.tool()
async def get_quality_profiles() -> Dict[str, Any]:
    """
    Retrieves all quality profiles configured in Radarr.
    Use the returned IDs when adding movies.
    """
    logger.info("Getting Radarr quality profiles...")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/qualityprofile")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} quality profiles: " + ", ".join(
            [f"{p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')})" for p in response]
        )
        return {"summary": summary, "profiles": response}

    return {"error": "Failed to get quality profiles due to unexpected API response."}


@mcp.tool()
async def get_root_folders() -> Dict[str, Any]:
    """
    Retrieves all root folder paths configured in Radarr.
    Use the returned paths when adding movies.
    """
    logger.info("Getting Radarr root folders...")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/rootfolder")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} root folders: " + ", ".join(
            [f"{f.get('path', 'N/A')} (Free: {f.get('freeSpace', 0) / (1024**3):.1f} GB)" for f in response]
        )
        return {"summary": summary, "folders": response}

    return {"error": "Failed to get root folders due to unexpected API response."}


@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """
    Retrieves system status and information about the Radarr instance.
    Returns version, OS, and runtime information.
    """
    logger.info("Getting Radarr system status...")
    response = await _radarr_api_request("GET", f"/api/{API_VERSION}/system/status")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        summary = (
            f"Radarr Version: {response.get('version', 'N/A')} (Branch: {response.get('branch', 'N/A')})\n"
            f"OS: {response.get('osName', 'N/A')} {response.get('osVersion', 'N/A')}\n"
            f"Runtime: {response.get('runtimeName', 'N/A')} {response.get('runtimeVersion', 'N/A')}\n"
            f"AppData: {response.get('appData', 'N/A')}\n"
            f"Startup Time: {response.get('startTime', 'N/A')}\n"
            f"Docker: {'Yes' if response.get('isDocker') else 'No'}"
        )
        return {"summary": summary, "status": response}

    return {"error": "Failed to get system status due to unexpected API response."}


# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Radarr MCP Server...")

    if RADARR_MCP_TRANSPORT == 'sse':
        mcp.run(
            transport='sse',
            host=RADARR_MCP_HOST,
            port=RADARR_MCP_PORT,
            path='/mcp'
        )
    elif RADARR_MCP_TRANSPORT == 'stdio':
        mcp.run()
    else:
        logger.error(f"Invalid RADARR_MCP_TRANSPORT: '{RADARR_MCP_TRANSPORT}'. Defaulting to STDIO.")
        mcp.run()
