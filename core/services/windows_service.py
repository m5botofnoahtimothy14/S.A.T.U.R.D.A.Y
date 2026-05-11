                             
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import asyncio
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

_SATURDAYCore = None

def get_saturday_core():
    global _SATURDAYCore
    if _SATURDAYCore is None:
        from core.main import SATURDAYCore
        _SATURDAYCore = SATURDAYCore
    return _SATURDAYCore

class SATURDAYWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = "SATURDAY_OS"
    _svc_display_name_ = "SATURDAY Artificial Intelligence OS"
    _svc_description_ = "Core service for the SATURDAY AI Operating System, managing vision, speech, and security."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.saturday = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.saturday:
            asyncio.run_coroutine_threadsafe(self.saturday.shutdown(), asyncio.get_event_loop())

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
                                                             
        try:
            self.saturday = SATURDAYCore()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.create_task(self.saturday.start())
            
            while True:
                                                 
                rc = win32event.WaitForSingleObject(self.stop_event, 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                    
            loop.run_until_complete(self.saturday.shutdown())
        except Exception as e:
            logging.error(f"Service error: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SATURDAYWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SATURDAYWindowsService)
