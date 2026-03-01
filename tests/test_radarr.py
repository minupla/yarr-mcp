"""Tests for the Radarr MCP server."""
import sys
import os
import pytest
import httpx
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "radarr-mcp"))
import importlib
radarr = importlib.import_module("radarr-mcp-server")

BASE = "http://radarr.test:7878/api/v3"


# --- get_movies ---

@respx.mock
@pytest.mark.asyncio
async def test_get_movies_happy():
    respx.get(f"{BASE}/movie").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "title": "Inception", "year": 2010, "tmdbId": 27205, "monitored": True, "hasFile": True, "sizeOnDisk": 50000, "path": "/movies/Inception", "overview": "A thief.", "genres": ["Sci-Fi"], "status": "released", "images": [{"coverType": "poster", "url": "http://big.jpg"}]},
        {"id": 2, "title": "Tenet", "year": 2020, "tmdbId": 577922, "monitored": True, "hasFile": False, "sizeOnDisk": 0, "path": "/movies/Tenet", "overview": "Time.", "genres": ["Action"], "status": "released"},
    ]))
    result = await radarr.get_movies()
    assert len(result["movies"]) == 2
    assert "2 monitored" in result["summary"]
    assert "1 downloaded" in result["summary"]
    # Verify condensed - no images
    assert "images" not in result["movies"][0]
    assert set(result["movies"][0].keys()) == {"id", "tmdbId", "title", "year", "status", "monitored", "hasFile", "sizeOnDisk", "path", "overview", "genres"}


@respx.mock
@pytest.mark.asyncio
async def test_get_movies_empty():
    respx.get(f"{BASE}/movie").mock(return_value=httpx.Response(200, json=[]))
    result = await radarr.get_movies()
    assert result["movies"] == []


@respx.mock
@pytest.mark.asyncio
async def test_get_movies_500():
    respx.get(f"{BASE}/movie").mock(return_value=httpx.Response(500, text="error"))
    result = await radarr.get_movies()
    assert "error" in result


# --- lookup_movie ---

@respx.mock
@pytest.mark.asyncio
async def test_lookup_movie_happy():
    respx.get(f"{BASE}/movie/lookup").mock(return_value=httpx.Response(200, json=[
        {"title": "Inception", "year": 2010, "tmdbId": 27205, "overview": "A thief.", "status": "released", "studio": "Warner Bros", "images": [{"coverType": "poster", "url": "http://big.jpg"}]},
    ]))
    result = await radarr.lookup_movie("inception")
    assert len(result["results"]) == 1
    assert "images" not in result["results"][0]
    assert set(result["results"][0].keys()) == {"title", "year", "tmdbId", "overview", "status", "studio"}


@respx.mock
@pytest.mark.asyncio
async def test_lookup_movie_no_results():
    respx.get(f"{BASE}/movie/lookup").mock(return_value=httpx.Response(200, json=[]))
    result = await radarr.lookup_movie("zzzzzzz")
    assert result["results"] == []


# --- add_movie ---

@respx.mock
@pytest.mark.asyncio
async def test_add_movie_happy():
    respx.get(f"{BASE}/movie/lookup/tmdb").mock(return_value=httpx.Response(200, json={
        "title": "Inception", "tmdbId": 27205
    }))
    respx.post(f"{BASE}/movie").mock(return_value=httpx.Response(201, json={
        "id": 5, "title": "Inception"
    }))
    result = await radarr.add_movie(27205, "Inception", 1, "/movies")
    assert "Successfully added" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_add_movie_lookup_not_found():
    respx.get(f"{BASE}/movie/lookup/tmdb").mock(return_value=httpx.Response(200, json={}))
    result = await radarr.add_movie(99999, "Nope", 1, "/movies")
    # The lookup returns a dict without "title", so should error
    assert "error" in result


@respx.mock
@pytest.mark.asyncio
async def test_add_movie_api_error():
    respx.get(f"{BASE}/movie/lookup/tmdb").mock(return_value=httpx.Response(404, text="Not found"))
    result = await radarr.add_movie(99999, "Nope", 1, "/movies")
    assert "error" in result


# --- get_queue ---

@respx.mock
@pytest.mark.asyncio
async def test_get_queue_happy():
    respx.get(f"{BASE}/queue").mock(return_value=httpx.Response(200, json={
        "totalRecords": 2,
        "records": [
            {"title": "Movie.mkv", "status": "downloading", "size": 2000, "sizeleft": 1000},
        ]
    }))
    result = await radarr.get_queue()
    assert "2 items" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_queue_zero_size():
    """Test queue item with size=0 doesn't cause division by zero."""
    respx.get(f"{BASE}/queue").mock(return_value=httpx.Response(200, json={
        "totalRecords": 1,
        "records": [{"title": "x", "status": "queued", "size": 0, "sizeleft": 0}]
    }))
    result = await radarr.get_queue()
    assert "error" not in result


# --- get_quality_profiles ---

@respx.mock
@pytest.mark.asyncio
async def test_get_quality_profiles():
    respx.get(f"{BASE}/qualityprofile").mock(return_value=httpx.Response(200, json=[
        {"id": 1, "name": "HD-1080p"},
        {"id": 4, "name": "Ultra-HD"},
    ]))
    result = await radarr.get_quality_profiles()
    assert len(result["profiles"]) == 2


# --- get_root_folders ---

@respx.mock
@pytest.mark.asyncio
async def test_get_root_folders():
    respx.get(f"{BASE}/rootfolder").mock(return_value=httpx.Response(200, json=[
        {"path": "/movies", "freeSpace": 53687091200},
    ]))
    result = await radarr.get_root_folders()
    assert "/movies" in result["summary"]


# --- get_system_status ---

@respx.mock
@pytest.mark.asyncio
async def test_get_system_status():
    respx.get(f"{BASE}/system/status").mock(return_value=httpx.Response(200, json={
        "version": "5.0.0", "branch": "develop", "osName": "Linux",
        "osVersion": "6.1", "runtimeName": ".NET", "runtimeVersion": "8.0",
        "appData": "/config", "startTime": "2024-01-01", "isDocker": False
    }))
    result = await radarr.get_system_status()
    assert "5.0.0" in result["summary"]
    assert "Docker: No" in result["summary"]


# --- Connection error ---

@respx.mock
@pytest.mark.asyncio
async def test_connection_error():
    respx.get(f"{BASE}/movie").mock(side_effect=httpx.ConnectError("refused"))
    result = await radarr.get_movies()
    assert "error" in result
