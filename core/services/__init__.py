                      
def __getattr__(name):
    if name == "SATURDAYWindowsService":
        from .windows_service import SATURDAYWindowsService
        return SATURDAYWindowsService
    elif name == "TaskScheduler":
        from .task_scheduler import TaskScheduler
        return TaskScheduler
    elif name == "EnergyManager":
        from .energy_manager import EnergyManager
        return EnergyManager
    elif name in {"AutoUpdater", "AutoUpdateService"}:
        from .auto_update import AutoUpdateService
        return AutoUpdateService
    elif name == "WebSearchService":
        from .web_search import WebSearchService
        return WebSearchService
    elif name == "MusicManager":
        from .music_manager import MusicManager
        return MusicManager
    elif name == "WeatherService":
        from .weather_service import WeatherService
        return WeatherService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "SATURDAYWindowsService",
    "TaskScheduler", 
    "EnergyManager",
    "AutoUpdater",
    "AutoUpdateService",
    "WebSearchService",
    "MusicManager",
    "WeatherService"
]
