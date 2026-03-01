"""Tests for the Sonarr MCP server."""
import sys
import os
import pytest
import httpx
import respx

# Ensure conftest env vars are loaded before import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "sonarr-mcp"))
import importlib
sonarr = importlib.import_module("sonarr-mcp-server")

BASE = "http://sonarr.test:8989/api/v3"


# --- get_series ---

@respx.mock
@pytest.mark.asyncio
async def test_get_series_happy():
    respx.get(f"{BASE}/series").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "title": "Breaking Bad", "monitored": True, "tvdbId": 81189, "year": 2008, "status": "ended", "network": "AMC", "overview": "A teacher turns to crime.", "path": "/tv/Breaking Bad", "statistics": {"seasonCount": 5, "episodeCount": 62, "episodeFileCount": 62, "sizeOnDisk": 100000}},
        {"id": 2, "title": "The Wire", "monitored": False, "tvdbId": 79126, "year": 2002, "status": "ended", "network": "HBO", "overview": "Baltimore drug scene.", "path": "/tv/The Wire", "statistics": {"seasonCount": 5, "episodeCount": 60, "episodeFileCount": 60, "sizeOnDisk": 90000}},
    ]))
    result = await sonarr.get_series()
    assert "series" in result
    assert len(result["series"]) == 2
    assert "2 series" in result["summary"]
    assert "1 monitored" in result["summary"]
    # Verify condensed shape - no image URLs or extra metadata
    s = result["series"][0]
    assert set(s.keys()) == {"id", "tvdbId", "title", "year", "status", "monitored", "network", "overview", "seasonCount", "episodeCount", "episodeFileCount", "sizeOnDisk", "path"}
    assert s["id"] == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_series_empty():
    respx.get(f"{BASE}/series").mock(return_value=httpx.Response(200, json=[]))
    result = await sonarr.get_series()
    assert result["series"] == []
    assert "0 series" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_series_api_error():
    respx.get(f"{BASE}/series").mock(return_value=httpx.Response(500, text="Internal Server Error"))
    result = await sonarr.get_series()
    assert "error" in result
    assert "500" in result["error"]


@respx.mock
@pytest.mark.asyncio
async def test_get_series_401():
    respx.get(f"{BASE}/series").mock(return_value=httpx.Response(401, text="Unauthorized"))
    result = await sonarr.get_series()
    assert "error" in result
    assert "401" in result["error"]


# --- lookup_series ---

@respx.mock
@pytest.mark.asyncio
async def test_lookup_series_happy():
    respx.get(f"{BASE}/series/lookup").mock(return_value=httpx.Response(200, json=[
        {"title": "Breaking Bad", "year": 2008, "tvdbId": 81189, "overview": "A teacher.", "status": "ended", "network": "AMC", "firstAired": "2008-01-20", "images": [{"coverType": "poster", "url": "http://big.jpg"}]},
    ]))
    result = await sonarr.lookup_series("breaking bad")
    assert len(result["results"]) == 1
    assert "1 results" in result["summary"]
    # Verify condensed - no images
    assert "images" not in result["results"][0]
    assert set(result["results"][0].keys()) == {"title", "year", "tvdbId", "overview", "status", "network", "firstAired"}


@respx.mock
@pytest.mark.asyncio
async def test_lookup_series_no_results():
    respx.get(f"{BASE}/series/lookup").mock(return_value=httpx.Response(200, json=[]))
    result = await sonarr.lookup_series("nonexistent")
    assert result["results"] == []


# --- add_series ---

@respx.mock
@pytest.mark.asyncio
async def test_add_series_happy():
    respx.get(f"{BASE}/series/lookup").mock(return_value=httpx.Response(200, json=[
        {"title": "Breaking Bad", "tvdbId": 81189}
    ]))
    respx.post(f"{BASE}/series").mock(return_value=httpx.Response(201, json={
        "id": 10, "title": "Breaking Bad"
    }))
    result = await sonarr.add_series(81189, "Breaking Bad", 1, "/tv", True, True, True)
    assert "Successfully added" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_add_series_lookup_fails():
    respx.get(f"{BASE}/series/lookup").mock(return_value=httpx.Response(200, json=[]))
    result = await sonarr.add_series(99999, "Nope", 1, "/tv")
    assert "error" in result


# --- get_episodes ---

@respx.mock
@pytest.mark.asyncio
async def test_get_episodes_happy():
    respx.get(f"{BASE}/episode").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "hasFile": True},
        {"id": 2, "hasFile": False},
    ]))
    result = await sonarr.get_episodes(1)
    assert len(result["episodes"]) == 2
    assert "1 downloaded" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_episodes_404():
    respx.get(f"{BASE}/episode").mock(return_value=httpx.Response(404, text="Not Found"))
    result = await sonarr.get_episodes(999)
    assert "error" in result


# --- get_season_status ---

@respx.mock
@pytest.mark.asyncio
async def test_get_season_status_happy():
    respx.get(f"{BASE}/series/1").mock(return_value=httpx.Response(200, json={
        "title": "Breaking Bad",
        "seasons": [
            {"seasonNumber": 1, "monitored": True, "statistics": {"totalEpisodeCount": 7, "episodeFileCount": 7, "percentOfEpisodes": 100}},
            {"seasonNumber": 2, "monitored": True, "statistics": {"totalEpisodeCount": 13, "episodeFileCount": 0, "percentOfEpisodes": 0}},
        ]
    }))
    result = await sonarr.get_season_status(1)
    assert "Breaking Bad" in result["summary"]
    assert len(result["seasons"]) == 2


# --- get_queue ---

@respx.mock
@pytest.mark.asyncio
async def test_get_queue_happy():
    respx.get(f"{BASE}/queue").mock(return_value=httpx.Response(200, json={
        "totalRecords": 1,
        "records": [{"title": "S01E01", "status": "downloading", "size": 1000, "sizeleft": 500}]
    }))
    result = await sonarr.get_queue()
    assert "1 items" in result["summary"]
    assert "50.0%" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_queue_empty():
    respx.get(f"{BASE}/queue").mock(return_value=httpx.Response(200, json={
        "totalRecords": 0, "records": []
    }))
    result = await sonarr.get_queue()
    assert "0 items" in result["summary"]


# --- get_quality_profiles ---

@respx.mock
@pytest.mark.asyncio
async def test_get_quality_profiles():
    respx.get(f"{BASE}/qualityprofile").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "name": "HD-1080p"},
    ]))
    result = await sonarr.get_quality_profiles()
    assert len(result["profiles"]) == 1


# --- get_root_folders ---

@respx.mock
@pytest.mark.asyncio
async def test_get_root_folders():
    respx.get(f"{BASE}/rootfolder").mock(return_value=httpx.Response(200, json=[
        {"path": "/tv", "freeSpace": 107374182400},
    ]))
    result = await sonarr.get_root_folders()
    assert "/tv" in result["summary"]


# --- get_system_status ---

@respx.mock
@pytest.mark.asyncio
async def test_get_system_status():
    respx.get(f"{BASE}/system/status").mock(return_value=httpx.Response(200, json={
        "version": "4.0.0", "branch": "main", "osName": "Linux",
        "osVersion": "6.1", "runtimeName": ".NET", "runtimeVersion": "8.0",
        "appData": "/config", "startTime": "2024-01-01", "isDocker": True
    }))
    result = await sonarr.get_system_status()
    assert "4.0.0" in result["summary"]
    assert "Docker: Yes" in result["summary"]


# --- Connection error ---

@respx.mock
@pytest.mark.asyncio
async def test_connection_error():
    respx.get(f"{BASE}/series").mock(side_effect=httpx.ConnectError("Connection refused"))
    result = await sonarr.get_series()
    assert "error" in result
    assert "failed" in result["error"].lower() or "error" in result["error"].lower()
