

import os
import psutil
import logging
from datetime import datetime

logger = logging.getLogger("SATURDAY.DiskMonitor")

                                      
WARNING_THRESHOLD = 80.0                        
CRITICAL_THRESHOLD = 90.0                
EMERGENCY_THRESHOLD = 95.0                    

                  
SAFE_ZONE = 50.0                                      


def get_disk_info():
    
    disks = {}
    for partition in psutil.disk_partitions():
        if partition.fstype:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks[partition.device] = {
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total_gb': usage.total / (1024**3),
                    'used_gb': usage.used / (1024**3),
                    'free_gb': usage.free / (1024**3),
                    'percent': usage.percent
                }
            except:
                pass
    return disks


def check_disk_status():
    
    c_drive = psutil.disk_usage('C:\\')
    
    percent = c_drive.percent
    free_gb = c_drive.free / (1024**3)
    
    if percent >= EMERGENCY_THRESHOLD:
        return "EMERGENCY", percent, free_gb
    elif percent >= CRITICAL_THRESHOLD:
        return "CRITICAL", percent, free_gb
    elif percent >= WARNING_THRESHOLD:
        return "WARNING", percent, free_gb
    else:
        return "OK", percent, free_gb


def get_cleanup_recommendations():
    
    recommendations = []
    temp = os.environ.get('TEMP', 'C:\\Users\\Administrator\\AppData\\Local\\Temp')
    
                
    if os.path.exists(temp):
        temp_size = sum(os.path.getsize(os.path.join(temp, f)) 
                       for f in os.listdir(temp) 
                       if os.path.isfile(os.path.join(temp, f)) 
                       and 'saturday' not in f.lower()
                       and 'antigrav' not in f.lower()) / (1024**2)
        recommendations.append({
            'path': temp,
            'size_mb': temp_size,
            'safe': True,
            'description': 'Temporary files (excluding SATURDAY)'
        })
    
                  
    win_temp = 'C:\\Windows\\Temp'
    if os.path.exists(win_temp):
        try:
            win_size = sum(os.path.getsize(os.path.join(win_temp, f))
                          for f in os.listdir(win_temp)
                          if os.path.isfile(os.path.join(win_temp, f))) / (1024**2)
            recommendations.append({
                'path': win_temp,
                'size_mb': win_size,
                'safe': True,
                'description': 'Windows temporary files'
            })
        except:
            pass
    
               
    pip_cache = os.path.expanduser('~/.cache/pip')
    if os.path.exists(pip_cache):
        try:
            pip_size = sum(os.path.getsize(os.path.join(pip_cache, f))
                          for f in os.listdir(pip_cache)
                          if os.path.isfile(os.path.join(pip_cache, f))) / (1024**2)
            recommendations.append({
                'path': pip_cache,
                'size_mb': pip_size,
                'safe': True,
                'description': 'pip download cache'
            })
        except:
            pass
    
               
    log_dir = 'C:\\Users\\Administrator\\AppData\\Local\\CrashDumps'
    if os.path.exists(log_dir):
        try:
            log_size = sum(os.path.getsize(os.path.join(log_dir, f))
                          for f in os.listdir(log_dir)
                          if os.path.isfile(os.path.join(log_dir, f))) / (1024**2)
            recommendations.append({
                'path': log_dir,
                'size_mb': log_size,
                'safe': True,
                'description': 'Crash dump logs'
            })
        except:
            pass
    
    return sorted(recommendations, key=lambda x: x['size_mb'], reverse=True)


def auto_cleanup():
    
    cleaned_mb = 0
    cleaned_paths = []
    
    temp = os.environ.get('TEMP', 'C:\\Users\\Administrator\\AppData\\Local\\Temp')
    
                                                         
    if os.path.exists(temp):
        for f in os.listdir(temp):
            if 'saturday' in f.lower() or 'antigrav' in f.lower():
                continue
            fpath = os.path.join(temp, f)
            try:
                if os.path.isfile(fpath):
                    size = os.path.getsize(fpath) / (1024**2)
                    os.remove(fpath)
                    cleaned_mb += size
                    cleaned_paths.append(f)
                elif os.path.isdir(fpath):
                    import shutil
                    size = sum(os.path.getsize(os.path.join(dp, f)) 
                              for dp, dn, fn in os.walk(fpath) 
                              for f in fn) / (1024**2)
                    shutil.rmtree(fpath, ignore_errors=True)
                    cleaned_mb += size
                    cleaned_paths.append(f)
            except:
                pass
    
                     
    pip_cache = os.path.expanduser('~/.cache/pip')
    if os.path.exists(pip_cache):
        try:
            import shutil
            size = sum(os.path.getsize(os.path.join(pip_cache, f))
                      for f in os.listdir(pip_cache)
                      if os.path.isfile(os.path.join(pip_cache, f))) / (1024**2)
            shutil.rmtree(pip_cache, ignore_errors=True)
            cleaned_mb += size
            cleaned_paths.append('pip_cache')
        except:
            pass
    
    return cleaned_mb, cleaned_paths


def set_disk_alert():
    
                                                    
    return '''
# Run this as Administrator to set up disk monitoring:
schtasks /create /tn "SATURDAY_DiskMonitor" /tr "python D:\\SATURDAY\\disk_monitor.py" /sc hourly /ru Administrator
'''


if __name__ == "__main__":
    print("=" * 60)
    print("SATURDAY Disk Space Monitor")
    print("=" * 60)
    
    disks = get_disk_info()
    for device, info in disks.items():
        print(f"\n{info['mountpoint']}: {info['percent']:.1f}% used")
        print(f"  Total: {info['total_gb']:.1f} GB")
        print(f"  Used:  {info['used_gb']:.1f} GB")
        print(f"  Free:  {info['free_gb']:.1f} GB")
    
    print("\n" + "-" * 60)
    status, percent, free_gb = check_disk_status()
    print(f"\nC: Drive Status: {status}")
    print(f"  Used: {percent:.1f}% ({free_gb:.2f} GB free)")
    
    if status != "OK":
        print(f"\n{'-' * 60}")
        print("RECOMMENDATIONS:")
        recs = get_cleanup_recommendations()
        for i, rec in enumerate(recs[:5], 1):
            print(f"  {i}. {rec['description']}")
            print(f"     Path: {rec['path']}")
            print(f"     Size: {rec['size_mb']:.1f} MB")
        
        if percent >= WARNING_THRESHOLD:
            print(f"\n{'=' * 60}")
            print("WARNING: C drive is getting full!")
            print("Consider running auto_cleanup or manually clean temp files.")
            print("=" * 60)
    
    print()
