"""
MCP Server for Sonarr
Implements tools for Sonarr TV show management using SSE transport.
Built with FastMCP following best practices from gofastmcp.com
Based on Sonarr API v3
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
SONARR_MCP_LOG_LEVEL = os.getenv('SONARR_MCP_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
SONARR_MCP_LOG_FILE = os.getenv('SONARR_MCP_LOG_FILE', "sonarr_mcp.log")
SONARR_MCP_TRANSPORT = os.getenv('SONARR_MCP_TRANSPORT', 'sse').lower()
SONARR_MCP_HOST = os.getenv('SONARR_MCP_HOST', '0.0.0.0')
SONARR_MCP_PORT = int(os.getenv('SONARR_MCP_PORT', '6974'))

NUMERIC_LOG_LEVEL = getattr(logging, SONARR_MCP_LOG_LEVEL, logging.INFO)
SCRIPT_DIR = Path(__file__).resolve().parent

# --- Environment Variable & API Client Setup ---
project_root = SCRIPT_DIR.parent.parent
env_path = project_root / '.env'

print(f"SonarrMCP: Looking for .env file at: {env_path}")
found_dotenv = load_dotenv(dotenv_path=env_path, override=False)
print(f"SonarrMCP: load_dotenv found file: {found_dotenv}")

SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

logger = logging.getLogger("SonarrMCPServer")
logger.setLevel(NUMERIC_LOG_LEVEL)
logger.propagate = False

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NUMERIC_LOG_LEVEL)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File Handler
log_file_path = SCRIPT_DIR / SONARR_MCP_LOG_FILE
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(NUMERIC_LOG_LEVEL)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging initialized (console and file: {log_file_path}). Log level: {SONARR_MCP_LOG_LEVEL}")
logger.info(f"Sonarr MCP Transport: {SONARR_MCP_TRANSPORT}, Host: {SONARR_MCP_HOST}, Port: {SONARR_MCP_PORT}")

if not SONARR_URL or not SONARR_API_KEY:
    if __name__ == "__main__":
        logger.error("SONARR_URL and SONARR_API_KEY environment variables must be set.")
        sys.exit(1)
    else:
        logger.warning("SONARR_URL or SONARR_API_KEY not set. Tools will fail at runtime.")

if SONARR_URL and SONARR_URL.endswith('/'):
    SONARR_URL = SONARR_URL[:-1]

if SONARR_URL and SONARR_API_KEY:
    logger.info(f"Sonarr API URL: {SONARR_URL}")
    logger.info(f"Sonarr API Key: {'*' * (len(SONARR_API_KEY) - 4) + SONARR_API_KEY[-4:]}")

# --- FastMCP Server Initialization ---
mcp = FastMCP(
    name="Sonarr MCP Server",
    instructions="""Provides tools to interact with a Sonarr instance.
Manages TV series, episodes, quality profiles, and monitors download queues.
Requires SONARR_URL and SONARR_API_KEY environment variables.
API interactions are based on Sonarr API v3."""
)

# --- Helper Functions ---
async def _sonarr_api_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], List[Any], None]:
    """Helper function to make requests to the Sonarr API."""
    headers = {'X-Api-Key': SONARR_API_KEY}
    url = f"{SONARR_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.debug(f"Request: {method} {url} - Params: {params} - Body: {json_body}")
            response = await client.request(method, url, params=params, json=json_body, headers=headers)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling Sonarr API: {e.response.status_code} - {e.response.text}")
        error_content = {"error": f"Sonarr API Error: {e.response.status_code}", "details": e.response.text}
        try:
            error_content["details"] = e.response.json()
        except Exception:
            pass
        return error_content
    except httpx.RequestError as e:
        logger.error(f"Request error calling Sonarr API: {e}")
        return {"error": f"Request to Sonarr API failed: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error in Sonarr API request: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}

# --- Core Tools ---

@mcp.tool()
async def get_series() -> Dict[str, Any]:
    """
    Retrieves a list of all series in the Sonarr library.
    Returns a summary and the full list of series objects.
    """
    logger.info("Listing all series...")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/series")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        monitored = [s for s in response if s.get('monitored', False)]
        summary = f"Found {len(response)} series ({len(monitored)} monitored)."
        if response:
            summary += " First few: " + ", ".join(
                [f"{s.get('title', 'N/A')} (ID: {s.get('id', 'N/A')}, {'Monitored' if s.get('monitored') else 'Unmonitored'})"
                 for s in response[:5]]
            )
        condensed = [{
            "id": s.get("id"),
            "tvdbId": s.get("tvdbId"),
            "title": s.get("title"),
            "year": s.get("year"),
            "status": s.get("status"),
            "monitored": s.get("monitored"),
            "network": s.get("network"),
            "overview": (s.get("overview") or "")[:200],
            "seasonCount": s.get("statistics", {}).get("seasonCount", s.get("seasonCount")),
            "episodeCount": s.get("statistics", {}).get("episodeCount", s.get("episodeCount")),
            "episodeFileCount": s.get("statistics", {}).get("episodeFileCount", s.get("episodeFileCount")),
            "sizeOnDisk": s.get("statistics", {}).get("sizeOnDisk", s.get("sizeOnDisk")),
            "path": s.get("path"),
        } for s in response]
        return {"summary": summary, "series": condensed}

    return {"error": "Failed to list series due to unexpected API response."}


@mcp.tool()
async def lookup_series(term: str) -> Dict[str, Any]:
    """
    Searches for TV series on TVDB via Sonarr.
    Returns matching series with TVDB IDs for use with add_series.
    """
    logger.info(f"Looking up series: '{term}'")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/series/lookup", params={"term": term})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        summary = f"Found {len(response)} results for '{term}'."
        if response:
            summary += " Top results: " + ", ".join(
                [f"{s.get('title', 'N/A')} ({s.get('year', 'N/A')}, TVDB: {s.get('tvdbId', 'N/A')})"
                 for s in response[:5]]
            )
        condensed = [{
            "title": s.get("title"),
            "year": s.get("year"),
            "tvdbId": s.get("tvdbId"),
            "overview": (s.get("overview") or "")[:200],
            "status": s.get("status"),
            "network": s.get("network"),
            "firstAired": s.get("firstAired"),
        } for s in response]
        return {"summary": summary, "results": condensed}

    return {"error": "Failed to lookup series due to unexpected API response."}


@mcp.tool()
async def add_series(
    tvdb_id: int,
    title: str,
    quality_profile_id: int,
    root_folder_path: str,
    monitored: bool = True,
    season_folder: bool = True,
    search_for_missing_episodes: bool = True
) -> Dict[str, Any]:
    """
    Adds a new TV series to Sonarr.
    Use lookup_series to find the tvdb_id, and get_quality_profiles/get_root_folders for valid IDs/paths.
    """
    logger.info(f"Adding series: '{title}' (TVDB: {tvdb_id})")

    # First lookup to get full series data
    lookup = await _sonarr_api_request("GET", f"/api/{API_VERSION}/series/lookup", params={"term": f"tvdb:{tvdb_id}"})
    if isinstance(lookup, dict) and "error" in lookup:
        return lookup
    if not isinstance(lookup, list) or len(lookup) == 0:
        return {"error": f"Could not find series with TVDB ID {tvdb_id}"}

    series_data = lookup[0]
    series_data.update({
        "qualityProfileId": quality_profile_id,
        "rootFolderPath": root_folder_path,
        "monitored": monitored,
        "seasonFolder": season_folder,
        "addOptions": {
            "searchForMissingEpisodes": search_for_missing_episodes
        }
    })

    response = await _sonarr_api_request("POST", f"/api/{API_VERSION}/series", json_body=series_data)

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict) and "id" in response:
        return {"summary": f"Successfully added '{response.get('title', title)}' (ID: {response.get('id')}).", "series": response}

    return {"error": "Failed to add series due to unexpected API response."}


@mcp.tool()
async def get_episodes(series_id: int) -> Dict[str, Any]:
    """
    Retrieves all episodes for a given series ID.
    Returns episode list with download status information.
    """
    logger.info(f"Getting episodes for series ID: {series_id}")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/episode", params={"seriesId": series_id})

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, list):
        has_file = [e for e in response if e.get('hasFile', False)]
        summary = f"Found {len(response)} episodes ({len(has_file)} downloaded)."
        return {"summary": summary, "episodes": response}

    return {"error": "Failed to get episodes due to unexpected API response."}


@mcp.tool()
async def get_season_status(series_id: int) -> Dict[str, Any]:
    """
    Gets download status per season for a given series.
    Shows how many episodes are available vs total for each season.
    """
    logger.info(f"Getting season status for series ID: {series_id}")
    series_response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/series/{series_id}")

    if isinstance(series_response, dict) and "error" in series_response:
        return series_response

    if isinstance(series_response, dict) and "seasons" in series_response:
        seasons = series_response.get("seasons", [])
        title = series_response.get("title", "Unknown")
        summary = f"Season status for '{title}':\n"
        for season in seasons:
            sn = season.get("seasonNumber", "?")
            stats = season.get("statistics", {})
            total = stats.get("totalEpisodeCount", 0)
            have = stats.get("episodeFileCount", 0)
            pct = stats.get("percentOfEpisodes", 0)
            monitored = "Monitored" if season.get("monitored") else "Unmonitored"
            label = "Specials" if sn == 0 else f"Season {sn}"
            summary += f"  {label}: {have}/{total} ({pct:.0f}%) [{monitored}]\n"
        return {"summary": summary.strip(), "series_title": title, "seasons": seasons}

    return {"error": "Failed to get season status due to unexpected API response."}


@mcp.tool()
async def get_queue() -> Dict[str, Any]:
    """
    Retrieves the current download queue from Sonarr.
    Shows active downloads with progress information.
    """
    logger.info("Getting Sonarr download queue...")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/queue", params={"pageSize": 100})

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
    Retrieves all quality profiles configured in Sonarr.
    Use the returned IDs when adding series.
    """
    logger.info("Getting Sonarr quality profiles...")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/qualityprofile")

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
    Retrieves all root folder paths configured in Sonarr.
    Use the returned paths when adding series.
    """
    logger.info("Getting Sonarr root folders...")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/rootfolder")

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
    Retrieves system status and information about the Sonarr instance.
    Returns version, OS, and runtime information.
    """
    logger.info("Getting Sonarr system status...")
    response = await _sonarr_api_request("GET", f"/api/{API_VERSION}/system/status")

    if isinstance(response, dict) and "error" in response:
        return response

    if isinstance(response, dict):
        summary = (
            f"Sonarr Version: {response.get('version', 'N/A')} (Branch: {response.get('branch', 'N/A')})\n"
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
    logger.info("Starting Sonarr MCP Server...")

    if SONARR_MCP_TRANSPORT == 'sse':
        mcp.run(
            transport='sse',
            host=SONARR_MCP_HOST,
            port=SONARR_MCP_PORT,
            path='/mcp'
        )
    elif SONARR_MCP_TRANSPORT == 'stdio':
        mcp.run()
    else:
        logger.error(f"Invalid SONARR_MCP_TRANSPORT: '{SONARR_MCP_TRANSPORT}'. Defaulting to STDIO.")
        mcp.run()
