#!/usr/bin/env python3
"""
AEGIS Windows Service Installer
Installs AEGIS as a Windows service that starts automatically on boot.
"""
import os
import sys
import subprocess

def install_service():
    """Install AEGIS as Windows service"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check for pywin32
    try:
        import win32service
        import win32serviceutil
        import win32api
    except ImportError:
        print("Installing pywin32...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pywin32"], check=True)
    
    service_code = f'''
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import sys
import os

class AEGISService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AEGIS"
    _svc_display_name_ = "AEGIS AI OS Server"
    _svc_description_ = "Self-owned AEGIS AI OS Server - Runs 24/7"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                            servicemanager.PYS_SERVICE_STARTED,
                            (self._svc_name_, ''))
        self.main()
        
    def main(self):
        os.chdir(r"{base_dir.replace(chr(92), chr(92)+chr(92))}")
        proc = subprocess.Popen(
            [sys.executable, "aegis_self_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        while True:
            if win32event.WaitForSingleObject(self.stop_event, 5000) == win32event.WAIT_OBJECT_0:
                proc.terminate()
                break
            if proc.poll() is not None:
                proc = subprocess.Popen(
                    [sys.executable, "aegis_self_server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AEGISService)
'''
    
    service_file = os.path.join(base_dir, "aegis_service.py")
    with open(service_file, "w") as f:
        f.write(service_code)
    
    print(f"Service file created: {service_file}")
    print("\nTo install the service, run:")
    print(f"  python {service_file} install")
    print("\nTo start the service:")
    print(f"  python {service_file} start")
    print("\nTo remove the service:")
    print(f"  python {service_file} remove")

if __name__ == "__main__":
    install_service()
