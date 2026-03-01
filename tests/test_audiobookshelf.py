"""Tests for the Audiobookshelf MCP server."""
import sys
import os
import pytest
import httpx
import respx
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "audiobookshelf-mcp"))
import importlib
abs_server = importlib.import_module("audiobookshelf-mcp-server")

BASE = "http://abs.test:13378"


# --- get_libraries ---

@respx.mock
@pytest.mark.asyncio
async def test_get_libraries_happy():
    respx.get(f"{BASE}/api/libraries").mock(return_value=httpx.Response(200, json={
        "libraries": [
            {"id": "lib1", "name": "Audiobooks", "mediaType": "book", "stats": {"totalItems": 42}},
        ]
    }))
    result = await abs_server.get_libraries()
    assert len(result["libraries"]) == 1
    assert result["libraries"][0]["name"] == "Audiobooks"


@respx.mock
@pytest.mark.asyncio
async def test_get_libraries_list_format():
    """Some API versions return a list directly."""
    respx.get(f"{BASE}/api/libraries").mock(return_value=httpx.Response(200, json=[
        {"id": "lib1", "name": "Audiobooks", "mediaType": "book"},
    ]))
    result = await abs_server.get_libraries()
    assert len(result["libraries"]) == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_libraries_error():
    respx.get(f"{BASE}/api/libraries").mock(return_value=httpx.Response(401, text="Unauthorized"))
    result = await abs_server.get_libraries()
    assert "error" in result


# --- get_library_items ---

@respx.mock
@pytest.mark.asyncio
async def test_get_library_items_happy():
    respx.get(f"{BASE}/api/libraries/lib1/items").mock(return_value=httpx.Response(200, json={
        "results": [
            {
                "id": "item1",
                "media": {"metadata": {"title": "Project Hail Mary", "authorName": "Andy Weir"}, "duration": 57600},
                "userMediaProgress": {"progress": 0.5}
            }
        ],
        "total": 1
    }))
    result = await abs_server.get_library_items("lib1")
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Project Hail Mary"


@respx.mock
@pytest.mark.asyncio
async def test_get_library_items_no_progress():
    respx.get(f"{BASE}/api/libraries/lib1/items").mock(return_value=httpx.Response(200, json={
        "results": [
            {
                "id": "item1",
                "media": {"metadata": {"title": "Test", "authorName": "Author"}, "duration": 3600},
            }
        ],
        "total": 1
    }))
    result = await abs_server.get_library_items("lib1")
    assert "currentTime" not in result["items"][0]  # no progress data


# --- search_library ---

@respx.mock
@pytest.mark.asyncio
async def test_search_library_happy():
    respx.get(f"{BASE}/api/libraries/lib1/search").mock(return_value=httpx.Response(200, json={
        "book": [
            {"libraryItem": {"id": "item1", "media": {"metadata": {"title": "Dune", "authorName": "Herbert"}, "duration": 72000}}}
        ]
    }))
    result = await abs_server.search_library("lib1", "dune")
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Dune"


@respx.mock
@pytest.mark.asyncio
async def test_search_library_empty():
    respx.get(f"{BASE}/api/libraries/lib1/search").mock(return_value=httpx.Response(200, json={
        "book": []
    }))
    result = await abs_server.search_library("lib1", "nonexistent")
    assert result["results"] == []


# --- get_item ---

@respx.mock
@pytest.mark.asyncio
async def test_get_item_happy():
    respx.get(f"{BASE}/api/items/item1").mock(return_value=httpx.Response(200, json={
        "id": "item1",
        "media": {
            "metadata": {"title": "Dune", "authorName": "Herbert", "narratorName": "Someone", "description": "Sci-fi"},
            "duration": 72000,
            "chapters": [
                {"id": 1, "title": "Chapter 1", "start": 0, "end": 3600},
                {"id": 2, "title": "Chapter 2", "start": 3600, "end": 7200},
            ]
        },
        "userMediaProgress": {"currentTime": 1800, "progress": 0.025, "isFinished": False}
    }))
    result = await abs_server.get_item("item1")
    assert result["item"]["title"] == "Dune"
    assert result["item"]["numChapters"] == 2
    assert "2.5%" in result["item"]["progress"]["progress"]


@respx.mock
@pytest.mark.asyncio
async def test_get_item_no_progress():
    respx.get(f"{BASE}/api/items/item1").mock(return_value=httpx.Response(200, json={
        "id": "item1",
        "media": {
            "metadata": {"title": "Test", "authorName": "Author", "narratorName": "N", "description": ""},
            "duration": 3600,
            "chapters": []
        },
    }))
    result = await abs_server.get_item("item1")
    assert "progress" not in result["item"]


@respx.mock
@pytest.mark.asyncio
async def test_get_item_404():
    respx.get(f"{BASE}/api/items/bad").mock(return_value=httpx.Response(404, text="Not found"))
    result = await abs_server.get_item("bad")
    assert "error" in result


# --- get_progress ---

@respx.mock
@pytest.mark.asyncio
async def test_get_progress_happy():
    respx.get(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(200, json={
        "currentTime": 1800, "duration": 72000, "progress": 0.025, "isFinished": False, "lastUpdate": 1700000000
    }))
    result = await abs_server.get_progress("item1")
    assert result["progress"]["currentTime"] == 1800
    assert "2.5%" in result["summary"]


@respx.mock
@pytest.mark.asyncio
async def test_get_progress_none():
    """No progress found returns None."""
    respx.get(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(204))
    result = await abs_server.get_progress("item1")
    assert result["progress"] is None


# --- update_progress ---

@respx.mock
@pytest.mark.asyncio
async def test_update_progress_happy():
    route = respx.patch(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(200, json={}))
    with patch("time.time", return_value=1700000.0):
        result = await abs_server.update_progress("item1", 3600.0, 72000.0, False)
    assert result["status"] == "success"
    # Verify the body was constructed correctly
    body = result["updated"]
    assert body["currentTime"] == 3600.0
    assert body["duration"] == 72000.0
    assert body["progress"] == pytest.approx(3600.0 / 72000.0)
    assert body["isFinished"] is False
    assert body["lastUpdate"] == 1700000000  # epoch ms


@respx.mock
@pytest.mark.asyncio
async def test_update_progress_finished():
    respx.patch(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(200, json={}))
    result = await abs_server.update_progress("item1", 72000.0, 72000.0, True)
    assert result["updated"]["isFinished"] is True
    assert result["updated"]["progress"] == pytest.approx(1.0)


@respx.mock
@pytest.mark.asyncio
async def test_update_progress_zero_duration():
    """Zero duration should not cause ZeroDivisionError."""
    respx.patch(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(200, json={}))
    result = await abs_server.update_progress("item1", 0, 0, False)
    assert result["updated"]["progress"] == 0.0


@respx.mock
@pytest.mark.asyncio
async def test_update_progress_api_error():
    respx.patch(f"{BASE}/api/me/progress/item1").mock(return_value=httpx.Response(500, text="error"))
    result = await abs_server.update_progress("item1", 100, 200)
    assert "error" in result


# --- get_all_progress ---

@respx.mock
@pytest.mark.asyncio
async def test_get_all_progress_happy():
    respx.get(f"{BASE}/api/me/items-in-progress").mock(return_value=httpx.Response(200, json={
        "libraryItems": [
            {
                "id": "item1",
                "media": {"metadata": {"title": "Dune", "authorName": "Herbert"}},
                "userMediaProgress": {"currentTime": 3600, "progress": 0.5, "isFinished": False}
            }
        ]
    }))
    result = await abs_server.get_all_progress()
    assert len(result["items"]) == 1
    assert "50.0%" in result["items"][0]["progress"]


@respx.mock
@pytest.mark.asyncio
async def test_get_all_progress_list_format():
    respx.get(f"{BASE}/api/me/items-in-progress").mock(return_value=httpx.Response(200, json=[
        {"id": "item1"}
    ]))
    result = await abs_server.get_all_progress()
    assert len(result["items"]) == 1


# --- get_listening_sessions ---

@respx.mock
@pytest.mark.asyncio
async def test_get_listening_sessions_happy():
    respx.get(f"{BASE}/api/me/listening-sessions").mock(return_value=httpx.Response(200, json={
        "sessions": [
            {
                "id": "s1",
                "mediaMetadata": {"title": "Dune", "authorName": "Herbert"},
                "timeListening": 3600, "currentTime": 7200, "updatedAt": "2024-01-01"
            }
        ],
        "total": 1
    }))
    result = await abs_server.get_listening_sessions()
    assert len(result["sessions"]) == 1


# --- get_listening_stats ---

@respx.mock
@pytest.mark.asyncio
async def test_get_listening_stats_happy():
    respx.get(f"{BASE}/api/me/listening-stats").mock(return_value=httpx.Response(200, json={
        "totalTime": 360000,
        "itemsFinished": 5,
        "days": {"2024-01-01": 3600, "2024-01-02": 7200},
        "authorsListening": {"Herbert": 10000}
    }))
    result = await abs_server.get_listening_stats()
    assert result["stats"]["itemsFinished"] == 5
    assert result["stats"]["daysListening"] == 2


@respx.mock
@pytest.mark.asyncio
async def test_get_listening_stats_empty():
    respx.get(f"{BASE}/api/me/listening-stats").mock(return_value=httpx.Response(200, json={
        "totalTime": 0, "days": {}
    }))
    result = await abs_server.get_listening_stats()
    assert result["stats"]["totalTime"] == 0


# --- get_in_progress (alias) ---

@respx.mock
@pytest.mark.asyncio
async def test_get_in_progress_is_alias():
    respx.get(f"{BASE}/api/me/items-in-progress").mock(return_value=httpx.Response(200, json={
        "libraryItems": []
    }))
    result = await abs_server.get_in_progress()
    assert "items" in result


# --- Connection error ---

@respx.mock
@pytest.mark.asyncio
async def test_connection_error():
    respx.get(f"{BASE}/api/libraries").mock(side_effect=httpx.ConnectError("refused"))
    result = await abs_server.get_libraries()
    assert "error" in result


# --- _format_duration helper ---

def test_format_duration_zero():
    assert abs_server._format_duration(0) == "0s"
    assert abs_server._format_duration(None) == "0s"


def test_format_duration_seconds():
    assert abs_server._format_duration(45) == "45s"


def test_format_duration_minutes():
    assert abs_server._format_duration(125) == "2m 5s"


def test_format_duration_hours():
    assert abs_server._format_duration(3661) == "1h 1m 1s"
