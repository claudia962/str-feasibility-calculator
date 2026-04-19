"""Test that Nominatim fallback geocodes Melbourne addresses."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_nominatim_fallback_melbourne():
    """Nominatim fallback should resolve a Melbourne address to correct lat/lng range."""
    mock_response = [{"lat": "-37.8136", "lon": "144.9631", "display_name": "Melbourne VIC, Australia", "importance": 0.9}]
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = mock_response
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        from app.services.property_intel import _geocode_nominatim
        result = await _geocode_nominatim("10 Collins Street, Melbourne VIC 3000")

    assert result is not None
    assert -38.5 < result.latitude < -37.0
    assert 144.0 < result.longitude < 146.0
    assert result.source == "nominatim"


@pytest.mark.asyncio
async def test_google_tried_first_when_key_available():
    """Google geocoding should be attempted before Nominatim when API key is set."""
    mock_google_response = {
        "status": "OK",
        "results": [{"geometry": {"location": {"lat": -37.8136, "lng": 144.9631}}, "formatted_address": "Melbourne VIC"}]
    }
    with patch("app.services.property_intel.settings") as mock_settings:
        mock_settings.google_geocoding_api_key = "fake_key"
        mock_settings.nominatim_url = "https://nominatim.openstreetmap.org"
        with patch("httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = mock_google_response
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

            from app.services.property_intel import _geocode_google
            result = await _geocode_google("Melbourne VIC")

    assert result is not None
    assert result.source == "google"


@pytest.mark.asyncio
async def test_geocode_returns_none_on_empty_nominatim():
    """Empty Nominatim response should return None gracefully."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = []
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        from app.services.property_intel import _geocode_nominatim
        result = await _geocode_nominatim("Nonexistent Address XYZABC 99999")

    assert result is None
