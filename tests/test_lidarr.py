"""Tests for the Lidarr MCP server."""
import sys
import os
import pytest
import httpx
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "lidarr-mcp"))
import importlib
lidarr = importlib.import_module("lidarr-mcp-server")

BASE = "http://lidarr.test:8686/api/v1"


# --- get_artists ---

@respx.mock
@pytest.mark.asyncio
async def test_get_artists_happy():
    respx.get(f"{BASE}/artist").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "artistName": "Radiohead", "monitored": True, "foreignArtistId": "abc", "status": "active", "path": "/music/Radiohead", "statistics": {"albumCount": 9}, "images": [{"coverType": "poster", "url": "http://big.jpg"}]},
        {"id": 2, "artistName": "Tool", "monitored": False, "foreignArtistId": "def", "status": "active", "path": "/music/Tool", "statistics": {"albumCount": 5}},
    ]))
    result = await lidarr.get_artists()
    assert len(result["artists"]) == 2
    assert "1 monitored" in result["summary"]
    # Verify condensed - no images
    assert "images" not in result["artists"][0]
    assert set(result["artists"][0].keys()) == {"id", "foreignArtistId", "artistName", "status", "monitored", "albumCount", "path"}


@respx.mock
@pytest.mark.asyncio
async def test_get_artists_empty():
    respx.get(f"{BASE}/artist").mock(return_value=httpx.Response(200, json=[]))
    result = await lidarr.get_artists()
    assert result["artists"] == []


@respx.mock
@pytest.mark.asyncio
async def test_get_artists_500():
    respx.get(f"{BASE}/artist").mock(return_value=httpx.Response(500, text="error"))
    result = await lidarr.get_artists()
    assert "error" in result


# --- lookup_artist ---

@respx.mock
@pytest.mark.asyncio
async def test_lookup_artist_happy():
    respx.get(f"{BASE}/artist/lookup").mock(return_value=httpx.Response(200, json=[
        {"artistName": "Radiohead", "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711"},
    ]))
    result = await lidarr.lookup_artist("radiohead")
    assert len(result["results"]) == 1


# --- add_artist ---

@respx.mock
@pytest.mark.asyncio
async def test_add_artist_happy():
    respx.get(f"{BASE}/artist/lookup").mock(return_value=httpx.Response(200, json=[
        {"artistName": "Radiohead", "foreignArtistId": "abc123"}
    ]))
    respx.post(f"{BASE}/artist").mock(return_value=httpx.Response(201, json={
        "id": 10, "artistName": "Radiohead"
    }))
    result = await lidarr.add_artist("abc123", "Radiohead", 1, 1, "/music")
    assert "Successfully added" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_add_artist_lookup_empty():
    respx.get(f"{BASE}/artist/lookup").mock(return_value=httpx.Response(200, json=[]))
    result = await lidarr.add_artist("nope", "Nope", 1, 1, "/music")
    assert "error" in result


# --- get_albums ---

@respx.mock
@pytest.mark.asyncio
async def test_get_albums_happy():
    respx.get(f"{BASE}/album").mock(return_value=httpx.Response(200, json=[
        {"title": "OK Computer", "monitored": True, "releaseDate": "1997-06-16"},
        {"title": "Kid A", "monitored": True, "releaseDate": "2000-10-02"},
    ]))
    result = await lidarr.get_albums(1)
    assert len(result["albums"]) == 2
    assert "2 monitored" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_albums_404():
    respx.get(f"{BASE}/album").mock(return_value=httpx.Response(404, text="Not found"))
    result = await lidarr.get_albums(999)
    assert "error" in result


# --- get_queue ---

@respx.mock
@pytest.mark.asyncio
async def test_get_queue_happy():
    respx.get(f"{BASE}/queue").mock(return_value=httpx.Response(200, json={
        "totalRecords": 1,
        "records": [{"title": "album.flac", "status": "downloading", "size": 500, "sizeleft": 100}]
    }))
    result = await lidarr.get_queue()
    assert "1 items" in result["summary"]


# --- get_quality_profiles ---

@respx.mock
@pytest.mark.asyncio
async def test_get_quality_profiles():
    respx.get(f"{BASE}/qualityprofile").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "name": "Lossless"},
    ]))
    result = await lidarr.get_quality_profiles()
    assert len(result["profiles"]) == 1


# --- get_metadata_profiles ---

@respx.mock
@pytest.mark.asyncio
async def test_get_metadata_profiles():
    respx.get(f"{BASE}/metadataprofile").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "name": "Standard"},
    ]))
    result = await lidarr.get_metadata_profiles()
    assert len(result["profiles"]) == 1


# --- get_root_folders ---

@respx.mock
@pytest.mark.asyncio
async def test_get_root_folders():
    respx.get(f"{BASE}/rootfolder").mock(return_value=httpx.Response(200, json=[
        {"path": "/music", "freeSpace": 107374182400},
    ]))
    result = await lidarr.get_root_folders()
    assert "/music" in result["summary"]


# --- get_system_status ---

@respx.mock
@pytest.mark.asyncio
async def test_get_system_status():
    respx.get(f"{BASE}/system/status").mock(return_value=httpx.Response(200, json={
        "version": "2.0.0", "branch": "main", "osName": "Linux",
        "osVersion": "6.1", "runtimeName": ".NET", "runtimeVersion": "8.0",
        "appData": "/config", "startTime": "2024-01-01", "isDocker": True
    }))
    result = await lidarr.get_system_status()
    assert "2.0.0" in result["summary"]


# --- Connection error ---

@respx.mock
@pytest.mark.asyncio
async def test_connection_error():
    respx.get(f"{BASE}/artist").mock(side_effect=httpx.ConnectError("refused"))
    result = await lidarr.get_artists()
    assert "error" in result
