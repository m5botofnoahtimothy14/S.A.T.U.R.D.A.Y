                       
import cv2
import numpy as np
import logging
from core.event_bus import EventBus

logger = logging.getLogger("AEGIS.Health.rPPG")

class RPPGEngine:
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.buffer_size = 150                      
        self.green_buffer = []
        self.times = []
        logger.info("rPPG Engine initialized.")

    def process_frame(self, frame, face_coords):
        
        if face_coords is None or len(face_coords) == 0:
            return

        x, y, w, h = face_coords[0]                  
        
        roi_x = x + int(w * 0.25)
        roi_y = y + int(h * 0.1)
        roi_w = int(w * 0.5)
        roi_h = int(h * 0.2)
        
        roi = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        if roi.size == 0:
            return

        avg_green = np.mean(roi[:, :, 1])
        self.green_buffer.append(avg_green)
        
        if len(self.green_buffer) > self.buffer_size:
            self.green_buffer.pop(0)
            
            if len(self.green_buffer) == self.buffer_size:
                bpm = self._estimate_bpm()
                if 40 < bpm < 180:
                    self.event_bus.publish("vitals_update", {"type": "heart_rate", "value": bpm, "method": "rPPG"})

    def _estimate_bpm(self):
        
        import scipy.fftpack
        from scipy.signal import butter, lfilter
        
        data = np.array(self.green_buffer)
        
        fps = 30.0                      
        lowcut = 0.66
        highcut = 3.0
        
        nyq = 0.5 * fps
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(2, [low, high], btype='band')
        
        filtered = lfilter(b, a, data)
        
        N = len(filtered)
        T = 1.0 / fps
        yf = scipy.fftpack.fft(filtered)
        xf = np.linspace(0.0, 1.0/(2.0*T), N//2)
        
        yf = np.abs(yf[:N//2])
        valid_indices = np.where((xf >= lowcut) & (xf <= highcut))[0]
        
        if len(valid_indices) == 0:
            return 0.0
            
        peak_idx = valid_indices[np.argmax(yf[valid_indices])]
        freq_hz = xf[peak_idx]
        
        bpm = freq_hz * 60.0
        return round(bpm, 1)
