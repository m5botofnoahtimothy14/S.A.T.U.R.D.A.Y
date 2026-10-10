"""SATURDAY package bootstrap — runs on ANY `import saturday.*`.

Windows consoles default to cp1252, which turns every emoji log line into
a UnicodeEncodeError crash. main.py reconfigures stdio for the CLI path,
but tests, scripts, and pythonw-launched code import modules directly —
so the package itself guarantees UTF-8-safe stdio here, once, guarded.
"""
try:
    import sys as _sys

    for _s in ("stdout", "stderr"):
        try:
            _stream = getattr(_sys, _s, None)
            if _stream is not None and hasattr(_stream, "reconfigure"):
                _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass
except Exception:
    pass
