"""
Shared fixtures for yarr-mcp test suites.
Sets env vars before any server module is imported.
"""
import os

# Set all required env vars BEFORE any server module gets imported.
# These are fake values — all HTTP calls are mocked via respx.
os.environ.setdefault("SONARR_URL", "http://sonarr.test:8989")
os.environ.setdefault("SONARR_API_KEY", "test-sonarr-key")
os.environ.setdefault("RADARR_URL", "http://radarr.test:7878")
os.environ.setdefault("RADARR_API_KEY", "test-radarr-key")
os.environ.setdefault("LIDARR_URL", "http://lidarr.test:8686")
os.environ.setdefault("LIDARR_API_KEY", "test-lidarr-key")
os.environ.setdefault("ABS_URL", "http://abs.test:13378")
os.environ.setdefault("ABS_TOKEN", "test-abs-token-1234567890")
os.environ.setdefault("PROWLARR_URL", "http://prowlarr.test:9696")
os.environ.setdefault("PROWLARR_API_KEY", "test-prowlarr-key")
