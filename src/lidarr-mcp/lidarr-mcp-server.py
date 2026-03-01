"""
MCP Server for Lidarr
Implements tools for Lidarr music management using SSE transport.
Built with FastMCP following best practices from gofastmcp.com
Based on Lidarr API v1
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
API_VERSION = "v1"

# --- Logging Setup ---
LIDARR_MCP_LOG_LEVEL = os.getenv('LIDARR_MCP_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
LIDARR_MCP_LOG_FILE = os.getenv('LIDARR_MCP_LOG_FILE', "lidarr_mcp.log")
LIDARR_MCP_TRANSPORT = os.getenv('LIDARR_MCP_TRANSPORT', 'sse').lower()
LIDARR_MCP_HOST = os.getenv('LIDARR_MCP_HOST', '0.0.0.0')
LIDARR_MCP_PORT = int(os.getenv('LIDARR_MCP_PORT', '6976'))

NUMERIC_LOG_LEVEL = getattr(logging, LIDARR_MCP_LOG_LEVEL, logging.INFO)
SCRIPT_DIR = Path(__file__).resolve().parent

# --- Environment Variable & API Client Setup ---
project_root = SCRIPT_DIR.parent.parent
env_path = project_root / '.env'

print(f"LidarrMCP: Looking for .env file at: {env_path}")
found_dotenv = load_dotenv(dotenv_path=env_path, override=False)
print(f"LidarrMCP: load_dotenv found file: {found_dotenv}")

LIDARR_URL = os.getenv('LIDARR_URL')
LIDARR_API_KEY = os.getenv('LIDARR_API_KEY')

logger = logging.getLogger("LidarrMCPServer")
logger.setLevel(NUMERIC_LOG_LEVEL)
logger.propagate = False

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NUMERIC_LOG_LEVEL)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File Handler
log_file_path = SCRIPT_DIR / LIDARR_MCP_LOG_FILE
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(NUMERIC_LOG_LEVEL)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging initialized (console and file: {log_file_path}). Log level: {LIDARR_MCP_LOG_LEVEL}")
logger.info(f"Lidarr MCP Transport: {LIDARR_MCP_TRANSPORT}, Host: {LIDARR_MCP_HOST}, Port: {LIDARR_MCP_PORT}")

if not LIDARR_URL or not LIDARR_API_KEY:
    if __name__ == "__main__":
        logger.error("LIDARR_URL and LIDARR_API_KEY environment variables must be set.")
        sys.exit(1)
    else:
        logger.warning("LIDARR_URL or LIDARR_API_KEY not set. Tools will fail at runtime.")

if LIDARR_URL and LIDARR_URL.endswith('/'):
    LIDARR_URL = LIDARR_URL[:-1]

if LIDARR_URL and LIDARR_API_KEY:
    logger.info(f"Lidarr API URL: {LIDARR_URL}")
    logger.info(f"Lidarr API Key: {'*' * (len(LIDARR_API_KEY) - 4) + LIDARR_API_KEY[-4:]}")

# --- FastMCP Server Initialization ---
mcp = FastMCP(
    name="Lidarr MCP Server",
    instructions="""Provides tools to interact with a Lidarr instance.
Manages music artists, albums, quality/metadata profiles, and monitors download queues.
Requires LIDARR_URL and LIDARR_API_KEY environment variables.
API interactions are based on Lidarr API v1."""
)

# --- Helper Functions ---
async def _lidarr_api_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], List[Any], None]:
    """Helper function to make requests to the Lidarr API."""
    headers = {'X-Api-Key': LIDARR_API_KEY}
    url = f"{LIDARR_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.debug(f"Request: {method} {url} - Params: {params} - Body: {json_body}")
            response = await client.request(method, url, params=params, json=json_body, headers=headers)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling Lidarr API: {e.response.status_code} - {e.response.text}")
        error_content = {"error": f"Lidarr API Error: {e.response.status_code}", "details": e.response.text}
        try:
            error_content["details"] = e.response.json()
        except Exception:
            pass
        return error_content
    except httpx.RequestError as e:
        logger.error(f"Request error calling Lidarr API: {e}")
        return {"error": f"Request to Lidarr API failed: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error in Lidarr API request: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}

# --- Core Tools ---

@mcp.tool()
async def get_artists() -> Dict[str, Any]:
    """
    Retrieves a list of all artists in the Lidarr library.
    Returns a summary and the full list of artist objects.
    """
    logger.info("Listing all artists...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/artist")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        monitored = [a for a in response if a.get('monitored', False)]
        summary = f"Found {len(response)} artists ({len(monitored)} monitored)."
        if response:
            summary += " First few: " + ", ".join(
                [f"{a.get('artistName', 'N/A')} (ID: {a.get('id', 'N/A')}, {'Monitored' if a.get('monitored') else 'Unmonitored'})"
                 for a in response[:5]]
            )
        condensed = [{
            "id": a.get("id"),
            "foreignArtistId": a.get("foreignArtistId"),
            "artistName": a.get("artistName"),
            "status": a.get("status"),
            "monitored": a.get("monitored"),
            "albumCount": a.get("statistics", {}).get("albumCount", a.get("albumCount")),
            "path": a.get("path"),
        } for a in response]
        return {"summary": summary, "artists": condensed}

    return {"error": "Failed to list artists due to unexpected API response."}


@mcp.tool()
async def lookup_artist(term: str) -> Dict[str, Any]:
    """
    Searches for music artists on MusicBrainz via Lidarr.
    Returns matching artists with foreign artist IDs for use with add_artist.
    """
    logger.info(f"Looking up artist: '{term}'")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/artist/lookup", params={"term": term})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} results for '{term}'."
        if response:
            summary += " Top results: " + ", ".join(
                [f"{a.get('artistName', 'N/A')} (Foreign ID: {a.get('foreignArtistId', 'N/A')})"
                 for a in response[:5]]
            )
        return {"summary": summary, "results": response}

    return {"error": "Failed to lookup artist due to unexpected API response."}


@mcp.tool()
async def add_artist(
    foreign_artist_id: str,
    artist_name: str,
    quality_profile_id: int,
    metadata_profile_id: int,
    root_folder_path: str,
    monitored: bool = True,
    monitor: str = "all",
    search_for_missing_albums: bool = True
) -> Dict[str, Any]:
    """
    Adds a new music artist to Lidarr.
    Use lookup_artist to find the foreign_artist_id.
    Use get_quality_profiles, get_metadata_profiles, and get_root_folders for valid IDs/paths.
    monitor options: all, future, missing, existing, first, latest, none
    """
    logger.info(f"Adding artist: '{artist_name}' (Foreign ID: {foreign_artist_id})")

    # First lookup to get full artist data
    lookup = await _lidarr_api_request("GET", f"/api/{API_VERSION}/artist/lookup", params={"term": f"lidarr:{foreign_artist_id}"})
    if isinstance(lookup, dict) and "error" in lookup:
        return lookup
    if not isinstance(lookup, list) or len(lookup) == 0:
        return {"error": f"Could not find artist with foreign ID {foreign_artist_id}"}

    artist_data = lookup[0]
    artist_data.update({
        "qualityProfileId": quality_profile_id,
        "metadataProfileId": metadata_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": monitored,
        "addOptions": {
            "monitor": monitor,
            "searchForMissingAlbums": search_for_missing_albums
        }
    })

    response = await _lidarr_api_request("POST", f"/api/{API_VERSION}/artist", json_body=artist_data)

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "id" in response:
        return {"summary": f"Successfully added '{response.get('artistName', artist_name)}' (ID: {response.get('id')}).", "artist": response}

    return {"error": "Failed to add artist due to unexpected API response."}


@mcp.tool()
async def get_albums(artist_id: int) -> Dict[str, Any]:
    """
    Retrieves all albums for a given artist ID.
    Returns album list with monitoring and download status.
    """
    logger.info(f"Getting albums for artist ID: {artist_id}")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/album", params={"artistId": artist_id})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        monitored = [a for a in response if a.get('monitored', False)]
        summary = f"Found {len(response)} albums ({len(monitored)} monitored)."
        if response:
            summary += " Albums: " + ", ".join(
                [f"{a.get('title', 'N/A')} ({a.get('releaseDate', 'N/A')[:4] if a.get('releaseDate') else 'N/A'})"
                 for a in response[:10]]
            )
        return {"summary": summary, "albums": response}

    return {"error": "Failed to get albums due to unexpected API response."}


@mcp.tool()
async def get_queue() -> Dict[str, Any]:
    """
    Retrieves the current download queue from Lidarr.
    Shows active downloads with progress information.
    """
    logger.info("Getting Lidarr download queue...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/queue", params={"pageSize": 100})

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
    Retrieves all quality profiles configured in Lidarr.
    Use the returned IDs when adding artists.
    """
    logger.info("Getting Lidarr quality profiles...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/qualityprofile")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} quality profiles: " + ", ".join(
            [f"{p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')})" for p in response]
        )
        return {"summary": summary, "profiles": response}

    return {"error": "Failed to get quality profiles due to unexpected API response."}


@mcp.tool()
async def get_metadata_profiles() -> Dict[str, Any]:
    """
    Retrieves all metadata profiles configured in Lidarr.
    Metadata profiles control which albums/releases are monitored for an artist.
    Use the returned IDs when adding artists.
    """
    logger.info("Getting Lidarr metadata profiles...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/metadataprofile")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} metadata profiles: " + ", ".join(
            [f"{p.get('name', 'N/A')} (ID: {p.get('id', 'N/A')})" for p in response]
        )
        return {"summary": summary, "profiles": response}

    return {"error": "Failed to get metadata profiles due to unexpected API response."}


@mcp.tool()
async def get_root_folders() -> Dict[str, Any]:
    """
    Retrieves all root folder paths configured in Lidarr.
    Use the returned paths when adding artists.
    """
    logger.info("Getting Lidarr root folders...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/rootfolder")

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
    Retrieves system status and information about the Lidarr instance.
    Returns version, OS, and runtime information.
    """
    logger.info("Getting Lidarr system status...")
    response = await _lidarr_api_request("GET", f"/api/{API_VERSION}/system/status")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        summary = (
            f"Lidarr Version: {response.get('version', 'N/A')} (Branch: {response.get('branch', 'N/A')})\n"
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
    logger.info("Starting Lidarr MCP Server...")

    if LIDARR_MCP_TRANSPORT == 'sse':
        mcp.run(
            transport='sse',
            host=LIDARR_MCP_HOST,
            port=LIDARR_MCP_PORT,
            path='/mcp'
        )
    elif LIDARR_MCP_TRANSPORT == 'stdio':
        mcp.run()
    else:
        logger.error(f"Invalid LIDARR_MCP_TRANSPORT: '{LIDARR_MCP_TRANSPORT}'. Defaulting to STDIO.")
        mcp.run()
