# services/windows_service.py
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import asyncio
import logging

# Ensure AEGIS root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Lazy import to avoid circular imports
_AEGISCore = None

def get_aegis_core():
    global _AEGISCore
    if _AEGISCore is None:
        from core.main import AEGISCore
        _AEGISCore = AEGISCore
    return _AEGISCore

class AEGISWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AEGIS_OS"
    _svc_display_name_ = "AEGIS Artificial Intelligence OS"
    _svc_description_ = "Core service for the AEGIS AI Operating System, managing vision, speech, and security."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.aegis = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.aegis:
            asyncio.run_coroutine_threadsafe(self.aegis.shutdown(), asyncio.get_event_loop())

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        # Initialize and run AEGIS core in the service thread
        try:
            self.aegis = AEGISCore()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Start the core
            loop.create_task(self.aegis.start())
            
            # Wait for stop event
            while True:
                # Check if stop event is signaled
                rc = win32event.WaitForSingleObject(self.stop_event, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                    
            loop.run_until_complete(self.aegis.shutdown())
        except Exception as e:
            logging.error(f"Service error: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AEGISWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AEGISWindowsService)
