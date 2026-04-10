                            
class TaskExecutor:
    def __init__(self, aegis_core=None):
        self.aegis_core = aegis_core

    async def execute(self, task_type: str, params: dict) -> dict:
        executors = {
            "music": self._music_task,
            "weather": self._weather_task,
            "search": self._search_task,
            "calendar": self._calendar_task,
            "email": self._email_task,
            "call": self._call_task,
            "home": self._home_task,
            "system": self._system_task,
        }

        executor = executors.get(task_type)
        if executor:
            return await executor(params)
        return {"status": "unknown_task"}

    async def _music_task(self, params: dict) -> dict:
        action = params.get("action", "play")
        music = getattr(self.aegis_core, "music", None) if self.aegis_core else None
        if not music or not hasattr(music, "play_request"):
            return {"status": "unavailable", "action": action, "reason": "Music service is not configured."}
        try:
            return music.play_request(query=params.get("query", ""), action=action)
        except Exception as e:
            return {"status": "error", "action": action, "reason": str(e)}

    async def _weather_task(self, params: dict) -> dict:
        weather_service = getattr(self.aegis_core, "weather_service", None) if self.aegis_core else None
        if not weather_service:
            return {"status": "unavailable", "reason": "Weather service is not configured."}
        try:
            return weather_service.get_current_weather(params.get("location", ""))
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _search_task(self, params: dict) -> dict:
        query = params.get("query", "")
        search_service = getattr(self.aegis_core, "web_search", None) if self.aegis_core else None
        if not search_service or not hasattr(search_service, "search"):
            return {"status": "unavailable", "query": query, "reason": "Search service is not configured."}
        try:
            return {"status": "success", "query": query, "results": search_service.search(query)}
        except Exception as e:
            return {"status": "error", "query": query, "reason": str(e)}

    async def _calendar_task(self, params: dict) -> dict:
        social_agent = getattr(self.aegis_core, "social_agent", None) if self.aegis_core else None
        if not social_agent or not hasattr(social_agent, "check_schedules"):
            return {"status": "unavailable", "reason": "Calendar integration is not configured."}
        try:
            return {"status": "success", "events": await social_agent.check_schedules()}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _email_task(self, params: dict) -> dict:
        social_agent = getattr(self.aegis_core, "social_agent", None) if self.aegis_core else None
        if not social_agent or not hasattr(social_agent, "check_email_status"):
            return {"status": "unavailable", "reason": "Email integration is not configured."}
        try:
            return {"status": "success", "emails": await social_agent.check_email_status()}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _call_task(self, params: dict) -> dict:
        call_agent = getattr(self.aegis_core, "call_agent", None) if self.aegis_core else None
        to_number = params.get("to")
        if not call_agent or not to_number:
            return {"status": "unavailable", "reason": "Call integration requires a destination number and LiveKit SIP."}
        try:
            return await call_agent.create_outbound_call(to_number)
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _home_task(self, params: dict) -> dict:
        homebot = getattr(self.aegis_core, "homebot", None) if self.aegis_core else None
        if not homebot or not hasattr(homebot, "execute_voice_command"):
            return {"status": "unavailable", "reason": "HomeBot integration is not configured."}
        try:
            return homebot.execute_voice_command(params.get("command", ""))
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _system_task(self, params: dict) -> dict:
        import psutil

        return {
            "cpu": f"{psutil.cpu_percent()}%",
            "memory": f"{psutil.virtual_memory().percent}%",
        }
