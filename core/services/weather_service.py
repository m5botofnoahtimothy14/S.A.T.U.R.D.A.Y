import logging
import os

import requests

logger = logging.getLogger("AEGIS.Services.Weather")

WEATHER_CODE_MAP = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


class WeatherService:
    def __init__(self):
        self.default_latitude = os.getenv("AEGIS_LATITUDE", "").strip()
        self.default_longitude = os.getenv("AEGIS_LONGITUDE", "").strip()
        self.default_location_name = os.getenv("AEGIS_LOCATION_NAME", "current location").strip()

    def get_current_weather(self, location_query: str = "") -> dict:
        location = self._resolve_location(location_query)
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current", {})
        weather_code = current.get("weather_code")
        return {
            "status": "success",
            "location": location["name"],
            "temperature_c": current.get("temperature_2m"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "condition": WEATHER_CODE_MAP.get(weather_code, "unknown"),
        }

    def _resolve_location(self, location_query: str) -> dict:
        query = (location_query or "").strip()
        if query:
            cleaned = query
            for prefix in ("weather in ", "forecast for ", "forecast in ", "temperature in "):
                if cleaned.lower().startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    break
            if cleaned:
                response = requests.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": cleaned, "count": 1, "language": "en", "format": "json"},
                    timeout=10,
                )
                response.raise_for_status()
                results = response.json().get("results") or []
                if not results:
                    raise RuntimeError(f"No geocoding result for '{cleaned}'.")
                first = results[0]
                return {
                    "name": first.get("name", cleaned),
                    "latitude": first["latitude"],
                    "longitude": first["longitude"],
                }

        if self.default_latitude and self.default_longitude:
            return {
                "name": self.default_location_name,
                "latitude": float(self.default_latitude),
                "longitude": float(self.default_longitude),
            }

        raise RuntimeError(
            "Weather location is not configured. Set AEGIS_LATITUDE and AEGIS_LONGITUDE or ask for a specific place."
        )
