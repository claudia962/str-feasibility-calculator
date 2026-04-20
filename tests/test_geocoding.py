"""Test that Nominatim fallback geocodes Melbourne addresses."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mock_client(json_response):
    """Build a properly wired async httpx client mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_response
    mock_resp.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_resp)

    mock_client_class = MagicMock()
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_client_class


@pytest.mark.asyncio
async def test_nominatim_fallback_melbourne():
    """Nominatim fallback should resolve a Melbourne address to correct lat/lng range."""
    mock_response = [{"lat": "-37.8136", "lon": "144.9631",
                      "display_name": "Melbourne VIC, Australia", "importance": 0.9}]

    with patch("httpx.AsyncClient", _make_mock_client(mock_response)):
        from app.services import property_intel as pi
        result = await pi._geocode_nominatim("10 Collins Street, Melbourne VIC 3000")

    assert result is not None
    assert -38.5 < result.latitude < -37.0
    assert 144.0 < result.longitude < 146.0
    assert result.source == "nominatim"


@pytest.mark.asyncio
async def test_google_tried_first_when_key_available():
    """Google geocoding should be attempted before Nominatim when API key is set."""
    mock_google_response = {
        "status": "OK",
        "results": [{"geometry": {"location": {"lat": -37.8136, "lng": 144.9631}},
                     "formatted_address": "Melbourne VIC",
                     "address_components": []}]
    }

    with patch("app.services.property_intel.settings") as mock_settings, \
         patch("httpx.AsyncClient", _make_mock_client(mock_google_response)):
        mock_settings.google_geocoding_api_key = "fake_key"
        mock_settings.nominatim_url = "https://nominatim.openstreetmap.org"
        from app.services import property_intel as pi
        result = await pi._geocode_google("Melbourne VIC")

    assert result is not None
    assert result.source == "google"


@pytest.mark.asyncio
async def test_geocode_returns_none_on_empty_nominatim():
    """Empty Nominatim response should return None gracefully."""
    with patch("httpx.AsyncClient", _make_mock_client([])):
        from app.services import property_intel as pi
        result = await pi._geocode_nominatim("Nonexistent Address XYZABC 99999")

    assert result is None
