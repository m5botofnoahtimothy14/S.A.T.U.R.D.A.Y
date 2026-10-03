import comtypes
from comtypes import CLSCTX_ALL
from ctypes import POINTER, c_float, c_int, c_uint32, c_ushort, c_ubyte
from comtypes import GUID, COMMETHOD, IUnknown

# Minimal Core Audio COM interfaces
class IMMDevice(IUnknown):
    _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    _methods_ = (
        COMMETHOD([], comtypes.HRESULT, "Activate",
                  (["in"], POINTER(GUID), "iid"),
                  (["in"], c_uint32, "dwClsCtx"),
                  (["in"], POINTER(c_uint32), "pActivationParams"),
                  (["out"], POINTER(POINTER(IUnknown)), "ppInterface")),
        COMMETHOD([], comtypes.HRESULT, "OpenPropertyStore"),
        COMMETHOD([], comtypes.HRESULT, "GetId"),
        COMMETHOD([], comtypes.HRESULT, "GetState"),
    )

class IMMDeviceCollection(IUnknown):
    _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")

class IMMDeviceEnumerator(IUnknown):
    _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB636636E}")
    _methods_ = (
        COMMETHOD([], comtypes.HRESULT, "EnumAudioEndpoints"),
        COMMETHOD([], comtypes.HRESULT, "GetDefaultAudioEndpoint",
                  (["in"], c_int, "dataFlow"),
                  (["in"], c_int, "role"),
                  (["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint")),
        COMMETHOD([], comtypes.HRESULT, "GetDevice"),
        COMMETHOD([], comtypes.HRESULT, "RegisterEndpointNotificationCallback"),
        COMMETHOD([], comtypes.HRESULT, "UnregisterEndpointNotificationCallback"),
    )

class IAudioEndpointVolume(IUnknown):
    _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
    _methods_ = (
        COMMETHOD([], comtypes.HRESULT, "RegisterControlChangeNotify"),
        COMMETHOD([], comtypes.HRESULT, "UnregisterControlChangeNotify"),
        COMMETHOD([], comtypes.HRESULT, "GetChannelCount"),
        COMMETHOD([], comtypes.HRESULT, "SetMasterVolumeLevel"),
        COMMETHOD([], comtypes.HRESULT, "SetMasterVolumeLevelScalar"),
        COMMETHOD([], comtypes.HRESULT, "GetMasterVolumeLevel"),
        COMMETHOD([], comtypes.HRESULT, "GetMasterVolumeLevelScalar",
                  (["out"], POINTER(c_float), "pfLevel")),
        COMMETHOD([], comtypes.HRESULT, "SetChannelVolumeLevel"),
        COMMETHOD([], comtypes.HRESULT, "SetChannelVolumeLevelScalar"),
        COMMETHOD([], comtypes.HRESULT, "GetChannelVolumeLevel"),
        COMMETHOD([], comtypes.HRESULT, "GetChannelVolumeLevelScalar"),
        COMMETHOD([], comtypes.HRESULT, "SetMute",
                  (["in"], c_int, "bMute"),
                  (["in"], POINTER(GUID), "pguidEventContext")),
        COMMETHOD([], comtypes.HRESULT, "GetMute",
                  (["out"], POINTER(c_int), "pbMute")),
    )

CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
eCapture, eCommunications = 1, 2
import ctypes as _ct
try:
    _ct.windll.ole32.CoInitializeEx(None, 0)
except Exception:
    pass
enumerator = comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
dev = POINTER(IMMDevice)()
enumerator.GetDefaultAudioEndpoint(eCapture, eCommunications, comtypes.byref(dev))
epv = POINTER(IAudioEndpointVolume)()
dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None, comtypes.byref(comtypes.cast(epv, POINTER(POINTER(IUnknown)))))
vol = epv.contents
lvl = c_float()
mute = c_int()
vol.GetMasterVolumeLevelScalar(comtypes.byref(lvl))
vol.GetMute(comtypes.byref(mute))
print(f"DEFAULT CAPTURE ENDPOINT: master_volume={lvl.value:.2f} muted={bool(mute.value)}", flush=True)
