import sys
import time
import math
import bisect
import functools
import ctypes
from ctypes import wintypes
import os
import threading
import gc
try:
    import psutil
except ImportError:
    psutil = None


class MIB_IFROW(ctypes.Structure):
    _fields_ = [
        ("wszName", wintypes.WCHAR * 256),
        ("dwIndex", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("dwMtu", wintypes.DWORD),
        ("dwSpeed", wintypes.DWORD),
        ("dwPhysAddrLen", wintypes.DWORD),
        ("bPhysAddr", ctypes.c_byte * 8),
        ("dwAdminStatus", wintypes.DWORD),
        ("dwOperStatus", wintypes.DWORD),
        ("dwLastChange", wintypes.DWORD),
        ("dwInOctets", wintypes.DWORD),
        ("dwInUcastPkts", wintypes.DWORD),
        ("dwInNUcastPkts", wintypes.DWORD),
        ("dwInDiscards", wintypes.DWORD),
        ("dwInErrors", wintypes.DWORD),
        ("dwInUnknownProtos", wintypes.DWORD),
        ("dwOutOctets", wintypes.DWORD),
        ("dwOutUcastPkts", wintypes.DWORD),
        ("dwOutNUcastPkts", wintypes.DWORD),
        ("dwOutDiscards", wintypes.DWORD),
        ("dwOutErrors", wintypes.DWORD),
        ("dwOutQLen", wintypes.DWORD),
        ("dwDescrLen", wintypes.DWORD),
        ("bDescr", ctypes.c_byte * 256),
    ]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("sullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


if sys.platform == "win32":
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetShellWindow.restype = wintypes.HWND
        user32.GetDesktopWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.IsIconic.argtypes = (wintypes.HWND,)
        user32.IsIconic.restype = wintypes.BOOL
        user32.IsZoomed.argtypes = (wintypes.HWND,)
        user32.IsZoomed.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.SetProcessWorkingSetSize.argtypes = (wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t)
        kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
    except Exception:
        pass
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QSettings, QFileInfo, QSize
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QBrush,
    QPen,
    QFont,
    QCursor,
    QIcon,
    QPixmap,
    QLinearGradient,
    QRadialGradient,
    QFontMetricsF,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QLineEdit,
    QFileIconProvider,
)

import drop_vault
from PyQt6.QtCore import QUrl, QMimeData
from PyQt6.QtGui import QDrag
from media_controller import WindowsMediaController
from lyrics_controller import LyricsFetcher
from youtube_bridge import YouTubeBridge


@functools.lru_cache(maxsize=128)
def _font(family: str, size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(family)
    font.setPointSizeF(float(size))
    font.setWeight(weight)
    return font


def _interpolate_color(c1: QColor, c2: QColor, t: float) -> QColor:
    if t <= 0.001:
        return c1
    if t >= 0.999:
        return c2
    return QColor(
        int(round(c1.red() + (c2.red() - c1.red()) * t)),
        int(round(c1.green() + (c2.green() - c1.green()) * t)),
        int(round(c1.blue() + (c2.blue() - c1.blue()) * t)),
        int(round(c1.alpha() + (c2.alpha() - c1.alpha()) * t)),
    )


# Pre-allocated QColor constants for high-frequency rendering routines (zero allocation overhead)
_SPEC_TOP_C1 = QColor("#34E1F1")  # Electric Cyan
_SPEC_TOP_C2 = QColor("#A855F7")  # Purple
_SPEC_BOT_C1 = QColor("#6366F1")  # Violet
_SPEC_BOT_C2 = QColor("#E879F9")  # Magenta Pink

_ROBOT_CYAN = QColor("#00F5FF")
_ROBOT_LIGHT_CYAN = QColor("#38BDF8")
_ROBOT_MAGENTA = QColor("#FF007F")
_ROBOT_LIGHT_MAGENTA = QColor("#E879F9")
_ROBOT_DARK_BG = QColor("#060A12")
_ROBOT_SLATE = QColor("#334155")


class WindowsAudioMeter:
    """Real-time Windows WASAPI Core Audio peak meter reader with multi-device support."""

    def __init__(self):
        self.available = False
        self._GUID = None
        self._CLSID_MMDeviceEnumerator = None
        self._IID_IMMDeviceEnumerator = None
        self._IID_IAudioMeterInformation = None
        self._endpoints = []  # list of tuples: (meter_ptr, get_peak_fn, get_channels_fn, channel_count)
        self._last_refresh = 0.0
        self._init_com_types()
        self.refresh_devices()

    def _init_com_types(self):
        if sys.platform != "win32":
            return
        try:
            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8),
                ]

            self._GUID = _GUID

            def _get_guid(s):
                g = _GUID()
                ctypes.windll.ole32.IIDFromString(s, ctypes.byref(g))
                return g

            self._CLSID_MMDeviceEnumerator = _get_guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            self._IID_IMMDeviceEnumerator = _get_guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            self._IID_IAudioMeterInformation = _get_guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
        except Exception:
            pass

    def refresh_devices(self):
        """Discover and bind all active audio rendering endpoints."""
        if sys.platform != "win32" or not self._GUID:
            return
        try:
            ctypes.windll.ole32.CoInitialize(None)
            enumerator = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(self._CLSID_MMDeviceEnumerator),
                None,
                1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(self._IID_IMMDeviceEnumerator),
                ctypes.byref(enumerator),
            )
            if hr != 0 or not enumerator:
                return

            vtable_enum = ctypes.cast(enumerator, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            EnumAudioEndpoints = ctypes.WINFUNCTYPE(
                wintypes.HRESULT,
                ctypes.c_void_p,
                wintypes.UINT,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
            )(vtable_enum[3])

            new_endpoints = []

            # 1. Enumerate all active render endpoints (eRender=0, DEVICE_STATE_ACTIVE=1)
            col = ctypes.c_void_p()
            hr_col = EnumAudioEndpoints(enumerator, 0, 1, ctypes.byref(col))
            if hr_col == 0 and col:
                vcol = ctypes.cast(col, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                GetCount = ctypes.WINFUNCTYPE(
                    wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)
                )(vcol[3])
                Item = ctypes.WINFUNCTYPE(
                    wintypes.HRESULT, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)
                )(vcol[4])

                count = wintypes.UINT()
                GetCount(col, ctypes.byref(count))

                for i in range(count.value):
                    dev = ctypes.c_void_p()
                    if Item(col, i, ctypes.byref(dev)) == 0 and dev:
                        vdev = ctypes.cast(dev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                        Activate = ctypes.WINFUNCTYPE(
                            wintypes.HRESULT,
                            ctypes.c_void_p,
                            ctypes.POINTER(self._GUID),
                            wintypes.DWORD,
                            ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p),
                        )(vdev[3])
                        meter = ctypes.c_void_p()
                        if Activate(dev, ctypes.byref(self._IID_IAudioMeterInformation), 1, None, ctypes.byref(meter)) == 0 and meter:
                            vm = ctypes.cast(meter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                            gp = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)
                            )(vm[3])
                            GetMeteringChannelCount = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)
                            )(vm[4])
                            gch = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_float)
                            )(vm[5])
                            channels = wintypes.DWORD()
                            GetMeteringChannelCount(meter, ctypes.byref(channels))
                            ch_cnt = max(1, channels.value)
                            new_endpoints.append((meter, gp, gch, ch_cnt))

            # 2. Also ensure default console & multimedia endpoints are covered if collection was empty
            if not new_endpoints:
                GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                    wintypes.HRESULT,
                    ctypes.c_void_p,
                    wintypes.UINT,
                    wintypes.UINT,
                    ctypes.POINTER(ctypes.c_void_p),
                )(vtable_enum[4])

                for role in (0, 1):  # eConsole=0, eMultimedia=1
                    dev = ctypes.c_void_p()
                    if GetDefaultAudioEndpoint(enumerator, 0, role, ctypes.byref(dev)) == 0 and dev:
                        vdev = ctypes.cast(dev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                        Activate = ctypes.WINFUNCTYPE(
                            wintypes.HRESULT,
                            ctypes.c_void_p,
                            ctypes.POINTER(self._GUID),
                            wintypes.DWORD,
                            ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_void_p),
                        )(vdev[3])
                        meter = ctypes.c_void_p()
                        if Activate(dev, ctypes.byref(self._IID_IAudioMeterInformation), 1, None, ctypes.byref(meter)) == 0 and meter:
                            vm = ctypes.cast(meter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                            gp = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)
                            )(vm[3])
                            GetMeteringChannelCount = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)
                            )(vm[4])
                            gch = ctypes.WINFUNCTYPE(
                                wintypes.HRESULT, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_float)
                            )(vm[5])
                            channels = wintypes.DWORD()
                            GetMeteringChannelCount(meter, ctypes.byref(channels))
                            ch_cnt = max(1, channels.value)
                            new_endpoints.append((meter, gp, gch, ch_cnt))

            self._endpoints = new_endpoints
            self.available = len(self._endpoints) > 0
            self._last_refresh = time.perf_counter()
        except Exception:
            self.available = len(self._endpoints) > 0

    def get_levels(self):
        """Return (master_peak, left_peak, right_peak) from the active rendering device."""
        now = time.perf_counter()
        if not self._endpoints:
            self.refresh_devices()
        elif (now - self._last_refresh > 5.0) and not getattr(self, "_is_animating", False):
            self.refresh_devices()

        if not self.available or not self._endpoints:
            return 0.0, 0.0, 0.0

        max_peak = 0.0
        best_left = 0.0
        best_right = 0.0
        peak = ctypes.c_float()

        try:
            for meter, gp, gch, ch_cnt in self._endpoints:
                hr = gp(meter, ctypes.byref(peak))
                if hr == 0:
                    val = float(peak.value)
                    if val > max_peak:
                        max_peak = val
                        c_peaks = (ctypes.c_float * ch_cnt)()
                        gch(meter, ch_cnt, c_peaks)
                        best_left = float(c_peaks[0]) if ch_cnt >= 1 else val
                        best_right = float(c_peaks[1]) if ch_cnt >= 2 else best_left
            return max_peak, best_left, best_right
        except Exception:
            self._last_refresh = 0.0
            return 0.0, 0.0, 0.0

class WindowsAudioController:
    """Real-time Windows WASAPI Core Audio master volume & mute controller."""

    def __init__(self):
        self.available = False
        self._endpoint_volume = None
        self._get_scalar = None
        self._set_scalar = None
        self._get_mute = None
        self._set_mute = None
        self._last_refresh = 0.0
        self.refresh_device()

    def refresh_device(self):
        if sys.platform != "win32":
            return
        try:
            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8),
                ]

            def _get_guid(s):
                g = _GUID()
                ctypes.windll.ole32.IIDFromString(s, ctypes.byref(g))
                return g

            CLSID_MMDeviceEnumerator = _get_guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            IID_IMMDeviceEnumerator = _get_guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            IID_IAudioEndpointVolume = _get_guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")

            ctypes.windll.ole32.CoInitialize(None)
            enumerator = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(CLSID_MMDeviceEnumerator),
                None,
                1,
                ctypes.byref(IID_IMMDeviceEnumerator),
                ctypes.byref(enumerator),
            )
            if hr != 0 or not enumerator:
                return

            vtable_enum = ctypes.cast(enumerator, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                wintypes.HRESULT,
                ctypes.c_void_p,
                wintypes.UINT,
                wintypes.UINT,
                ctypes.POINTER(ctypes.c_void_p),
            )(vtable_enum[4])

            defaultDevice = ctypes.c_void_p()
            hr = GetDefaultAudioEndpoint(enumerator, 0, 1, ctypes.byref(defaultDevice))
            if hr != 0 or not defaultDevice:
                return

            dev_vtable = ctypes.cast(defaultDevice, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            Activate = ctypes.WINFUNCTYPE(
                wintypes.HRESULT,
                ctypes.c_void_p,
                ctypes.POINTER(_GUID),
                wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            )(dev_vtable[3])

            endpointVolume = ctypes.c_void_p()
            hr = Activate(defaultDevice, ctypes.byref(IID_IAudioEndpointVolume), 23, None, ctypes.byref(endpointVolume))
            if hr != 0 or not endpointVolume:
                return

            self._endpoint_volume = endpointVolume
            epv_vtable = ctypes.cast(endpointVolume, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

            self._set_scalar = ctypes.WINFUNCTYPE(
                wintypes.HRESULT, ctypes.c_void_p, ctypes.c_float, ctypes.c_void_p
            )(epv_vtable[7])
            self._get_scalar = ctypes.WINFUNCTYPE(
                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)
            )(epv_vtable[9])
            self._set_mute = ctypes.WINFUNCTYPE(
                wintypes.HRESULT, ctypes.c_void_p, wintypes.BOOL, ctypes.c_void_p
            )(epv_vtable[14])
            self._get_mute = ctypes.WINFUNCTYPE(
                wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)
            )(epv_vtable[15])

            self.available = True
            self._last_refresh = time.perf_counter()
        except Exception:
            self.available = False

    def get_volume(self) -> float:
        if not self._endpoint_volume:
            self.refresh_device()
        if self._endpoint_volume and self._get_scalar:
            try:
                val = ctypes.c_float()
                if self._get_scalar(self._endpoint_volume, ctypes.byref(val)) == 0:
                    return float(val.value)
            except Exception:
                self.refresh_device()
        return 0.5

    def set_volume(self, scalar: float):
        scalar = max(0.0, min(1.0, float(scalar)))
        if not self._endpoint_volume:
            self.refresh_device()
        if self._endpoint_volume and self._set_scalar:
            try:
                self._set_scalar(self._endpoint_volume, ctypes.c_float(scalar), None)
                if scalar > 0.0:
                    self.set_mute(False)
            except Exception:
                self.refresh_device()

    def is_muted(self) -> bool:
        if not self._endpoint_volume:
            self.refresh_device()
        if self._endpoint_volume and self._get_mute:
            try:
                m = wintypes.BOOL()
                if self._get_mute(self._endpoint_volume, ctypes.byref(m)) == 0:
                    return bool(m.value)
            except Exception:
                self.refresh_device()
        return False

    def set_mute(self, muted: bool):
        if not self._endpoint_volume:
            self.refresh_device()
        if self._endpoint_volume and self._set_mute:
            try:
                self._set_mute(self._endpoint_volume, wintypes.BOOL(muted), None)
            except Exception:
                self.refresh_device()


class BrowserTabDetector:

    """
    Mendeteksi apakah ada tab browser aktif yang berada tepat di bawah area notch (occluded).
    Menggunakan Windows UI Automation (UIA) native via ctypes untuk hit-testing super cepat (<2.5ms).
    """
    def __init__(self):
        self.initialized = False
        self.p_auto = None
        self.fn_from_point = None
        self.fn_get_parent = None
        self.p_walker = None
        self._init_uia()

    def _init_uia(self):
        if sys.platform != "win32":
            return
        try:
            from ctypes import wintypes
            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)

            class GUID(ctypes.Structure):
                _fields_ = [
                    ('Data1', wintypes.DWORD),
                    ('Data2', wintypes.WORD),
                    ('Data3', wintypes.WORD),
                    ('Data4', ctypes.c_byte * 8)
                ]

            def make_guid(d1, d2, d3, b):
                g = GUID()
                g.Data1, g.Data2, g.Data3 = d1, d2, d3
                for i in range(8):
                    g.Data4[i] = b[i]
                return g

            CLSID_CUIAutomation = make_guid(0xff48dba4, 0x60ef, 0x4201, [0xaa, 0x87, 0x54, 0x10, 0x3e, 0xef, 0x59, 0x4e])
            IID_IUIAutomation = make_guid(0x30cbe57d, 0xd9d0, 0x452a, [0xab, 0x13, 0x7a, 0xc5, 0xac, 0x48, 0x25, 0xee])

            p_auto = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(ctypes.byref(CLSID_CUIAutomation), None, 1, ctypes.byref(IID_IUIAutomation), ctypes.byref(p_auto))
            if hr != 0 or not p_auto.value:
                return

            self.p_auto = p_auto
            self.vtable = ctypes.cast(ctypes.cast(p_auto, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))

            class POINT(ctypes.Structure):
                _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]
            self.POINT = POINT

            class VARIANT(ctypes.Structure):
                _fields_ = [
                    ('vt', wintypes.WORD),
                    ('wReserved1', wintypes.WORD),
                    ('wReserved2', wintypes.WORD),
                    ('wReserved3', wintypes.WORD),
                    ('val', ctypes.c_void_p),
                    ('padding2', ctypes.c_uint64)
                ]
            self.VARIANT = VARIANT

            # Method 7: ElementFromPoint
            self.fn_from_point = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, self.POINT, ctypes.POINTER(ctypes.c_void_p))(self.vtable[7])

            # Method 14: get_ControlViewWalker
            p_walker = ctypes.c_void_p()
            fn_walker = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.vtable[14])
            hr_w = fn_walker(self.p_auto, ctypes.byref(p_walker))
            if hr_w == 0 and p_walker.value:
                self.p_walker = p_walker
                walker_vtable = ctypes.cast(ctypes.cast(p_walker, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))
                # Method 3 in IUIAutomationTreeWalker: GetParentElement
                self.fn_get_parent = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(walker_vtable[3])

            self.initialized = True
        except Exception:
            self.initialized = False

    def _release_com(self, p_unk):
        if not p_unk:
            return
        try:
            from ctypes import wintypes
            val = p_unk.value if hasattr(p_unk, 'value') else p_unk
            if not val or not isinstance(val, int) or val == 0:
                return
            p_void = ctypes.c_void_p(val)
            vtable = ctypes.cast(ctypes.cast(p_void, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))
            fn_rel = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])
            fn_rel(p_void)
        except Exception:
            pass

    def _is_tab_element(self, p_elem_val):
        if not p_elem_val:
            return False
        try:
            from ctypes import wintypes
            oleaut32 = ctypes.windll.oleaut32

            curr = p_elem_val
            to_release = []
            found_tab = False
            try:
                for depth in range(4):
                    if not curr:
                        break
                    v = ctypes.cast(ctypes.cast(curr, ctypes.POINTER(ctypes.c_void_p)).contents, ctypes.POINTER(ctypes.c_void_p))
                    fn_prop = ctypes.WINFUNCTYPE(wintypes.HRESULT, ctypes.c_void_p, wintypes.LONG, ctypes.POINTER(self.VARIANT))(v[10])

                    # 1. ControlType 30003: 50019 = UIA_TabItemControlTypeId
                    var_t = self.VARIANT()
                    hr_t = fn_prop(curr, 30003, ctypes.byref(var_t))
                    ctype = (var_t.val & 0xFFFFFFFF) if (hr_t == 0 and var_t.vt == 3) else 0
                    oleaut32.VariantClear(ctypes.byref(var_t))

                    # 50019 = UIA_TabItemControlTypeId (Individual Tab Page)
                    if ctype == 50019:
                        found_tab = True
                        break

                    # 50018 = UIA_TabControlTypeId (The TabStrip container bar)
                    # 50032 = Window, 50037 = TitleBar
                    # JIKA mencapai kontainer bilah tab kosong atau jendela tanpa menemukan tab individual,
                    # titik ini berada di area kosong bilah tab, BUKAN di atas tab!
                    if ctype in (50018, 50032, 50037):
                        break

                    # 2. LocalizedControlType 30004
                    # HANYA mencocokkan kata spesifik tab individual, BUKAN tab strip / bilah tab
                    var_l = self.VARIANT()
                    hr_l = fn_prop(curr, 30004, ctypes.byref(var_l))
                    loc = ctypes.wstring_at(var_l.val).lower().strip() if (hr_l == 0 and var_l.vt == 8 and var_l.val) else ''
                    oleaut32.VariantClear(ctypes.byref(var_l))
                    if loc in ("tab", "tab item", "tabitem", "item tab", "halaman tab"):
                        found_tab = True
                        break
                    if "strip" in loc or "bar" in loc or "bilah" in loc:
                        break

                    # 3. ClassName 30012
                    # HANYA tab individual, BUKAN TabStripView / TabStrip / TabBar
                    var_c = self.VARIANT()
                    hr_c = fn_prop(curr, 30012, ctypes.byref(var_c))
                    cls_name = ctypes.wstring_at(var_c.val).lower().strip() if (hr_c == 0 and var_c.vt == 8 and var_c.val) else ''
                    oleaut32.VariantClear(ctypes.byref(var_c))
                    if cls_name in ("tab", "browsertab", "tabitem", "tabitemview"):
                        found_tab = True
                        break
                    if "strip" in cls_name or "container" in cls_name:
                        break

                    # 4. Filter tombol '+' (New Tab / Tab Baru) agar tidak dianggap sebagai tab tertutup
                    var_n = self.VARIANT()
                    hr_n = fn_prop(curr, 30005, ctypes.byref(var_n))
                    name = ctypes.wstring_at(var_n.val).lower().strip() if (hr_n == 0 and var_n.vt == 8 and var_n.val) else ''
                    oleaut32.VariantClear(ctypes.byref(var_n))
                    if "new tab" in name or "tab baru" in name or name == "+":
                        break

                    # Ambil parent element untuk memeriksa apakah elemen saat ini adalah teks/tombol silang di dalam tab
                    if not self.fn_get_parent:
                        break
                    p_parent = ctypes.c_void_p()
                    hr_p = self.fn_get_parent(self.p_walker, curr, ctypes.byref(p_parent))
                    if hr_p != 0 or not p_parent.value:
                        break
                    to_release.append(p_parent.value)
                    curr = p_parent.value
            finally:
                for p in to_release:
                    self._release_com(p)
            return found_tab
        except Exception:
            return False

    def is_tab_at(self, x: int, y: int, exclude_hwnd: int = 0) -> bool:
        if not self.initialized or not self.p_auto or not self.fn_from_point:
            return False
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            class POINT_W(ctypes.Structure):
                _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]
            user32.WindowFromPoint.argtypes = (POINT_W,)
            user32.WindowFromPoint.restype = wintypes.HWND
            pt_win = POINT_W(int(x), int(y))
            win_at_pt = user32.WindowFromPoint(pt_win)
            if exclude_hwnd and win_at_pt == exclude_hwnd:
                return False

            p_elem = ctypes.c_void_p()
            pt = self.POINT(int(x), int(y))
            hr = self.fn_from_point(self.p_auto, pt, ctypes.byref(p_elem))
            if hr != 0 or not p_elem.value:
                return False
            try:
                return self._is_tab_element(p_elem.value)
            finally:
                self._release_com(p_elem)
        except Exception:
            return False

    def has_tab_under_notch(self, notch_x: float, notch_w: float, tab_y: int = 18, exclude_hwnd: int = 0) -> bool:
        """
        Memeriksa 9 titik horizontal di sepanjang rentang fisik notch dengan inset pelindung.
        Dynamic Island HANYA menyusut jika ada tab browser nyata yang secara fisik tertutup oleh badan notch.
        """
        if not self.initialized:
            return False
        try:
            inset = 8.0
            scan_w = max(10.0, notch_w - (inset * 2.0))
            start_x = notch_x + inset
            num_pts = 9
            step = scan_w / float(num_pts - 1)
            for i in range(num_pts):
                px = int(start_x + i * step)
                if self.is_tab_at(px, tab_y, exclude_hwnd=exclude_hwnd):
                    return True
                if self.is_tab_at(px, tab_y + 6, exclude_hwnd=exclude_hwnd):
                    return True
            return False
        except Exception:
            return False

    def cleanup(self):
        if self.p_walker:
            self._release_com(self.p_walker)
            self.p_walker = None
        if self.p_auto:
            self._release_com(self.p_auto)
            self.p_auto = None
        self.initialized = False


class DesktopDynamicIsland(QWidget):
    @staticmethod
    def _trim_memory():
        """
        Aggressively purges unused Python heap fragmentation and releases working set pages to Windows OS.
        Drops active RAM usage from ~55-60MB down to ~3-10MB without sacrificing any features or responsiveness.
        """
        try:
            gc.collect()
            if sys.platform == "win32":
                kernel32.SetProcessWorkingSetSize(kernel32.GetCurrentProcess(), ctypes.c_size_t(-1), ctypes.c_size_t(-1))
        except Exception:
            pass

    def __init__(self):
        super().__init__()

        # 1. Window Frameless, Always-on-Top, Transparan
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 2. Kanvas menempel tepat di bibir atas layar (y = 0)
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        screen_w = max(1, screen_geometry.width())
        self.canvas_w = min(920, screen_w)
        self.canvas_h = 180
        self.setGeometry(
            screen_geometry.left() + (screen_w - self.canvas_w) // 2,
            screen_geometry.top(),
            self.canvas_w,
            self.canvas_h,
        )

        # Keep the island centered and comfortably sized on both compact and
        # wide displays instead of relying on one fixed desktop width.
        self.expanded_w = min(
            float(self.canvas_w),
            max(180.0, min(360.0, float(screen_w - 24))),
        )
        self.lyrics_expanded_w = min(
            float(self.canvas_w - 72.0),
            640.0,
        )
        self.lyrics_open = False
        self.expanded_h = 144.0
        self.media_expanded_h = 168.0
        self.empty_expanded_h = 124.0
        self.open_height = self.empty_expanded_h

        # System Notification & Status state (Battery, CPU, RAM)
        self.system_battery_percent = 100
        self.system_battery_charging = True
        self.system_cpu_percent = 0.0
        self.system_ram_percent = 0.0
        self._last_stats_time = 0.0
        self._prev_idle_time = 0
        self._prev_kernel_time = 0
        self._prev_user_time = 0

        # User Profile State & Persistence
        default_user = "User"
        try:
            import getpass
            default_user = getpass.getuser().capitalize()
        except Exception:
            pass
        self.settings = QSettings("DynamicIsland", "DynamicIsland")
        self.default_profile_name = default_user
        self.default_profile_status = "System Operator"
        self.profile_name = str(self.settings.value("profile/name", self.default_profile_name))
        self.profile_status = str(self.settings.value("profile/status", self.default_profile_status))
        self.profile_editor_open = False
        self.btn_profile_rect = QRectF()
        self.profile_close_rect = QRectF()
        self.profile_reset_rect = QRectF()
        self.profile_cancel_rect = QRectF()
        self.profile_save_rect = QRectF()

        # Live Network Traffic Speed State (Upload & Download)
        self.net_upload_speed = 0.0
        self.net_download_speed = 0.0
        self.pencil_presence = 1.0 if not getattr(self, "has_media", False) else 0.0

        self.profile_name_input = QLineEdit(self)
        self.profile_status_input = QLineEdit(self)
        for editor in (self.profile_name_input, self.profile_status_input):
            editor.setStyleSheet("""
                QLineEdit {
                    color: #F1F5F9; background: rgba(255, 255, 255, 12);
                    border: 1px solid rgba(255, 255, 255, 24); border-radius: 6px;
                    padding: 2px 8px; font: 8.5pt "Segoe UI";
                    selection-background-color: #38BDF8;
                }
                QLineEdit:focus { border: 1.2px solid #38BDF8; background: rgba(255, 255, 255, 20); }
            """)
            editor.hide()

        # Real-Time WASAPI Audio Spectrum State (Dot-Matrix Equalizer)
        self.audio_meter = WindowsAudioMeter()
        self.eq_col_heights = [0.0] * 18
        self.eq_peak_dots = [0.0] * 18
        self.eq_peak_dot_hold = [0.0] * 18
        self._last_audio_peak = 0.0
        self._audio_rolling_max = 0.15
        self._audio_short_avg = 0.0
        self._audio_beat_punch = 0.0

        self.compact_clock_font = _font("Segoe UI", 8.5, QFont.Weight.DemiBold)
        self.compact_clock_text_width = math.ceil(
            QFontMetricsF(self.compact_clock_font).horizontalAdvance("12.59 PM")
        )
        self.compact_clock_box_width = self.compact_clock_text_width + 12.0
        # Apple standard compact Dynamic Island: spacious 192px width with generous breathing padding
        self.collapsed_w = 192.0
        self.collapsed_h = 34.0

        # Browser Auto-Shrink Micro-Notch State (4px line only when tabs are occluded by notch)
        self.is_browser_active = False
        self.is_browser_maximized = False
        self.is_tab_occluded = False
        self.next_tab_occlusion_poll = 0.0
        self.tab_detector = BrowserTabDetector()
        self._last_polled_hwnd = None
        self._last_idle_update_sec = 0
        self.micro_notch_w = 88.0
        self.micro_notch_h = 4.0

        # State Fisika Pegas (Menggunakan Float murni)
        self.cur_w = self.collapsed_w
        self.cur_h = self.collapsed_h
        self.vel_w = 0.0
        self.vel_h = 0.0

        # State Interaksi & Visual
        self.expand_progress = 0.0
        self.wave_phase = 0.0
        self.is_hovered = False
        self.is_playing = False
        self.hovered_btn = None
        self.btn_hover_anim = {
            "lyrics": 0.0,
            "speaker_mute": 0.0,
            "volume_slider": 0.0,
            "volume_down": 0.0,
            "volume_up": 0.0,
            "prev": 0.0,
            "play": 0.0,
            "next": 0.0,
            "settings": 0.0,
            "skip_ad": 0.0,
        }
        self.chevron_prev_opacity = 0.0
        self.chevron_next_opacity = 0.0
        self.page_scroll_pos = 0.0
        self.page_scroll_vel = 0.0
        self.lyrics_smooth_index = 0.0
        self.lyrics_anim_progress = 0.0
        self.vel_lyrics_anim = 0.0
        self.click_through_active = False
        self.media_state = "connecting"
        self.has_media = False
        self.youtube_ad_detected = False
        self.youtube_can_skip = False
        self.youtube_skip_stale = False
        self.youtube_skip_stale_clicked = False
        self.track_title = "Mencari pemutar media…"
        self.track_artist = "Windows Media Control"
        self.track_album = ""
        self.lyrics_track_key = None
        self.lyrics_cues = ()
        self.lyrics_timestamps = ()
        self.lyrics_status = "idle"
        self.lyrics_cache = {}
        self._lyrics_fetchers = []
        self._lyrics_retry_at = 0.0
        self.album_art = QPixmap()
        self.local_clock_text = self._format_local_clock()
        self.active_app_name = "Desktop"
        self.active_app_path = ""
        self.active_app_icon = QIcon()
        self.active_app_identity = ""
        self.active_app_icon_cache = {}
        self.next_active_app_poll = 0.0
        self.position_seconds = 0.0
        self.position_updated_at = time.perf_counter()
        self.position_rate = 0.0
        self.duration_seconds = 0.0
        self.can_play_pause = False
        self.can_previous = False
        self.can_next = False
        self.settings = QSettings("DynamicIsland", "DynamicIsland")
        self.default_gradient_top = QColor("#0C0F17")
        self.default_gradient_bottom = QColor("#030406")
        self.gradient_top = QColor(
            self.settings.value("appearance/gradientTop", self.default_gradient_top.name())
        )
        self.gradient_bottom = QColor(
            self.settings.value("appearance/gradientBottom", self.default_gradient_bottom.name())
        )
        if not self.gradient_top.isValid():
            self.gradient_top = QColor(self.default_gradient_top)
        if not self.gradient_bottom.isValid():
            self.gradient_bottom = QColor(self.default_gradient_bottom)
        self.gradient_middle = QColor(
            round((self.gradient_top.red() + self.gradient_bottom.red()) / 2),
            round((self.gradient_top.green() + self.gradient_bottom.green()) / 2),
            round((self.gradient_top.blue() + self.gradient_bottom.blue()) / 2),
        )
        self._cached_notch_key = None
        self._cached_notch_path = None
        self._last_idle_update_sec = 0
        self._next_clock_poll = 0.0
        self._robot_render_tick = 0

        # Hitbox Interaktif
        self.notch_rect = QRectF()
        self.btn_prev_rect = QRectF()
        self.btn_play_rect = QRectF()
        self.btn_next_rect = QRectF()
        self.btn_tab_previous_rect = QRectF()
        self.btn_tab_next_rect = QRectF()
        self.island_page_index = 0
        self.prev_island_page_index = 0
        self.tab_transition_t = 1.0
        self.total_pages = 4
        self.tab_dots_rects = []
        self.btn_lyrics_rect = QRectF()
        self.media_source_app = ""
        self.btn_volume_down_rect = QRectF()
        self.btn_volume_up_rect = QRectF()
        self.btn_speaker_rect = QRectF()
        self.vol_group_rect = QRectF()
        self.vol_track_rect = QRectF()
        self.is_dragging_volume = False
        self.is_seeking = False
        self.seek_rect = QRectF()
        self.volume_pulse = 0.0
        self.current_volume_scalar = 0.5
        self.is_audio_muted = False
        self.audio_controller = WindowsAudioController()
        self.btn_skip_ad_rect = QRectF()
        self.btn_settings_rect = QRectF()
        self.settings_open = False
        self.view_transition_snapshot = QPixmap()
        self.view_transition_started_at = 0.0
        self.view_transition_duration = 0.42
        self.view_transition_origin = QPointF(self.canvas_w / 2.0, self.collapsed_h / 2.0)
        self.settings_close_rect = QRectF()
        self.settings_reset_rect = QRectF()
        self.settings_save_rect = QRectF()
        self.settings_top_hitboxes = []
        self.settings_bottom_hitboxes = []
        self.appearance_original_top = QColor(self.gradient_top)
        self.appearance_original_bottom = QColor(self.gradient_bottom)
        self.appearance_top = QColor(self.gradient_top)
        self.appearance_bottom = QColor(self.gradient_bottom)
        self.gradient_palette = [
            QColor(color)
            for color in (
                "#171C2B", "#090B12", "#243249", "#4358A6",
                "#5865D8", "#1A6878", "#1D8A77", "#3D865D",
                "#A8782B", "#B85B3A", "#9E4868", "#724F9B",
            )
        ]
        self.gradient_top_input = QLineEdit(self)
        self.gradient_bottom_input = QLineEdit(self)
        for side, editor in (
            ("top", self.gradient_top_input),
            ("bottom", self.gradient_bottom_input),
        ):
            editor.setMaxLength(7)
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            editor.setPlaceholderText("#RRGGBB")
            editor.setAccessibleName(
                "Kode HEX warna bagian atas"
                if side == "top"
                else "Kode HEX warna bagian bawah"
            )
            editor.setStyleSheet("""
                QLineEdit {
                    color: #F1F5F9; background: rgba(255, 255, 255, 12);
                    border: 1px solid rgba(255, 255, 255, 24); border-radius: 6px;
                    padding: 2px 4px; font: 7.8pt "Consolas", monospace;
                    selection-background-color: #38BDF8;
                }
                QLineEdit:focus { border: 1.2px solid #38BDF8; background: rgba(255, 255, 255, 20); }
            """)
            editor.textChanged.connect(
                lambda value, color_side=side: self._on_gradient_hex_changed(color_side, value)
            )
            editor.editingFinished.connect(
                lambda color_side=side: self._normalize_gradient_input(color_side)
            )
            editor.hide()

        # Setup Win32 API untuk Click-Through dinamis
        self.hwnd = int(self.winId()) if sys.platform == "win32" else None
        self.set_click_through(True)

        # Inisialisasi resolusi timer 1ms Windows & thread latar belakang status jaringan
        if sys.platform == "win32":
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                pass

        self._stop_background_threads = False
        self._start_network_speed_thread()
        self.expanded_w = self._calculate_base_media_width()

        # 3. Real Delta-Time Loop menggunakan perf_counter()
        self.last_time = time.perf_counter()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(8)  # 125Hz high-refresh rate animation loop (buttery smooth on 60Hz, 120Hz, 144Hz displays)

        self._setup_tray()
        self.youtube_bridge = YouTubeBridge(self)
        self.drop_vault = drop_vault.DropVaultManager()
        self.setAcceptDrops(True)
        self.is_drag_hovered = False
        self.drag_start_pos = None
        self.dragged_vault_item = None
        self.btn_vault_qr_close_rect = QRectF()
        self.vault_scroll_x = 0.0
        self.is_panning_vault = False
        self.pan_start_x = 0.0
        self.pan_start_scroll_x = 0.0
        self.vault_item_rects = []
        self.vault_item_hover_anims = {}
        self.vault_qr_modal_anim = 0.0
        self.vault_qr_closing_item = None
        self.vault_qr_closing_qr = None
        self.scroll_indicator_t = 0.0
        self.vault_scroll_track_rect = QRectF()
        self._tab_1_content_h = 168.0
        self.youtube_bridge.ad_state_changed.connect(self.on_youtube_ad_state)
        self.youtube_bridge.ad_state_stale_changed.connect(self.on_youtube_ad_state_stale)
        if not self.youtube_bridge.start():
            self.tray.showMessage(
                "Integrasi YouTube tidak aktif",
                "Port lokal Dynamic Island sedang digunakan aplikasi lain.",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
        self.media_controller = WindowsMediaController(self)
        self.media_controller.media_updated.connect(self.on_media_updated)
        self.media_controller.command_result.connect(self.on_command_result)
        self.media_controller.start()

        # Schedule working set memory trim once all initial GUI & WinRT subsystems settle
        self._last_memory_trim = time.perf_counter()
        self._was_expanded = False
        QTimer.singleShot(1500, self._trim_memory)

    @property
    def is_spotify_active(self) -> bool:
        """Return True only when active media playback is from Spotify."""
        return self.has_media and "spotify" in self.media_source_app.lower()

    def cleanup(self):
        """Cleanly release high-resolution timer and background workers on application exit."""
        self._stop_background_threads = True
        if hasattr(self, "tab_detector"):
            self.tab_detector.cleanup()
        if sys.platform == "win32":
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass

    def _create_robot_mascot_icon(self) -> QIcon:
        """Render high-definition multi-resolution Cyberpunk Robot Mascot head for tray and window icon."""
        icon = QIcon()
        for size in (16, 20, 24, 32, 48, 64):
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            center = QPointF(size / 2.0, size / 2.0)
            scale = (size * 0.90) / 20.0
            self._draw_robot_mascot(painter, center, 0.0, scale=scale)
            painter.end()
            icon.addPixmap(pm)
        return icon

    def _setup_tray(self):
        robot_icon = self._create_robot_mascot_icon()
        self.setWindowIcon(robot_icon)

        self.tray = QSystemTrayIcon(robot_icon, self)
        self.tray.setToolTip("Dynamic Island — mencari pemutar media")
        menu = QMenu()
        menu.addAction("Tampilkan / sembunyikan pulau", self.toggle_visibility)
        menu.addAction("Cara pasang integrasi YouTube", self.open_youtube_guide)
        menu.addSeparator()
        menu.addAction("Keluar", self.exit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _begin_view_transition(self, origin: QPointF):
        """Capture the old view for a springy, source-anchored reveal."""
        if self.expand_progress <= 0.83 or not self.isVisible():
            self.view_transition_snapshot = QPixmap()
            return

        snapshot = self.grab()
        if snapshot.isNull():
            self.view_transition_snapshot = QPixmap()
            return

        self.view_transition_snapshot = snapshot
        self.view_transition_started_at = time.perf_counter()
        self.view_transition_origin = QPointF(origin)

    def _view_transition_reveal(self):
        if self.view_transition_snapshot.isNull():
            return None

        elapsed = time.perf_counter() - self.view_transition_started_at
        progress = max(0.0, min(1.0, elapsed / self.view_transition_duration))

        # A restrained back-ease gives the reveal a quick lift and soft settle.
        t = progress - 1.0
        eased = 1.0 + 2.35 * (t ** 3) + 1.35 * (t ** 2)

        start_size = 28.0
        start_rect = QRectF(
            self.view_transition_origin.x() - start_size / 2.0,
            self.view_transition_origin.y() - start_size / 2.0,
            start_size,
            start_size,
        )
        end_rect = QRectF(
            -self.canvas_w * 0.10,
            -self.canvas_h * 0.32,
            self.canvas_w * 1.20,
            self.canvas_h * 1.64,
        )
        reveal_rect = QRectF(
            start_rect.x() + (end_rect.x() - start_rect.x()) * eased,
            start_rect.y() + (end_rect.y() - start_rect.y()) * eased,
            start_rect.width() + (end_rect.width() - start_rect.width()) * eased,
            start_rect.height() + (end_rect.height() - start_rect.height()) * eased,
        )
        radius = min(30.0, max(10.0, reveal_rect.height() * 0.48))
        return progress, reveal_rect, radius

    def _paint_view_transition(self, painter: QPainter):
        """Reveal the next panel from the control that opened or closed it."""
        transition = self._view_transition_reveal()
        if transition is None:
            return

        progress, reveal_rect, radius = transition
        if progress >= 1.0:
            self.view_transition_snapshot = QPixmap()
            return

        ring_path = QPainterPath()
        ring_path.setFillRule(Qt.FillRule.OddEvenFill)
        ring_path.addRect(QRectF(0.0, 0.0, float(self.canvas_w), float(self.canvas_h)))
        ring_path.addRoundedRect(reveal_rect, radius, radius)

        painter.save()
        painter.setClipPath(ring_path, Qt.ClipOperation.IntersectClip)
        painter.drawPixmap(QPointF(0.0, 0.0), self.view_transition_snapshot)
        painter.restore()

        # A narrow mint edge gives the expanding mask a polished glass-like cue.
        edge_opacity = max(0.0, 1.0 - progress) ** 0.65
        painter.save()
        painter.setOpacity(painter.opacity() * edge_opacity)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(131, 227, 193, 36), 8.0))
        painter.drawRoundedRect(reveal_rect, radius, radius)
        painter.setPen(QPen(QColor(178, 255, 228, 175), 1.2))
        painter.drawRoundedRect(reveal_rect, radius, radius)
        painter.restore()

    def open_appearance_settings(self):
        """Show the gradient editor directly inside the expanded island."""
        if self.settings_open:
            return
        if self.profile_editor_open:
            self._close_profile_editor(save=False)
        self._begin_view_transition(self.btn_settings_rect.center())
        self.appearance_original_top = QColor(self.gradient_top)
        self.appearance_original_bottom = QColor(self.gradient_bottom)
        self.appearance_top = QColor(self.gradient_top)
        self.appearance_bottom = QColor(self.gradient_bottom)
        self.settings_open = True
        self._set_gradient_input_text("top", self.appearance_top)
        self._set_gradient_input_text("bottom", self.appearance_bottom)
        self.update()

    def _set_gradient_input_text(self, side: str, color: QColor):
        editor = self.gradient_top_input if side == "top" else self.gradient_bottom_input
        editor.blockSignals(True)
        editor.setText(color.name().upper())
        editor.blockSignals(False)

    def _update_gradient_middle(self):
        self.gradient_middle = QColor(
            round((self.gradient_top.red() + self.gradient_bottom.red()) / 2),
            round((self.gradient_top.green() + self.gradient_bottom.green()) / 2),
            round((self.gradient_top.blue() + self.gradient_bottom.blue()) / 2),
        )

    def _on_gradient_hex_changed(self, side: str, value: str):
        if len(value) != 7:
            return
        color = QColor(value)
        if not color.isValid():
            return
        if side == "top":
            self.appearance_top = color
            self.gradient_top = QColor(color)
        else:
            self.appearance_bottom = color
            self.gradient_bottom = QColor(color)
        self._update_gradient_middle()
        self.update()

    def _normalize_gradient_input(self, side: str):
        color = self.appearance_top if side == "top" else self.appearance_bottom
        self._set_gradient_input_text(side, color)

    def _select_gradient_color(self, side: str, color: QColor):
        if side == "top":
            self.appearance_top = QColor(color)
            self.gradient_top = QColor(color)
        else:
            self.appearance_bottom = QColor(color)
            self.gradient_bottom = QColor(color)
        self._update_gradient_middle()
        self._set_gradient_input_text(side, color)
        self.update()

    def _reset_appearance_settings(self):
        self.appearance_top = QColor(self.default_gradient_top)
        self.appearance_bottom = QColor(self.default_gradient_bottom)
        self.gradient_top = QColor(self.appearance_top)
        self.gradient_bottom = QColor(self.appearance_bottom)
        self._update_gradient_middle()
        self._set_gradient_input_text("top", self.appearance_top)
        self._set_gradient_input_text("bottom", self.appearance_bottom)
        self.update()

    def _close_appearance_settings(self, save: bool):
        self._begin_view_transition(self.settings_close_rect.center())
        if save:
            self.gradient_top = QColor(self.appearance_top)
            self.gradient_bottom = QColor(self.appearance_bottom)
            self.settings.setValue("appearance/gradientTop", self.gradient_top.name())
            self.settings.setValue("appearance/gradientBottom", self.gradient_bottom.name())
            self.settings.sync()
        else:
            self.gradient_top = QColor(self.appearance_original_top)
            self.gradient_bottom = QColor(self.appearance_original_bottom)
        self._update_gradient_middle()
        self.settings_open = False
        self.gradient_top_input.clearFocus()
        self.gradient_bottom_input.clearFocus()
        self.gradient_top_input.hide()
        self.gradient_bottom_input.hide()
        self.update()

    def _paint_appearance_settings(self, painter, expanded_x: float, expanded_w: float):
        """Paint an inline editor and place its two HEX fields inside the island."""
        self.settings_top_hitboxes = []
        self.settings_bottom_hitboxes = []
        self.settings_close_rect = QRectF(expanded_x + expanded_w - 38.0, 8.0, 20.0, 20.0)
        painter.save()

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(_font("Segoe UI", 9.2, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(expanded_x + 18.0, 6.0, expanded_w - 78.0, 24.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Pengaturan Warna Gradien",
        )

        close_hovered = self.hovered_btn == "settings_cancel"
        close_bg = _interpolate_color(QColor(255, 255, 255, 12), QColor(255, 255, 255, 34), 1.0 if close_hovered else 0.0)
        close_border = _interpolate_color(QColor(255, 255, 255, 18), QColor(255, 255, 255, 55), 1.0 if close_hovered else 0.0)
        painter.setPen(QPen(close_border, 0.8))
        painter.setBrush(QBrush(close_bg))
        painter.drawEllipse(self.settings_close_rect)
        close_center = self.settings_close_rect.center()
        painter.setPen(QPen(QColor("#94A3B8"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(
            QPointF(close_center.x() - 3.0, close_center.y() - 3.0),
            QPointF(close_center.x() + 3.0, close_center.y() + 3.0),
        )
        painter.drawLine(
            QPointF(close_center.x() + 3.0, close_center.y() - 3.0),
            QPointF(close_center.x() - 3.0, close_center.y() + 3.0),
        )

        label_width = 42.0
        field_width = 64.0
        chip_size = 15.0
        chip_gap = 5.0
        chip_start_x = expanded_x + 18.0 + label_width
        chip_end_x = expanded_x + expanded_w - 18.0 - field_width - 8.0
        chip_available_w = max(0.0, chip_end_x - chip_start_x)
        chip_count = min(
            len(self.gradient_palette),
            max(0, int((chip_available_w + chip_gap) // (chip_size + chip_gap))),
        )

        painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.Bold))
        for side, label, row_y, current_color, editor, hitboxes in (
            (
                "top", "ATAS", 38.0, self.appearance_top,
                self.gradient_top_input, self.settings_top_hitboxes,
            ),
            (
                "bottom", "BAWAH", 68.0, self.appearance_bottom,
                self.gradient_bottom_input, self.settings_bottom_hitboxes,
            ),
        ):
            painter.setPen(QColor("#64748B"))
            painter.drawText(
                QRectF(expanded_x + 18.0, row_y, label_width - 4.0, 22.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

            for index, color in enumerate(self.gradient_palette[:chip_count]):
                rect = QRectF(
                    chip_start_x + index * (chip_size + chip_gap),
                    row_y + (22.0 - chip_size) / 2.0,
                    chip_size,
                    chip_size,
                )
                selected = color.name().lower() == current_color.name().lower()
                painter.setPen(
                    QPen(QColor("#38BDF8") if selected else QColor(255, 255, 255, 30), 1.8 if selected else 0.8)
                )
                painter.setBrush(QBrush(color))
                painter.drawRoundedRect(rect, 4.0, 4.0)
                hitboxes.append((rect, QColor(color)))

            editor_x = expanded_x + expanded_w - 18.0 - field_width
            editor_y = row_y
            target_geometry = (
                int(round(editor_x)), int(round(editor_y)),
                int(round(field_width)), 22,
            )
            current_geometry = (
                editor.x(), editor.y(), editor.width(), editor.height(),
            )
            if current_geometry != target_geometry:
                editor.setGeometry(*target_geometry)
            transition = self._view_transition_reveal()
            reveal_rect = transition[1] if transition is not None else None
            if self.view_transition_snapshot.isNull() and not editor.isVisible():
                editor.show()
            elif (
                reveal_rect is not None
                and reveal_rect.contains(QRectF(editor.geometry()))
                and not editor.isVisible()
            ):
                editor.show()
            elif (
                reveal_rect is not None
                and not reveal_rect.contains(QRectF(editor.geometry()))
                and editor.isVisible()
            ):
                editor.hide()

        btn_y = 104.0
        self.settings_reset_rect = QRectF(expanded_x + 18.0, btn_y, 60.0, 24.0)
        self.settings_save_rect = QRectF(expanded_x + expanded_w - 18.0 - 68.0, btn_y, 68.0, 24.0)

        # Reset Button (Left)
        reset_hovered = self.hovered_btn == "settings_reset"
        reset_bg = _interpolate_color(QColor(255, 255, 255, 10), QColor(255, 255, 255, 26), 1.0 if reset_hovered else 0.0)
        reset_border = _interpolate_color(QColor(255, 255, 255, 18), QColor(255, 255, 255, 45), 1.0 if reset_hovered else 0.0)
        painter.setPen(QPen(reset_border, 0.8))
        painter.setBrush(QBrush(reset_bg))
        painter.drawRoundedRect(self.settings_reset_rect, 12.0, 12.0)
        painter.setPen(QColor("#94A3B8"))
        painter.setFont(_font("Segoe UI", 8.0, QFont.Weight.Medium))
        painter.drawText(self.settings_reset_rect, Qt.AlignmentFlag.AlignCenter, "Reset")

        # Live Preview Capsule (Center)
        prev_w = 80.0
        prev_rect = QRectF(expanded_x + (expanded_w - prev_w) / 2.0, btn_y + 2.0, prev_w, 20.0)
        prev_grad = QLinearGradient(prev_rect.topLeft(), prev_rect.bottomLeft())
        prev_grad.setColorAt(0.0, self.appearance_top)
        prev_grad.setColorAt(1.0, self.appearance_bottom)
        painter.setBrush(QBrush(prev_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 25), 0.8))
        painter.drawRoundedRect(prev_rect, 10.0, 10.0)
        painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.Medium))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(prev_rect, Qt.AlignmentFlag.AlignCenter, "Preview")

        # Save Button (Right)
        save_hovered = self.hovered_btn == "settings_save"
        save_bg = _interpolate_color(QColor("#F8FAFC"), QColor("#E2E8F0"), 1.0 if save_hovered else 0.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(save_bg))
        painter.drawRoundedRect(self.settings_save_rect, 12.0, 12.0)
        painter.setPen(QColor("#0F172A"))
        painter.setFont(_font("Segoe UI", 8.2, QFont.Weight.Bold))
        painter.drawText(self.settings_save_rect, Qt.AlignmentFlag.AlignCenter, "Simpan")
        painter.restore()

    def open_profile_editor(self):
        """Show the profile editor directly inside the expanded island."""
        if self.profile_editor_open:
            return
        if self.settings_open:
            self._close_appearance_settings(save=False)
        self._begin_view_transition(self.btn_profile_rect.center())
        self.profile_editor_open = True
        self.profile_name_input.setText(self.profile_name)
        self.profile_status_input.setText(self.profile_status)
        self.update()

    def _reset_profile_editor(self):
        self.profile_name_input.setText(self.default_profile_name)
        self.profile_status_input.setText(self.default_profile_status)
        self.update()

    def _close_profile_editor(self, save: bool):
        self._begin_view_transition(self.profile_close_rect.center())
        if save:
            new_name = self.profile_name_input.text().strip() or self.default_profile_name
            new_status = self.profile_status_input.text().strip() or self.default_profile_status
            self.profile_name = new_name
            self.profile_status = new_status
            self.settings.setValue("profile/name", self.profile_name)
            self.settings.setValue("profile/status", self.profile_status)
            self.settings.sync()
        self.profile_editor_open = False
        self.profile_name_input.clearFocus()
        self.profile_status_input.clearFocus()
        self.profile_name_input.hide()
        self.profile_status_input.hide()
        self.update()

    def _paint_profile_editor(self, painter, expanded_x: float, expanded_w: float):
        """Paint an authentic inline profile editor with Name and Status fields inside the island."""
        self.profile_close_rect = QRectF(expanded_x + expanded_w - 38.0, 8.0, 20.0, 20.0)
        painter.save()

        # Header Title
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(_font("Segoe UI", 9.2, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(expanded_x + 18.0, 6.0, expanded_w - 78.0, 24.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Edit Profil Pengguna",
        )

        # Close button (X)
        close_hovered = self.hovered_btn == "profile_cancel"
        close_bg = _interpolate_color(QColor(255, 255, 255, 12), QColor(255, 255, 255, 34), 1.0 if close_hovered else 0.0)
        close_border = _interpolate_color(QColor(255, 255, 255, 18), QColor(255, 255, 255, 55), 1.0 if close_hovered else 0.0)
        painter.setPen(QPen(close_border, 0.8))
        painter.setBrush(QBrush(close_bg))
        painter.drawEllipse(self.profile_close_rect)
        close_center = self.profile_close_rect.center()
        painter.setPen(QPen(QColor("#94A3B8"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(
            QPointF(close_center.x() - 3.0, close_center.y() - 3.0),
            QPointF(close_center.x() + 3.0, close_center.y() + 3.0),
        )
        painter.drawLine(
            QPointF(close_center.x() + 3.0, close_center.y() - 3.0),
            QPointF(close_center.x() - 3.0, close_center.y() + 3.0),
        )

        label_width = 54.0
        field_x = expanded_x + 18.0 + label_width
        field_w = expanded_w - 36.0 - label_width

        painter.setFont(_font("Segoe UI", 7.5, QFont.Weight.Bold))
        # Row 1: NAMA
        row1_y = 38.0
        painter.setPen(QColor("#64748B"))
        painter.drawText(
            QRectF(expanded_x + 18.0, row1_y, label_width - 4.0, 24.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "NAMA",
        )
        self.profile_name_input.setGeometry(int(round(field_x)), int(round(row1_y)), int(round(field_w)), 24)
        if not self.profile_name_input.isVisible():
            self.profile_name_input.show()

        # Row 2: STATUS
        row2_y = 69.0
        painter.setPen(QColor("#64748B"))
        painter.drawText(
            QRectF(expanded_x + 18.0, row2_y, label_width - 4.0, 24.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "STATUS",
        )
        self.profile_status_input.setGeometry(int(round(field_x)), int(round(row2_y)), int(round(field_w)), 24)
        if not self.profile_status_input.isVisible():
            self.profile_status_input.show()

        # Action Buttons on bottom row
        btn_y = 104.0
        btn_h = 24.0

        # Reset button (Left)
        self.profile_reset_rect = QRectF(expanded_x + 18.0, btn_y, 60.0, btn_h)
        reset_hovered = self.hovered_btn == "profile_reset"
        reset_bg = _interpolate_color(QColor(255, 255, 255, 10), QColor(255, 255, 255, 26), 1.0 if reset_hovered else 0.0)
        reset_border = _interpolate_color(QColor(255, 255, 255, 18), QColor(255, 255, 255, 45), 1.0 if reset_hovered else 0.0)
        painter.setPen(QPen(reset_border, 0.8))
        painter.setBrush(QBrush(reset_bg))
        painter.drawRoundedRect(self.profile_reset_rect, 12.0, 12.0)
        painter.setFont(_font("Segoe UI", 8.0, QFont.Weight.Medium))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(self.profile_reset_rect, Qt.AlignmentFlag.AlignCenter, "Reset")

        # Save button (Right)
        save_w = 68.0
        self.profile_save_rect = QRectF(expanded_x + expanded_w - 18.0 - save_w, btn_y, save_w, btn_h)
        save_hovered = self.hovered_btn == "profile_save"
        save_bg = _interpolate_color(QColor("#F8FAFC"), QColor("#E2E8F0"), 1.0 if save_hovered else 0.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(save_bg))
        painter.drawRoundedRect(self.profile_save_rect, 12.0, 12.0)
        painter.setPen(QColor("#0F172A"))
        painter.setFont(_font("Segoe UI", 8.2, QFont.Weight.Bold))
        painter.drawText(self.profile_save_rect, Qt.AlignmentFlag.AlignCenter, "Simpan")

        self.profile_cancel_rect = QRectF()
        painter.restore()

    def open_youtube_guide(self):
        candidates = []
        if getattr(sys, "frozen", False):
            if hasattr(sys, "_MEIPASS"):
                candidates.append(os.path.join(sys._MEIPASS, "youtube_extension", "README.md"))
            candidates.append(os.path.join(os.path.dirname(sys.executable), "youtube_extension", "README.md"))
        else:
            candidates.append(os.path.join(os.path.dirname(__file__), "youtube_extension", "README.md"))

        guide = next((p for p in candidates if os.path.isfile(p)), None)
        if guide:
            os.startfile(guide)
        else:
            self.tray.showMessage(
                "Panduan integrasi tidak ditemukan",
                "Pastikan ekstensi YouTube terpasang.",
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    def closeEvent(self, event):
        if hasattr(self, "drop_vault"):
            self.drop_vault.cleanup()
        super().closeEvent(event)

    def exit_app(self):
        if hasattr(self, "drop_vault"):
            self.drop_vault.cleanup()
        self.media_controller.stop()
        if self.media_controller.isRunning():
            self.media_controller.wait(2000)
        self.stop_lyrics_fetchers()
        self.youtube_bridge.stop()
        self.tray.hide()
        QApplication.quit()

    def on_media_updated(self, snapshot: dict):
        was_media = self.has_media
        was_playing = self.is_playing
        previous_title = self.track_title
        previous_artist = self.track_artist
        self.media_state = snapshot.get("state", "error")
        self.media_source_app = str(snapshot.get("source_app", "") or "")
        self.has_media = self.media_state == "media"
        if not self.has_media:
            if self.lyrics_open:
                self.lyrics_open = False
            self._clear_active_lyrics()
            self.track_album = ""
            self.album_art = QPixmap()
        elif not self.is_spotify_active:
            if self.lyrics_open:
                self.lyrics_open = False
            self._clear_active_lyrics()

        if self.has_media:
            if "artwork" in snapshot:
                self.album_art = QPixmap()
                artwork = snapshot.get("artwork")
                if artwork:
                    raw_pix = QPixmap()
                    if raw_pix.loadFromData(artwork):
                        if raw_pix.width() > 128 or raw_pix.height() > 128:
                            self.album_art = raw_pix.scaled(
                                128, 128,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        else:
                            self.album_art = raw_pix
            new_title = snapshot.get("title") or "Media tanpa judul"
            new_artist = snapshot.get("artist") or "Pemutar media"
            new_album = snapshot.get("album") or ""
            new_position = max(0.0, float(snapshot.get("position", 0.0)))
            new_is_playing = snapshot.get("is_playing", False)
            new_duration = max(0.0, float(snapshot.get("duration", 0.0)))
            playback_rate = snapshot.get("playback_rate")
            new_position_rate = (
                max(0.0, float(playback_rate))
                if playback_rate is not None
                else (1.0 if new_is_playing else 0.0)
            )
            if new_is_playing:
                new_position += max(0.0, float(snapshot.get("position_age", 0.0))) * new_position_rate
            if new_duration > 0:
                new_position = min(new_position, new_duration)
            now = time.perf_counter()
            same_track = (
                was_media
                and new_title == previous_title
                and new_artist == previous_artist
            )
            estimated_position = self.display_position_seconds(now)
            stale_timeline = (
                same_track
                and was_playing
                and new_is_playing
                and abs(new_position - self.position_seconds) <= 0.05
                and estimated_position - new_position > 0.2
            )
            if not stale_timeline:
                if (
                    same_track
                    and was_playing
                    and new_is_playing
                    and new_position >= self.position_seconds - 0.05
                    and abs(new_position - estimated_position) < 1.25
                ):
                    # Smooth small timing corrections instead of visibly jumping
                    # the progress indicator on every Windows poll.
                    self.position_seconds = (
                        estimated_position + (new_position - estimated_position) * 0.35
                    )
                else:
                    self.position_seconds = new_position
                self.position_updated_at = now

            self.track_title = new_title
            self.track_artist = new_artist
            self.track_album = new_album
            self.duration_seconds = new_duration
            self.is_playing = new_is_playing
            self.position_rate = new_position_rate if new_is_playing else 0.0
            self.can_play_pause = snapshot.get("can_play_pause", False)
            self.can_previous = snapshot.get("can_previous", False)
            self.can_next = snapshot.get("can_next", False)
            if self.is_spotify_active:
                self._request_lyrics(new_title, new_artist, new_album, new_duration)
            else:
                self._clear_active_lyrics()
            self.tray.setToolTip(f"Dynamic Island — {self.track_title}")
        elif self.media_state == "no_media":
            self.media_source_app = ""
            if self.lyrics_open:
                self.lyrics_open = False
            self._clear_active_lyrics()
            self.album_art = QPixmap()
            if self.youtube_ad_detected:
                self.track_title = "Iklan YouTube"
                self.track_artist = (
                    "YouTube tidak aktif · status terakhir"
                    if self.youtube_skip_stale
                    else (
                        "Tombol Skip iklan tersedia"
                        if self.youtube_can_skip
                        else "Iklan sedang diputar"
                    )
                )
            else:
                self.track_title = "Tidak ada media aktif"
                self.track_artist = "Putar musik atau video untuk mulai"
            self.position_seconds = 0.0
            self.position_updated_at = time.perf_counter()
            self.position_rate = 0.0
            self.duration_seconds = 0.0
            self.is_playing = False
            self.can_play_pause = self.can_previous = self.can_next = False
            self.tray.setToolTip(
                "Dynamic Island — iklan YouTube"
                if self.youtube_ad_detected
                else "Dynamic Island — tidak ada media aktif"
            )
        elif self.media_state == "dependency_missing":
            self.track_title = "Integrasi media belum terpasang"
            self.track_artist = "Jalankan install.bat lalu buka kembali"
            self.is_playing = False
            self.can_play_pause = self.can_previous = self.can_next = False
            self.tray.setToolTip("Dynamic Island — dependensi belum terpasang")
        elif self.media_state == "access_denied":
            self.track_title = "Perlu izin media Windows"
            self.track_artist = "Jalankan paket MSIX berizin media"
            self.is_playing = False
            self.can_play_pause = self.can_previous = self.can_next = False
            self.tray.setToolTip("Dynamic Island — izin Global Media Control diperlukan")
        elif self.media_state == "unsupported":
            self.track_title = "Aplikasi ini berjalan di Windows"
            self.track_artist = ""
            self.is_playing = False
            self.can_play_pause = self.can_previous = self.can_next = False
            self.tray.setToolTip("Dynamic Island — Windows saja")
        else:
            self.track_title = "Sesi media tidak tersedia"
            self.track_artist = snapshot.get("message") or "Mencoba menyambungkan kembali…"
            self.is_playing = False
            self.can_play_pause = self.can_previous = self.can_next = False
            self.tray.setToolTip("Dynamic Island — menyambungkan kembali ke media")

        self.expanded_w = self._calculate_base_media_width()
        self.update()

    def _request_lyrics(self, title: str, artist: str, album: str, duration: float):
        """Fetch synchronized lyrics once per track without blocking media updates."""
        key = (title.strip().casefold(), artist.strip().casefold(), album.strip().casefold())
        if key == self.lyrics_track_key:
            if self.lyrics_status != "error" or time.monotonic() < self._lyrics_retry_at:
                return

        self.lyrics_track_key = key
        self.lyrics_cues = ()
        self.lyrics_timestamps = ()
        self.lyrics_status = "loading"
        cached = self.lyrics_cache.get(key)
        if cached is not None:
            self.lyrics_cues, self.lyrics_status = cached
            self.lyrics_timestamps = tuple(cue[0] for cue in self.lyrics_cues)
            return

        fetcher = LyricsFetcher(
            key,
            title,
            artist,
            album,
            duration,
            self,
        )
        self._lyrics_fetchers.append(fetcher)
        fetcher.result_ready.connect(self._on_lyrics_result)
        fetcher.finished.connect(
            lambda worker=fetcher: self._retire_lyrics_fetcher(worker)
        )
        fetcher.start()

    def _on_lyrics_result(self, result: dict):
        key = tuple(result.get("key") or ())
        if len(key) != 3:
            return
        from lyrics_controller import _inject_instrumental_breaks
        raw_cues = [
            (max(0.0, float(timestamp)), str(line).strip() or "♪")
            for timestamp, line in result.get("cues", ())
        ]
        cues = tuple(_inject_instrumental_breaks(raw_cues, self.duration_seconds))
        status = str(result.get("status") or "error")
        if status == "error":
            if key == self.lyrics_track_key:
                self._lyrics_retry_at = time.monotonic() + 15.0
        else:
            self.lyrics_cache[key] = (cues, status)
            if len(self.lyrics_cache) > 64:
                self.lyrics_cache.pop(next(iter(self.lyrics_cache)))

        if key == self.lyrics_track_key:
            self.lyrics_cues = cues
            self.lyrics_timestamps = tuple(cue[0] for cue in cues)
            self.lyrics_status = status
            if cues:
                initial_idx = bisect.bisect_right(self.lyrics_timestamps, self.display_position_seconds()) - 1
                self.lyrics_smooth_index = float(max(0, initial_idx))
            else:
                self.lyrics_smooth_index = 0.0
            self.update()

    def _retire_lyrics_fetcher(self, worker):
        if worker in self._lyrics_fetchers:
            self._lyrics_fetchers.remove(worker)

    def stop_lyrics_fetchers(self):
        for worker in tuple(self._lyrics_fetchers):
            if worker.isRunning():
                worker.wait(10000)

    def _clear_active_lyrics(self):
        self.lyrics_track_key = None
        self.lyrics_cues = ()
        self.lyrics_timestamps = ()
        self.lyrics_status = "idle"
        self.lyrics_smooth_index = 0.0

    def _paint_current_lyrics(self, painter: QPainter, rect: QRectF):
        if not self.lyrics_cues:
            message = {
                "loading": "Mencari lirik tersinkron…",
                "unsynced": "Lirik tersinkron tidak tersedia",
                "not_found": "Lirik tersinkron tidak ditemukan",
                "error": "Lirik tidak dapat dimuat",
            }.get(self.lyrics_status, "")
            if message:
                painter.save()
                painter.setFont(_font("Segoe UI", 7.5, QFont.Weight.Medium))
                painter.setPen(QColor("#8793A5"))
                message = painter.fontMetrics().elidedText(
                    message, Qt.TextElideMode.ElideRight, max(1, int(rect.width()))
                )
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    message,
                )
                painter.restore()
            return

        current_index = bisect.bisect_right(
            self.lyrics_timestamps, self.display_position_seconds()
        ) - 1
        visible_cues = (
            (None, None, self.lyrics_cues[0])
            if current_index < 0
            else (
                self.lyrics_cues[current_index - 1] if current_index > 0 else None,
                self.lyrics_cues[current_index],
                self.lyrics_cues[current_index + 1]
                if current_index + 1 < len(self.lyrics_cues)
                else None,
            )
        )
        row_y = (rect.top(), rect.top() + 14.0, rect.top() + 28.0)
        for row, (cue, y) in enumerate(zip(visible_cues, row_y)):
            if cue is None:
                continue
            text = cue[1]
            active = row == 1
            font = _font(
                "Segoe UI",
                8.5 if active else 7.5,
                QFont.Weight.DemiBold if active else QFont.Weight.Medium,
            )
            painter.save()
            painter.setFont(font)
            painter.setPen(QColor("#B6F1DA" if active else "#8995A8"))
            elided = painter.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, max(1, int(rect.width()))
            )
            painter.drawText(
                QRectF(rect.left(), y, rect.width(), 14.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )
            painter.restore()

    def _paint_side_lyrics_panel(self, painter: QPainter, panel_rect: QRectF):
        """Draw Spotify-style synchronized lyrics spanning the full island height."""
        if panel_rect.width() < 2.0 or panel_rect.height() < 40.0:
            return

        panel_x = panel_rect.left()
        panel_y = panel_rect.top()
        panel_w = panel_rect.width()
        panel_h = panel_rect.height()

        painter.save()

        # Clip strictly to the panel bounds with safe top/bottom margin
        clip_top = 32.0
        clip_bottom = 8.0
        clip_rect = QRectF(
            panel_x,
            panel_y + clip_top,
            panel_w,
            panel_h - clip_top - clip_bottom,
        )
        painter.setClipRect(clip_rect)

        if not self.lyrics_cues:
            message = {
                "loading": "Mencari lirik tersinkron…",
                "unsynced": "Lirik tersinkron tidak tersedia",
                "not_found": "Lirik tersinkron belum ditemukan",
                "error": "Lirik tidak dapat dimuat",
            }.get(self.lyrics_status, "Tidak ada lirik aktif")
            painter.setFont(_font("Segoe UI", 9.0, QFont.Weight.Medium))
            painter.setPen(QColor("#778496"))
            elided = painter.fontMetrics().elidedText(
                message, Qt.TextElideMode.ElideRight, max(1, int(max(panel_w, 200.0) - 20.0))
            )
            painter.drawText(QRectF(panel_x, panel_y, max(panel_w, 200.0), panel_h), Qt.AlignmentFlag.AlignCenter, elided)
            painter.restore()
            return

        current_float = getattr(self, "lyrics_smooth_index", 0.0)
        center_y = panel_y + (panel_h / 2.0)
        avail_w = max(10.0, panel_w - 16.0)
        spacing = 8.0

        min_idx = max(0, int(math.floor(current_float - 3.0)))
        max_idx = min(len(self.lyrics_cues), int(math.ceil(current_float + 4.0)))

        cue_metrics = {}
        for idx in range(min_idx, max_idx):
            cue = self.lyrics_cues[idx]
            raw_text = cue[1].strip() if (isinstance(cue, (list, tuple)) and len(cue) > 1) else str(cue).strip()
            is_instrumental = not raw_text or raw_text in ("♪", "♫", "♩", "♪   ♪   ♪", "(instrumental)", "[instrumental]")
            text = "♪" if is_instrumental else raw_text
            diff = idx - current_float
            prox = max(0.0, 1.0 - abs(diff) * 0.40)
            prox_eased = prox ** 1.6
            weight = QFont.Weight.Bold if prox > 0.65 else (QFont.Weight.DemiBold if prox > 0.35 else QFont.Weight.Medium)
            font_family = "Segoe UI Symbol" if is_instrumental else "Segoe UI"
            f_size = 11.0 if is_instrumental else 9.5
            font = _font(font_family, f_size, weight)
            fm = QFontMetricsF(font)

            if is_instrumental:
                cue_metrics[idx] = (20.0, 1, font, text, prox, prox_eased)
            else:
                single_w = fm.horizontalAdvance(text)
                if single_w <= avail_w:
                    cue_metrics[idx] = (20.0, 1, font, text, prox, prox_eased)
                else:
                    br = fm.boundingRect(QRectF(0, 0, avail_w, 200), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), text)
                    lines = max(1, min(2, int(round(br.height() / max(1.0, fm.lineSpacing())))))
                    box_h = max(20.0, br.height() + 2.0)
                    cue_metrics[idx] = (box_h, lines, font, text, prox, prox_eased)

        # Compute relative cumulative vertical offsets relative to floor(current_float)
        base_k = int(math.floor(current_float))
        rel_y = {base_k: 0.0}
        for idx in range(base_k + 1, max_idx):
            prev_h = cue_metrics.get(idx - 1, (20.0,))[0]
            cur_h = cue_metrics.get(idx, (20.0,))[0]
            rel_y[idx] = rel_y[idx - 1] + (prev_h + cur_h) / 2.0 + spacing

        for idx in range(base_k - 1, min_idx - 1, -1):
            next_h = cue_metrics.get(idx + 1, (20.0,))[0]
            cur_h = cue_metrics.get(idx, (20.0,))[0]
            rel_y[idx] = rel_y[idx + 1] - (next_h + cur_h) / 2.0 - spacing

        # Continuous interpolated camera scroll between cues
        frac = current_float - base_k
        next_offset = rel_y.get(base_k + 1, rel_y[base_k] + 28.0)
        scroll_y = rel_y[base_k] + (next_offset - rel_y[base_k]) * frac

        for idx in range(min_idx, max_idx):
            if idx not in cue_metrics:
                continue
            h_box, lines, font, text, prox, prox_eased = cue_metrics[idx]

            cue_center_y = center_y + (rel_y[idx] - scroll_y)
            cue_top_y = cue_center_y - (h_box / 2.0)

            # Edge fade calculation (smooth fade out at top and bottom margins)
            edge_dist = min(cue_center_y - (panel_y + 12.0), (panel_y + panel_h - 12.0) - cue_center_y)
            edge_fade = max(0.0, min(1.0, edge_dist / 24.0))

            base_color = QColor(114, 130, 150)
            active_color = QColor(255, 255, 255)
            text_color = _interpolate_color(base_color, active_color, prox_eased)
            alpha = int(255 * (0.28 + 0.72 * prox_eased) * edge_fade)
            text_color.setAlpha(alpha)

            painter.setFont(font)
            painter.setPen(text_color)

            draw_rect = QRectF(panel_x + 8.0, cue_top_y, avail_w, h_box)
            if lines > 1:
                flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                painter.drawText(draw_rect, flags, text)
            else:
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                painter.drawText(draw_rect, align, text)

        painter.restore()

    def on_youtube_ad_state(self, is_ad: bool, can_skip: bool):
        self.youtube_ad_detected = bool(is_ad)
        self.youtube_can_skip = self.youtube_ad_detected and bool(can_skip)
        if not self.youtube_can_skip:
            self.youtube_skip_stale = False
            self.youtube_skip_stale_clicked = False
            self.btn_skip_ad_rect = QRectF()
        if not self.has_media:
            if self.youtube_ad_detected:
                self.track_title = "Iklan YouTube"
                self.track_artist = (
                    "Tombol Skip iklan tersedia"
                    if self.youtube_can_skip
                    else "Iklan sedang diputar"
                )
            elif self.media_state == "no_media":
                self.track_title = "Tidak ada media aktif"
                self.track_artist = "Putar musik atau video untuk mulai"
                self.tray.setToolTip("Dynamic Island — tidak ada media aktif")
            if self.youtube_ad_detected:
                self.tray.setToolTip("Dynamic Island — iklan YouTube")
        self.update()

    def on_youtube_ad_state_stale(self, stale: bool):
        self.youtube_skip_stale = bool(stale and self.youtube_can_skip)
        if not self.youtube_skip_stale:
            self.youtube_skip_stale_clicked = False
        if not self.has_media and self.youtube_can_skip:
            self.track_artist = (
                "YouTube tidak aktif · status terakhir"
                if self.youtube_skip_stale
                else "Tombol Skip iklan tersedia"
            )
        self.update()

    def display_position_seconds(self, now: float | None = None) -> float:
        """Interpolate the last Windows timeline sample between media polls."""
        position = max(0.0, self.position_seconds)
        if self.has_media and self.is_playing:
            sample_time = time.perf_counter() if now is None else now
            position += max(0.0, sample_time - self.position_updated_at) * self.position_rate
        if self.duration_seconds > 0:
            position = min(position, self.duration_seconds)
        return position

    def on_command_result(self, command: str, succeeded: bool, message: str):
        if succeeded:
            return
        detail = message or "Pemutar media tidak menerima perintah ini."
        self.tray.showMessage(
            "Kontrol media tidak berhasil",
            detail,
            QSystemTrayIcon.MessageIcon.Warning,
            4000,
        )

    def _button_at(self, local_pos: QPointF):
        if not self.view_transition_snapshot.isNull():
            return None
        if self.expand_progress <= 0.88:
            return None
        if self.settings_open:
            if self.settings_close_rect.contains(local_pos):
                return "settings_cancel"
            if self.settings_reset_rect.contains(local_pos):
                return "settings_reset"
            if self.settings_save_rect.contains(local_pos):
                return "settings_save"
            for side, hitboxes in (
                ("top", self.settings_top_hitboxes),
                ("bottom", self.settings_bottom_hitboxes),
            ):
                for rect, color in hitboxes:
                    if rect.contains(local_pos):
                        return f"gradient_{side}:{color.name()}"
            return None
        if self.profile_editor_open:
            if self.profile_cancel_rect.contains(local_pos) or self.profile_close_rect.contains(local_pos):
                return "profile_cancel"
            if self.profile_reset_rect.contains(local_pos):
                return "profile_reset"
            if self.profile_save_rect.contains(local_pos):
                return "profile_save"
            return None
        if self.btn_settings_rect.contains(local_pos):
            return "settings"
        if not self.btn_profile_rect.isEmpty() and self.btn_profile_rect.contains(local_pos):
            return "profile_edit"
        if self.btn_tab_previous_rect.contains(local_pos):
            return "tab_previous"
        if self.btn_tab_next_rect.contains(local_pos):
            return "tab_next"
        for idx, rect in enumerate(self.tab_dots_rects):
            if rect.contains(local_pos):
                return f"tab_dot:{idx}"

        # Hit testing for Tab 2 (The Drop Vault)
        if self.island_page_index == 1:
            if getattr(self, "btn_vault_clear_all_rect", QRectF()).contains(local_pos):
                return "vault_clear_all"
            if getattr(self, "btn_vault_qr_close_rect", QRectF()).contains(local_pos):
                return "vault_qr_close"
            for entry in getattr(self, "vault_item_rects", []):
                if len(entry) == 6:
                    item_id, item_full_rect, btn_cut_rect, btn_qr_rect, btn_del_rect, is_hovered = entry
                    if is_hovered:
                        if btn_del_rect.contains(local_pos):
                            return f"vault_remove:{item_id}"
                        if btn_cut_rect.contains(local_pos):
                            return f"vault_cut:{item_id}"
                        if btn_qr_rect.contains(local_pos):
                            return f"vault_qr:{item_id}"
                    if item_full_rect.contains(local_pos):
                        return f"vault_card:{item_id}"
            return None

        if self.island_page_index != 0:
            return None
        skip_ready = self.youtube_ad_detected and self.youtube_can_skip
        if skip_ready and self.btn_skip_ad_rect.contains(local_pos):
            return "skip_ad_stale" if self.youtube_skip_stale else "skip_ad"
        if not self.has_media and not skip_ready:
            return None
        if self.is_spotify_active and self.btn_lyrics_rect.contains(local_pos):
            return "lyrics"
        if getattr(self, "btn_speaker_rect", QRectF()).contains(local_pos):
            return "speaker_mute"
        if getattr(self, "vol_group_rect", QRectF()).contains(local_pos):
            return "volume_slider"
        for name, rect, enabled in (
            ("volume_down", self.btn_volume_down_rect, True),
            ("volume_up", self.btn_volume_up_rect, True),
            ("play", self.btn_play_rect, self.can_play_pause),
            ("prev", self.btn_prev_rect, self.can_previous),
            ("next", self.btn_next_rect, self.can_next),
        ):
            if enabled and rect.contains(local_pos):
                return name
        return None

    @staticmethod
    def _draw_lyrics_icon(painter, rect: QRectF, active: bool, color: QColor):
        """Draw authentic Apple Music quote.bubble SF Symbol for synced lyrics."""
        cx, cy = rect.center().x(), rect.center().y()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bubble = QPainterPath()
        bx, by, bw, bh = cx - 6.2, cy - 6.0, 12.4, 9.2
        bubble.addRoundedRect(QRectF(bx, by, bw, bh), 2.6, 2.6)

        tail = QPainterPath()
        tail.moveTo(cx - 4.2, cy + 2.5)
        tail.lineTo(cx - 5.8, cy + 6.0)
        tail.lineTo(cx - 1.5, cy + 3.0)
        tail.closeSubpath()
        full_bubble = bubble.united(tail).simplified()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(full_bubble)

        # Quotes inside the bubble
        quote_col = QColor("#0B0F19") if active else QColor("#121824")
        painter.setPen(QPen(quote_col, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(QBrush(quote_col))

        # Left quote
        painter.drawEllipse(QPointF(cx - 2.8, cy - 2.0), 0.9, 0.9)
        painter.drawLine(QPointF(cx - 2.8, cy - 1.6), QPointF(cx - 3.4, cy + 0.4))

        # Right quote
        painter.drawEllipse(QPointF(cx + 1.6, cy - 2.0), 0.9, 0.9)
        painter.drawLine(QPointF(cx + 1.6, cy - 1.6), QPointF(cx + 1.0, cy + 0.4))
        painter.restore()

    @staticmethod
    def _draw_animated_speaker_icon(painter, cx: float, cy: float, level: float, pulse: float = 0.0, is_mute: bool = False, color: QColor = QColor("#CBD5E1")):
        """
        Renders the dynamic animated speaker icon with refined proportions:
        - Clean padding from capsule edge
        - Soundwaves scaled to fit elegantly within the capsule without clipping
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if abs(pulse) > 0.01:
            painter.translate(cx, cy)
            scale_fac = 1.0 + pulse * 0.18
            painter.scale(scale_fac, scale_fac)
            painter.translate(-cx, -cy)

        # 1. Speaker Cone Body
        cone_w = 3.5
        cone_h = 4.8
        flare_w = 3.8
        flare_h = 9.2

        body = QPainterPath()
        body.moveTo(cx - 6.5, cy - cone_h / 2.0)
        body.lineTo(cx - 6.5 + cone_w, cy - cone_h / 2.0)
        body.lineTo(cx - 6.5 + cone_w + flare_w, cy - flare_h / 2.0)
        body.lineTo(cx - 6.5 + cone_w + flare_w, cy + flare_h / 2.0)
        body.lineTo(cx - 6.5 + cone_w, cy + cone_h / 2.0)
        body.lineTo(cx - 6.5, cy + cone_h / 2.0)
        body.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(body)

        # 2. Soundwaves / Mute State
        if is_mute or level <= 0.001:
            painter.setPen(QPen(QColor("#F87171"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            cross_cx = cx + 4.5
            painter.drawLine(QPointF(cross_cx - 2.5, cy - 2.5), QPointF(cross_cx + 2.5, cy + 2.5))
            painter.drawLine(QPointF(cross_cx - 2.5, cy + 2.5), QPointF(cross_cx + 2.5, cy - 2.5))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            w1_alpha = min(255, int(255 * min(1.0, level / 0.33)))
            w1_col = QColor(color.red(), color.green(), color.blue(), w1_alpha)
            painter.setPen(QPen(w1_col, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            wave1 = QPainterPath()
            wave1.arcMoveTo(QRectF(cx + 1.2, cy - 3.2, 3.6, 6.4), -45)
            wave1.arcTo(QRectF(cx + 1.2, cy - 3.2, 3.6, 6.4), -45, 90)
            painter.drawPath(wave1)

            if level > 0.33:
                w2_alpha = min(255, int(255 * min(1.0, (level - 0.33) / 0.33)))
                w2_col = QColor(color.red(), color.green(), color.blue(), w2_alpha)
                painter.setPen(QPen(w2_col, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                wave2 = QPainterPath()
                wave2.arcMoveTo(QRectF(cx + 3.2, cy - 5.2, 5.2, 10.4), -50)
                wave2.arcTo(QRectF(cx + 3.2, cy - 5.2, 5.2, 10.4), -50, 100)
                painter.drawPath(wave2)

            if level > 0.66:
                w3_alpha = min(255, int(255 * min(1.0, (level - 0.66) / 0.34)))
                w3_col = QColor(color.red(), color.green(), color.blue(), w3_alpha)
                painter.setPen(QPen(w3_col, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                wave3 = QPainterPath()
                wave3.arcMoveTo(QRectF(cx + 5.2, cy - 7.2, 6.8, 14.4), -55)
                wave3.arcTo(QRectF(cx + 5.2, cy - 7.2, 6.8, 14.4), -55, 110)
                painter.drawPath(wave3)

        painter.restore()

    @staticmethod
    def _draw_vector_prev(painter, cx: float, cy: float, col: QColor):
        """Draw clean, antialiased vector previous button (bar + left triangle)."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))
        painter.drawRoundedRect(QRectF(cx - 5.5, cy - 4.5, 1.8, 9.0), 0.6, 0.6)
        tri = QPainterPath()
        tri.moveTo(cx + 5.0, cy - 4.5)
        tri.lineTo(cx - 3.2, cy)
        tri.lineTo(cx + 5.0, cy + 4.5)
        tri.closeSubpath()
        painter.drawPath(tri)
        painter.restore()

    @staticmethod
    def _draw_vector_next(painter, cx: float, cy: float, col: QColor):
        """Draw clean, antialiased vector next button (right triangle + bar)."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))
        tri = QPainterPath()
        tri.moveTo(cx - 5.0, cy - 4.5)
        tri.lineTo(cx + 3.2, cy)
        tri.lineTo(cx - 5.0, cy + 4.5)
        tri.closeSubpath()
        painter.drawPath(tri)
        painter.drawRoundedRect(QRectF(cx + 3.7, cy - 4.5, 1.8, 9.0), 0.6, 0.6)
        painter.restore()

    @staticmethod
    def _draw_vector_play_pause(painter, cx: float, cy: float, is_playing: bool, col: QColor):
        """Draw optically balanced play triangle or symmetrical pause bars."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))
        if is_playing:
            p1 = QRectF(cx - 3.8, cy - 5.0, 2.6, 10.0)
            p2 = QRectF(cx + 1.2, cy - 5.0, 2.6, 10.0)
            painter.drawRoundedRect(p1, 0.8, 0.8)
            painter.drawRoundedRect(p2, 0.8, 0.8)
        else:
            tri = QPainterPath()
            tri.moveTo(cx - 3.2, cy - 5.5)
            tri.lineTo(cx + 6.4, cy)
            tri.lineTo(cx - 3.2, cy + 5.5)
            tri.closeSubpath()
            painter.drawPath(tri)
        painter.restore()

    @staticmethod
    def _draw_vector_lyrics_note(painter, cx: float, cy: float, col: QColor):
        """Draw mathematically and optically centered double eighth note vector."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(col))

        # Left note head
        painter.save()
        painter.translate(cx - 3.4, cy + 3.7)
        painter.rotate(-22.0)
        painter.drawEllipse(QRectF(-2.2, -1.6, 4.4, 3.2))
        painter.restore()

        # Right note head
        painter.save()
        painter.translate(cx + 2.8, cy + 2.3)
        painter.rotate(-22.0)
        painter.drawEllipse(QRectF(-2.2, -1.6, 4.4, 3.2))
        painter.restore()

        # Left stem
        painter.drawRoundedRect(QRectF(cx - 2.1, cy - 4.0, 1.4, 7.8), 0.5, 0.5)

        # Right stem
        painter.drawRoundedRect(QRectF(cx + 4.1, cy - 5.3, 1.4, 7.8), 0.5, 0.5)

        # Connecting beam
        beam = QPainterPath()
        beam.moveTo(cx - 2.1, cy - 2.0)
        beam.lineTo(cx + 5.5, cy - 3.3)
        beam.lineTo(cx + 5.5, cy - 5.3)
        beam.lineTo(cx - 2.1, cy - 4.0)
        beam.closeSubpath()
        painter.drawPath(beam)

        painter.restore()

    def _draw_volume_icon(painter, rect: QRectF, increase: bool, color: QColor):
        """Draw SF Symbol speaker with crisp hairline plus/minus indicator."""
        cx, cy = rect.center().x(), rect.center().y()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        spk = QPainterPath()
        spk.addRoundedRect(QRectF(cx - 7.2, cy - 2.4, 3.0, 4.8), 0.8, 0.8)

        horn = QPainterPath()
        horn.moveTo(cx - 4.4, cy - 2.4)
        horn.lineTo(cx - 1.2, cy - 5.4)
        horn.lineTo(cx - 1.2, cy + 5.4)
        horn.lineTo(cx - 4.4, cy + 2.4)
        horn.closeSubpath()

        speaker_combined = spk.united(horn).simplified()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(speaker_combined)

        sym_x = cx + 4.5
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(sym_x - 2.2, cy), QPointF(sym_x + 2.2, cy))
        if increase:
            painter.drawLine(QPointF(sym_x, cy - 2.2), QPointF(sym_x, cy + 2.2))
        painter.restore()

    @staticmethod
    def _draw_play_pause_icon(painter, rect: QRectF, playing: bool, color: QColor):
        """Draw signature Apple hero action play/pause glyph with optical centering."""
        cx, cy = rect.center().x(), rect.center().y()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))

        if playing:
            pw, ph = 3.2, 11.4
            painter.drawRoundedRect(QRectF(cx - 4.3, cy - ph / 2.0, pw, ph), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(cx + 1.1, cy - ph / 2.0, pw, ph), 1.2, 1.2)
        else:
            play = QPainterPath()
            bx = cx - 3.2
            tip_x = cx + 5.8
            play.moveTo(bx, cy - 5.8)
            play.lineTo(tip_x, cy)
            play.lineTo(bx, cy + 5.8)
            play.closeSubpath()
            painter.setPen(QPen(color, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(play)
        painter.restore()

    @staticmethod
    def _draw_track_skip_icon(painter, rect: QRectF, forward: bool, color: QColor):
        """Draw SF Symbol track skip glyph with soft rounded corners."""
        cx, cy = rect.center().x(), rect.center().y()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(color))

        bar_w = 1.8
        h_half = 5.5
        triangle = QPainterPath()

        if forward:
            triangle.moveTo(cx - 5.0, cy - h_half)
            triangle.lineTo(cx + 1.0, cy)
            triangle.lineTo(cx - 5.0, cy + h_half)
            triangle.closeSubpath()
            painter.drawPath(triangle)
            painter.drawRoundedRect(QRectF(cx + 3.0, cy - h_half, bar_w, h_half * 2.0), 0.8, 0.8)
        else:
            painter.drawRoundedRect(QRectF(cx - 4.8, cy - h_half, bar_w, h_half * 2.0), 0.8, 0.8)
            triangle.moveTo(cx + 5.0, cy - h_half)
            triangle.lineTo(cx - 1.0, cy)
            triangle.lineTo(cx + 5.0, cy + h_half)
            triangle.closeSubpath()
            painter.drawPath(triangle)
        painter.restore()

    @staticmethod
    def _draw_vector_power(painter: QPainter, cx: float, cy: float, is_charging: bool, is_ac: bool, pct: int):
        """Draw clean Apple-style battery capsule with terminal cap and charge indicator."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if is_ac:
            bolt = QPainterPath()
            bolt.moveTo(cx + 0.5, cy - 5.5)
            bolt.lineTo(cx - 2.5, cy - 0.2)
            bolt.lineTo(cx, cy - 0.2)
            bolt.lineTo(cx - 0.5, cy + 5.5)
            bolt.lineTo(cx + 2.5, cy + 0.2)
            bolt.lineTo(cx, cy + 0.2)
            bolt.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#38BDF8")))
            painter.drawPath(bolt)
        else:
            bw, bh = 12.0, 7.5
            rect = QRectF(cx - bw / 2.0, cy - bh / 2.0, bw, bh)
            painter.setPen(QPen(QColor(255, 255, 255, 75), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
            painter.drawRoundedRect(rect, 2.2, 2.2)

            # Terminal nipple
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 75)))
            painter.drawRoundedRect(QRectF(rect.right() + 0.5, cy - 1.5, 1.0, 3.0), 0.5, 0.5)

            col = QColor("#38BDF8") if is_charging else (
                QColor("#34D399") if pct > 30 else (QColor("#FBBF24") if pct > 15 else QColor("#F87171"))
            )
            fill_pct = max(0.12, min(1.0, pct / 100.0))
            painter.setBrush(QBrush(col))
            painter.drawRoundedRect(QRectF(rect.left() + 1.2, cy - bh / 2.0 + 1.2, (bw - 2.4) * fill_pct, bh - 2.4), 1.2, 1.2)
        painter.restore()

    @staticmethod
    def _draw_vector_cpu(painter: QPainter, cx: float, cy: float, color: QColor):
        """Draw a clean, pixel-perfect CPU processor microchip vector icon."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chip_rect = QRectF(cx - 4.5, cy - 4.5, 9.0, 9.0)
        painter.setPen(QPen(color, 1.0))
        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 35)))
        painter.drawRoundedRect(chip_rect, 1.5, 1.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRect(QRectF(cx - 1.2, cy - 1.2, 2.4, 2.4))
        painter.setPen(QPen(color, 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for off in (-2.2, 2.2):
            painter.drawLine(QPointF(cx + off, cy - 4.5), QPointF(cx + off, cy - 6.2))
            painter.drawLine(QPointF(cx + off, cy + 4.5), QPointF(cx + off, cy + 6.2))
            painter.drawLine(QPointF(cx - 4.5, cy + off), QPointF(cx - 6.2, cy + off))
            painter.drawLine(QPointF(cx + 4.5, cy + off), QPointF(cx + 6.2, cy + off))
        painter.restore()

    @staticmethod
    def _draw_vector_ram(painter: QPainter, cx: float, cy: float, color: QColor):
        """Draw a clean, pixel-perfect RAM DIMM memory stick vector icon."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ram_w, ram_h = 11.0, 7.0
        ram_rect = QRectF(cx - ram_w / 2.0, cy - ram_h / 2.0, ram_w, ram_h)
        path = QPainterPath()
        l, r, t, b = ram_rect.left(), ram_rect.right(), ram_rect.top(), ram_rect.bottom()
        path.moveTo(l, t + 1.0)
        path.quadTo(l, t, l + 1.0, t)
        path.lineTo(r - 1.0, t)
        path.quadTo(r, t, r, t + 1.0)
        path.lineTo(r, b - 1.0)
        path.quadTo(r, b, r - 1.0, b)
        nx = l + 4.2
        path.lineTo(nx + 1.6, b)
        path.lineTo(nx + 1.6, b - 1.6)
        path.lineTo(nx, b - 1.6)
        path.lineTo(nx, b)
        path.lineTo(l + 1.0, b)
        path.quadTo(l, b, l, b - 1.0)
        path.closeSubpath()
        painter.setPen(QPen(color, 1.0))
        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 35)))
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        for chip_x in (cx - 3.4, cx - 0.5, cx + 2.4):
            painter.drawRect(QRectF(chip_x, cy - 2.0, 1.5, 3.0))
        painter.restore()

    @staticmethod
    def _draw_vector_pencil(painter: QPainter, cx: float, cy: float, color: QColor):
        """Draw an authentic Apple SF Symbol style tilted pencil edit icon."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(cx, cy)
        painter.rotate(-45.0)

        p_pen = QPen(color, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(p_pen)
        painter.setBrush(QBrush(color))

        # Pencil tip triangle
        tip = QPolygonF([
            QPointF(-4.8, 0.0),
            QPointF(-2.2, -1.8),
            QPointF(-2.2, 1.8),
        ])
        painter.drawPolygon(tip)

        # Pencil body
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(-2.0, -1.8, 5.6, 3.6), 0.6, 0.6)

        # Eraser cap
        painter.drawLine(QPointF(4.2, -1.8), QPointF(4.2, 1.8))
        painter.restore()

    @staticmethod
    def _draw_settings_gear_icon(painter: QPainter, cx: float, cy: float, color: QColor, angle_deg: float = 0.0):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for spoke in range(8):
            ang = math.radians(spoke * 45.0 + angle_deg)
            painter.drawLine(
                QPointF(cx + math.cos(ang) * 3.2, cy + math.sin(ang) * 3.2),
                QPointF(cx + math.cos(ang) * 5.4, cy + math.sin(ang) * 5.4),
            )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 1.2, 1.2)
        painter.restore()

    def _calculate_base_media_width(self) -> float:
        """Calculate the snug, content-hugging base width for the media player."""
        fixed_overhead = 206.0  # margin(16) + art(46) + gap(10) + vis_gap(12) + trans/vis(106) + margin(16)
        if self.has_media:

            title_font = _font("Segoe UI", 11.0, QFont.Weight.Bold)
            sub_font = _font("Segoe UI", 8.8, QFont.Weight.Medium)
            title_w = QFontMetricsF(title_font).horizontalAdvance(self.track_title or "")

            has_distinct_album = (
                bool(self.track_album)
                and self.track_album.strip()
                and self.track_album.strip().lower() not in (
                    (self.track_title or "").strip().lower(),
                    (self.track_artist or "").strip().lower(),
                    "unknown album",
                    "single",
                )
            )
            if self.track_artist and has_distinct_album:
                subtitle = f"{self.track_artist} · {self.track_album}"
            elif self.track_artist:
                subtitle = self.track_artist
            elif has_distinct_album:
                subtitle = self.track_album
            else:
                subtitle = ""
            sub_w = QFontMetricsF(sub_font).horizontalAdvance(subtitle) if subtitle else 0.0
            content_text_w = max(title_w, sub_w)
            desired_w = fixed_overhead + content_text_w
        else:
            desired_w = 420.0

        screen_w = QApplication.primaryScreen().availableGeometry().width()
        max_w = min(460.0, float(screen_w - 24))
        return max(420.0, min(max_w, desired_w))

    def _calculate_dynamic_lyrics_width(self, now: float = 0.0) -> float:
        """Return stable lyrics expanded width for jitter-free animation."""
        return getattr(self, "lyrics_expanded_w", 640.0)

    def _update_system_stats(self, now: float):
        if now - self._last_stats_time < 1.8:
            return
        # Never perform CPU/RAM measurements while the island is actively animating
        if abs(self.vel_w) > 1.0 or abs(self.vel_h) > 1.0 or self.expand_progress < 0.95:
            return
        self._last_stats_time = now

        try:
            # 1. Battery (instant kernel call ~0.005ms)
            pstat = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(pstat)):
                self.system_battery_percent = int(pstat.BatteryLifePercent)
                self.system_battery_charging = bool(pstat.BatteryFlag & 8) or bool(pstat.ACLineStatus == 1)

            # 2. RAM (instant kernel call ~0.003ms)
            mstat = MEMORYSTATUSEX()
            mstat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mstat)):
                self.system_ram_percent = float(mstat.dwMemoryLoad)

            # 3. CPU (instant kernel call ~0.002ms)
            idle_ft = FILETIME()
            kernel_ft = FILETIME()
            user_ft = FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle_ft), ctypes.byref(kernel_ft), ctypes.byref(user_ft)):
                i = (idle_ft.dwHighDateTime << 32) | idle_ft.dwLowDateTime
                k = (kernel_ft.dwHighDateTime << 32) | kernel_ft.dwLowDateTime
                u = (user_ft.dwHighDateTime << 32) | user_ft.dwLowDateTime
                if self._prev_kernel_time > 0:
                    d_idle = i - self._prev_idle_time
                    d_total = (k - self._prev_kernel_time) + (u - self._prev_user_time)
                    if d_total > 0:
                        self.system_cpu_percent = max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0))
                self._prev_idle_time, self._prev_kernel_time, self._prev_user_time = i, k, u
        except Exception:
            pass

    @staticmethod
    def _query_network_io():
        """Returns (bytes_sent, bytes_recv) using psutil with seamless fallback to Windows native GetIfTable."""
        if psutil is not None:
            try:
                net = psutil.net_io_counters()
                return net.bytes_sent, net.bytes_recv
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                buf_size = wintypes.DWORD(0)
                ctypes.windll.iphlpapi.GetIfTable(None, ctypes.byref(buf_size), False)
                if buf_size.value > 0:
                    buf = ctypes.create_string_buffer(buf_size.value)
                    if ctypes.windll.iphlpapi.GetIfTable(buf, ctypes.byref(buf_size), False) == 0:
                        num = wintypes.DWORD.from_buffer_copy(buf[:4]).value
                        row_size = ctypes.sizeof(MIB_IFROW)
                        tot_in = 0
                        tot_out = 0
                        for i in range(num):
                            row = MIB_IFROW.from_buffer_copy(buf[4 + i * row_size : 4 + (i + 1) * row_size])
                            if row.dwType != 24:  # Exclude loopback
                                tot_in += row.dwInOctets
                                tot_out += row.dwOutOctets
                        return tot_out, tot_in
            except Exception:
                pass
        return 0, 0

    def _start_network_speed_thread(self):
        """Continuously measures real-time network upload and download throughput in a background thread."""
        def _worker():
            last_sent, last_recv = self._query_network_io()
            last_time = time.perf_counter()

            while not getattr(self, "_stop_background_threads", False):
                try:
                    time.sleep(0.5)
                    now = time.perf_counter()
                    dt = max(0.1, now - last_time)
                    last_time = now

                    curr_sent, curr_recv = self._query_network_io()
                    if curr_sent >= last_sent and curr_recv >= last_recv:
                        up_diff = curr_sent - last_sent
                        down_diff = curr_recv - last_recv
                    else:
                        up_diff = max(0, curr_sent)
                        down_diff = max(0, curr_recv)
                    last_sent = curr_sent
                    last_recv = curr_recv

                    instant_up = up_diff / dt
                    instant_down = down_diff / dt

                    # Smooth responsive filter (70% current, 30% previous)
                    self.net_upload_speed = (self.net_upload_speed * 0.3) + (instant_up * 0.7)
                    self.net_download_speed = (self.net_download_speed * 0.3) + (instant_down * 0.7)
                except Exception:
                    time.sleep(0.5)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    @staticmethod
    def _format_network_speed(bytes_per_sec: float) -> str:
        if bytes_per_sec >= 1024 * 1024 * 100:
            return f"{int(round(bytes_per_sec / (1024 * 1024)))} MB/s"
        elif bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif bytes_per_sec >= 100 * 1024:
            return f"{int(round(bytes_per_sec / 1024))} KB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        elif bytes_per_sec >= 60:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return "0 KB/s"

    def _paint_top_status_bar(self, painter: QPainter, media_x: float, media_w: float, margin: float, draw_clock: bool = False):
        top_y = 8.0
        pill_h = 19.0
        pill_r = 9.5
        cy_stat = top_y + pill_h / 2.0  # 17.5px

        # 1. Left System Health Pill [ Battery · CPU · RAM ] (Vector Icons only, NO TEXT)
        stats_rect = QRectF(media_x + margin, top_y, 148.0, pill_h)
        painter.setBrush(QBrush(QColor(255, 255, 255, 11)))
        painter.setPen(QPen(QColor(255, 255, 255, 16), 0.8))
        painter.drawRoundedRect(stats_rect, pill_r, pill_r)

        cur_stat_x = stats_rect.left() + 7.0
        is_ac = self.system_battery_percent > 100
        is_charging = self.system_battery_charging
        pwr_text = "AC" if is_ac else f"{self.system_battery_percent}%"
        cpu_val = int(round(self.system_cpu_percent))
        cpu_text = f"{cpu_val}%"
        ram_val = int(round(self.system_ram_percent))
        ram_text = f"{ram_val}%"

        # Battery / AC
        self._draw_vector_power(painter, cur_stat_x + 5.0, cy_stat, is_charging, is_ac, self.system_battery_percent)
        cur_stat_x += 13.0
        painter.setFont(_font("Segoe UI", 7.6, QFont.Weight.DemiBold))
        painter.setPen(QColor("#38BDF8") if (is_ac or is_charging) else (
            QColor("#34D399") if self.system_battery_percent > 40 else (
                QColor("#FBBF24") if self.system_battery_percent > 20 else QColor("#F87171")
            )
        ))
        painter.drawText(QRectF(cur_stat_x, top_y, 32.0, pill_h), Qt.AlignmentFlag.AlignVCenter, pwr_text)
        cur_stat_x += 28.0

        # Dot
        painter.setPen(QColor(255, 255, 255, 40))
        painter.drawText(QRectF(cur_stat_x, top_y, 6.0, pill_h), Qt.AlignmentFlag.AlignCenter, "·")
        cur_stat_x += 6.0

        # CPU
        self._draw_vector_cpu(painter, cur_stat_x + 5.0, cy_stat, QColor("#818CF8"))
        cur_stat_x += 13.0
        painter.setFont(_font("Segoe UI", 7.6, QFont.Weight.DemiBold))
        painter.setPen(QColor("#F87171") if cpu_val > 80 else QColor("#CBD5E1"))
        painter.drawText(QRectF(cur_stat_x, top_y, 26.0, pill_h), Qt.AlignmentFlag.AlignVCenter, cpu_text)
        cur_stat_x += 24.0

        # Dot
        painter.setPen(QColor(255, 255, 255, 40))
        painter.drawText(QRectF(cur_stat_x, top_y, 6.0, pill_h), Qt.AlignmentFlag.AlignCenter, "·")
        cur_stat_x += 6.0

        # RAM
        self._draw_vector_ram(painter, cur_stat_x + 6.0, cy_stat, QColor("#34D399"))
        cur_stat_x += 14.0
        painter.setFont(_font("Segoe UI", 7.6, QFont.Weight.DemiBold))
        painter.setPen(QColor("#F87171") if ram_val > 85 else QColor("#CBD5E1"))
        painter.drawText(QRectF(cur_stat_x, top_y, 26.0, pill_h), Qt.AlignmentFlag.AlignVCenter, ram_text)

        # 2. Center Living Clock (Locked to canvas_w / 2.0)
        if draw_clock:
            clock_cx = self.canvas_w / 2.0
            clock_rect = QRectF(clock_cx - 32.0, top_y, 64.0, pill_h)
            painter.setBrush(QBrush(QColor(255, 255, 255, 15)))
            painter.setPen(QPen(QColor(255, 255, 255, 24), 0.8))
            painter.drawRoundedRect(clock_rect, pill_r, pill_r)
            painter.setFont(_font("Segoe UI", 8.4, QFont.Weight.DemiBold))
            painter.setPen(QColor("#FFFFFF"))
            clock_text = self.local_clock_text or self._format_local_clock()
            painter.drawText(clock_rect, Qt.AlignmentFlag.AlignCenter, clock_text)

        # 3. Right Wing: Settings Gear + Conditional Pencil + Speed Up/Down
        right_anchor_x = media_x + media_w - margin
        btn_size = 19.0
        btn_gap = 6.0

        # Settings Gear
        self.btn_settings_rect = QRectF(right_anchor_x - btn_size, top_y, btn_size, btn_size)
        settings_t = self.btn_hover_anim.get("settings", 0.0)
        gear_bg = _interpolate_color(QColor(255, 255, 255, 10), QColor(255, 255, 255, 30), settings_t)
        gear_border = _interpolate_color(QColor(255, 255, 255, 16), QColor(255, 255, 255, 50), settings_t)
        painter.setBrush(QBrush(gear_bg))
        painter.setPen(QPen(gear_border, 0.8))
        painter.drawRoundedRect(self.btn_settings_rect, 6.0, 6.0)
        self._draw_settings_gear_icon(
            painter,
            self.btn_settings_rect.center().x(),
            self.btn_settings_rect.center().y(),
            _interpolate_color(QColor("#94A3B8"), QColor("#FFFFFF"), settings_t),
        )

        # Conditional Pencil Edit (ONLY when media is NOT active)
        show_pencil = not self.has_media
        if show_pencil:
            self.btn_profile_rect = QRectF(self.btn_settings_rect.left() - btn_gap - btn_size, top_y, btn_size, btn_size)
            profile_t = self.btn_hover_anim.get("profile_edit", 0.0)
            pencil_bg = _interpolate_color(QColor(255, 255, 255, 10), QColor(255, 255, 255, 30), profile_t)
            pencil_border = _interpolate_color(QColor(255, 255, 255, 16), QColor(255, 255, 255, 50), profile_t)
            painter.setBrush(QBrush(pencil_bg))
            painter.setPen(QPen(pencil_border, 0.8))
            painter.drawRoundedRect(self.btn_profile_rect, 6.0, 6.0)
            self._draw_vector_pencil(
                painter,
                self.btn_profile_rect.center().x(),
                self.btn_profile_rect.center().y(),
                _interpolate_color(QColor("#38BDF8"), QColor("#00F5FF"), profile_t),
            )
            speed_anchor = self.btn_profile_rect.left()
        else:
            self.btn_profile_rect = QRectF()
            speed_anchor = self.btn_settings_rect.left()

        # Network Speed Pill OR Clear All button (on page 2 with files)
        vault_has_files = self.island_page_index == 1 and hasattr(self, "drop_vault") and len(self.drop_vault.items) > 0
        vault_qr_showing = vault_has_files and (
            bool(self.drop_vault.active_qr_item_id and self.drop_vault.get_item_by_id(self.drop_vault.active_qr_item_id))
            or getattr(self, "vault_qr_modal_anim", 0.0) > 0.05
        )
        show_clear_all = vault_has_files and not vault_qr_showing

        if show_clear_all:
            # "Hapus Semua" button replaces speed pill
            clear_w = 92.0
            clear_rect = QRectF(speed_anchor - btn_gap - clear_w, top_y, clear_w, pill_h)
            self.btn_vault_clear_all_rect = clear_rect
            clr_hvd = self.hovered_btn == "vault_clear_all"
            painter.setBrush(QBrush(QColor(239, 68, 68, 35 if clr_hvd else 14)))
            painter.setPen(QPen(QColor(239, 68, 68, 90 if clr_hvd else 45), 0.8))
            painter.drawRoundedRect(clear_rect, 6.0, 6.0)
            painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.DemiBold))
            painter.setPen(QColor("#F87171" if clr_hvd else "#EF4444"))
            painter.drawText(clear_rect, Qt.AlignmentFlag.AlignCenter, "✕ Hapus Semua")
        else:
            self.btn_vault_clear_all_rect = QRectF()
            up_text = self._format_network_speed(self.net_upload_speed)
            down_text = self._format_network_speed(self.net_download_speed)
            speed_w = 114.0
            speed_rect = QRectF(speed_anchor - btn_gap - speed_w, top_y, speed_w, pill_h)
            painter.setBrush(QBrush(QColor(255, 255, 255, 11)))
            painter.setPen(QPen(QColor(255, 255, 255, 16), 0.8))
            painter.drawRoundedRect(speed_rect, pill_r, pill_r)

            painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.Medium))
            # Download (↓)
            painter.setPen(QColor("#38BDF8"))
            painter.drawText(QRectF(speed_rect.left() + 4.0, top_y, 48.0, pill_h), Qt.AlignmentFlag.AlignCenter, f"↓ {down_text}")
            # Dot
            painter.setPen(QColor(255, 255, 255, 40))
            painter.drawText(QRectF(speed_rect.left() + 53.0, top_y, 6.0, pill_h), Qt.AlignmentFlag.AlignCenter, "·")
            # Upload (↑)
            painter.setPen(QColor("#A78BFA"))
            painter.drawText(QRectF(speed_rect.left() + 60.0, top_y, 48.0, pill_h), Qt.AlignmentFlag.AlignCenter, f"↑ {up_text}")

    def _calculate_base_media_width(self) -> float:
        """Calculate the snug, content-hugging base width for the media player."""
        fixed_overhead = 206.0  # margin(16) + art(46) + gap(10) + vis_gap(12) + trans/vis(106) + margin(16)
        if self.has_media:

            title_font = _font("Segoe UI", 11.0, QFont.Weight.Bold)
            sub_font = _font("Segoe UI", 8.8, QFont.Weight.Medium)
            title_w = QFontMetricsF(title_font).horizontalAdvance(self.track_title or "")

            has_distinct_album = (
                bool(self.track_album)
                and self.track_album.strip()
                and self.track_album.strip().lower() not in (
                    (self.track_title or "").strip().lower(),
                    (self.track_artist or "").strip().lower(),
                    "unknown album",
                    "single",
                )
            )
            if self.track_artist and has_distinct_album:
                subtitle = f"{self.track_artist} · {self.track_album}"
            elif self.track_artist:
                subtitle = self.track_artist
            elif has_distinct_album:
                subtitle = self.track_album
            else:
                subtitle = ""
            sub_w = QFontMetricsF(sub_font).horizontalAdvance(subtitle) if subtitle else 0.0
            content_text_w = max(title_w, sub_w)
            desired_w = fixed_overhead + content_text_w
        else:
            desired_w = 420.0

        screen_w = QApplication.primaryScreen().availableGeometry().width()
        max_w = min(460.0, float(screen_w - 24))
        return max(420.0, min(max_w, desired_w))

    def _update_audio_reactive_spectrum(self, dt: float, now: float):
        num_cols = 17
        max_rows = 11.0

        if not hasattr(self, "audio_meter"):
            return

        # Professional 17-band graphic equalizer profile with natural musical curve
        band_profile = (
            0.88, 0.94, 1.00, 0.96, 0.90,
            0.84, 0.86, 0.90, 0.92, 0.88,
            0.84, 0.80, 0.78, 0.74, 0.70,
            0.66, 0.62
        )

        levels = self.audio_meter.get_levels()
        if not levels or not isinstance(levels, (tuple, list)) or len(levels) < 3:
            master_peak, left_peak, right_peak = 0.0, 0.0, 0.0
        else:
            master_peak, left_peak, right_peak = levels
        has_system_audio = master_peak > 0.0015
        self._system_audio_active = has_system_audio
        is_audio_active = self.is_playing or has_system_audio

        if is_audio_active:
            # 1. Adaptive Rolling AGC: Automatically scales quiet YouTube/Chrome media (e.g. 0.05 peak)
            # as well as loud uncompressed audio to fully explore rows 1 to 11.
            decay_factor = math.exp(-0.35 * dt)
            self._audio_rolling_max = max(0.06, max(self._audio_rolling_max * decay_factor, master_peak))

            # 2. Perceptual Power-Law Expansion (Stevens law / log loudness response)
            norm_master = min(1.0, master_peak / self._audio_rolling_max)
            perc_master = math.pow(norm_master, 0.46)

            norm_left = min(1.0, left_peak / self._audio_rolling_max)
            perc_left = math.pow(norm_left, 0.46)

            norm_right = min(1.0, right_peak / self._audio_rolling_max)
            perc_right = math.pow(norm_right, 0.46)

            # 3. Dynamic Beat & Transient Onset Tracker (Kicks, snares, 808 bass bursts)
            transient = max(0.0, master_peak - self._audio_short_avg)
            self._audio_short_avg += (master_peak - self._audio_short_avg) * (1.0 - math.exp(-14.0 * dt))

            beat_impulse = min(1.0, transient * 4.5)
            self._audio_beat_punch = max(beat_impulse, self._audio_beat_punch * math.exp(-18.0 * dt))

            for i in range(num_cols):
                # Channel assignment: Left side (0..8) responds to Left, Right side (9..16) to Right
                ch_energy = perc_left if i < 9 else perc_right

                # Rhythmic harmonic shimmer gives organic life to adjacent frequency bands
                w1 = math.sin(self.wave_phase * 1.6 + i * 0.85)
                w2 = math.cos(self.wave_phase * 2.4 - i * 1.15)
                shimmer = (w1 * 0.5 + w2 * 0.4 + 1.0) / 2.0

                if i < 5:
                    # Bass Kick Zone: Heavy visceral response to drum transients & sub-bass energy
                    col_energy = (ch_energy * 0.60 + self._audio_beat_punch * 0.55 + transient * 1.8) * (0.80 + 0.35 * shimmer)
                elif i < 11:
                    # Midrange Melody Zone: Vocal presence, guitars, synth chords
                    col_energy = (ch_energy * 0.70 + perc_master * 0.25 + self._audio_beat_punch * 0.25) * (0.82 + 0.30 * shimmer)
                else:
                    # High Treble Zone: Crisp snare snap, hi-hats, percussive transients
                    col_energy = (ch_energy * 0.65 + perc_master * 0.20 + transient * 1.2) * (0.75 + 0.40 * shimmer)

                target_rows = max(0.0, min(max_rows, col_energy * band_profile[i] * max_rows))

                # Snappy attack on beats, smooth natural decay
                if target_rows > self.eq_col_heights[i]:
                    self.eq_col_heights[i] = target_rows
                else:
                    self.eq_col_heights[i] = max(0.0, self.eq_col_heights[i] - 18.0 * dt)

                # Floating peak hold dot physics
                if self.eq_col_heights[i] >= self.eq_peak_dots[i]:
                    self.eq_peak_dots[i] = self.eq_col_heights[i]
                    self.eq_peak_dot_hold[i] = 0.16
                else:
                    if self.eq_peak_dot_hold[i] > 0.0:
                        self.eq_peak_dot_hold[i] -= dt
                    else:
                        self.eq_peak_dots[i] = max(0.0, self.eq_peak_dots[i] - 11.0 * dt)
        elif self.is_playing:
            # Fallback when playing but master_peak is zero (e.g. digital bypass/exclusive audio driver)
            # Generates a lively beat-pulsing spectrum that bounces with musical rhythm
            beat_pulse = (math.sin(self.wave_phase * 1.8) + 1.0) * 0.5
            for i in range(num_cols):
                w1 = math.sin(self.wave_phase * 1.3 + i * 0.75)
                w2 = math.cos(self.wave_phase * 2.1 - i * 0.95)
                sim = (w1 * 0.5 + w2 * 0.3 + 0.8) / 1.6
                sim_energy = (sim * 0.65 + beat_pulse * 0.35)
                target_rows = sim_energy * band_profile[i] * max_rows
                if target_rows > self.eq_col_heights[i]:
                    self.eq_col_heights[i] = target_rows
                else:
                    self.eq_col_heights[i] = max(0.0, self.eq_col_heights[i] - 15.0 * dt)
                if self.eq_col_heights[i] >= self.eq_peak_dots[i]:
                    self.eq_peak_dots[i] = self.eq_col_heights[i]
                    self.eq_peak_dot_hold[i] = 0.16
                else:
                    if self.eq_peak_dot_hold[i] > 0.0:
                        self.eq_peak_dot_hold[i] -= dt
                    else:
                        self.eq_peak_dots[i] = max(0.0, self.eq_peak_dots[i] - 10.0 * dt)
        else:
            # Paused / silence: smoothly fall down to zero (transparent)
            self._audio_beat_punch = 0.0
            self._audio_short_avg = 0.0
            for i in range(num_cols):
                self.eq_col_heights[i] = max(0.0, self.eq_col_heights[i] - 20.0 * dt)
                self.eq_peak_dots[i] = max(0.0, self.eq_peak_dots[i] - 15.0 * dt)
                self.eq_peak_dot_hold[i] = 0.0

    @staticmethod
    def _get_spectrum_gradient(bar_rect: QRectF, u: float) -> QLinearGradient:
        """
        Computes 2D Cyan-to-Magenta spectrum gradient for audio visualizer bars.
        Matches Apple/Spotify vibrant aesthetic from user reference:
        Horizontal spectrum: Electric Cyan (#34E1F1) -> Violet/Indigo -> Magenta/Pink (#E879F9).
        Vertical gradient: Lighter cyan-tinted top -> deeper magenta-tinted bottom.
        """
        grad = QLinearGradient(bar_rect.topLeft(), bar_rect.bottomLeft())
        top_col = _interpolate_color(_SPEC_TOP_C1, _SPEC_TOP_C2, u)
        bot_col = _interpolate_color(_SPEC_BOT_C1, _SPEC_BOT_C2, u)

        grad.setColorAt(0.0, top_col)
        grad.setColorAt(1.0, bot_col)
        return grad

    def _paint_dot_matrix_equalizer(self, painter: QPainter, rect: QRectF):
        """
        Continuous Cyan-to-Magenta pill-bar spectrum equalizer (Apple / Spotify aesthetic).
        Features:
        - 11 continuous vertical pill bars with smooth circular caps
        - Symmetrical height expansion around vertical center (Y = rect.center().y())
        - Seamless 2D gradient transitioning from Electric Cyan -> Violet -> Vibrant Magenta Pink
        - Real-time WASAPI audio beat and frequency band response
        - Soft ambient glow bloom on high-energy peaks
        """
        num_bars = 11
        bar_w = 4.8
        gap = 3.2
        total_w = num_bars * bar_w + (num_bars - 1) * gap  # 84.8px
        start_x = rect.left() + (rect.width() - total_w) / 2.0
        cy = rect.center().y()
        max_h = rect.height() - 2.0
        r = bar_w / 2.0

        is_active_audio = self.is_playing or getattr(self, "_system_audio_active", False)
        sample_indices = (0, 1, 3, 5, 7, 8, 9, 11, 13, 14, 16)
        idle_profile = (5.0, 8.0, 12.0, 17.0, 21.0, 19.0, 21.0, 17.0, 12.0, 8.0, 5.0)
        beat_boost = getattr(self, "_audio_beat_punch", 0.0) * 0.35

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i in range(num_bars):
            u = i / float(num_bars - 1)
            bx = start_x + i * (bar_w + gap)

            if is_active_audio:
                b_idx = sample_indices[i]
                raw_col = self.eq_col_heights[b_idx] if b_idx < len(self.eq_col_heights) else 0.0
                norm_h = min(1.0, max(0.0, raw_col / 11.0))
                # Dynamic beat expansion (center bars respond extra to punch)
                center_factor = 1.0 + (0.35 if 3 <= i <= 7 else 0.0)
                bar_h = max(4.5, min(max_h, (norm_h * 0.75 + beat_boost * center_factor) * max_h))
                bar_rect = QRectF(bx, cy - bar_h / 2.0, bar_w, bar_h)

                grad = self._get_spectrum_gradient(bar_rect, u)
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bar_rect, r, r)

                # Soft bloom glow on active energy
                if bar_h > 18.0:
                    glow_alpha = int(min(45, (bar_h / max_h) * 50))
                    top_c = _interpolate_color(_SPEC_TOP_C1, _SPEC_TOP_C2, u)
                    bot_c = _interpolate_color(_SPEC_BOT_C1, _SPEC_BOT_C2, u)
                    mid_c = _interpolate_color(top_c, bot_c, 0.5)
                    mid_c.setAlpha(glow_alpha)
                    painter.setBrush(QBrush(mid_c))
                    painter.drawRoundedRect(bar_rect.adjusted(-1.2, -1.2, 1.2, 1.2), r + 1.2, r + 1.2)
            else:
                bar_h = idle_profile[i]
                bar_rect = QRectF(bx, cy - bar_h / 2.0, bar_w, bar_h)
                painter.setBrush(QBrush(QColor(148, 163, 184, 85)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bar_rect, r, r)

        painter.restore()

    def _draw_robot_mascot(self, painter: QPainter, center: QPointF, t: float, scale: float = 1.0):
        """
        Renders an ultra-smooth, high-definition Front-Facing Cyberpunk Mecha Skull Android Mascot.
        Faithful to user's second reference image:
        - Symmetrical front-facing Cyberpunk Skull / Mecha Android
        - Mohawk crest of ribbed power conduit cables curving back over the crown with glowing fiber tips
        - Inverted triangular forehead crest with magenta border & glowing electric cyan diode
        - Chiseled titanium brow armor with downward slant
        - Dual Signature Cyber-Optics:
            * Left Eye (viewer's left): Piercing Electric Cyan (#00F5FF) with smooth lens flare
            * Right Eye (viewer's right): Piercing Neon Magenta (#FF007F) with smooth lens flare
        - Skull nasal cavity with central vertical septum divider
        - Symmetrical blocky ear modules with yellow/black hazard warning stripes & horizontal antenna pins
        - Angular rebreather jaw with vertical vents & cyan chin diode
        - Symmetrical curved power conduits looping under the jaw
        - Back neon cyber-shield aura (Cyan left, Magenta right)
        - Ultra-smooth, buttery animation lifecycle:
            * Dual-harmonic floating hover bob + continuous breathing energy pulse
            * Quintic smoothstep gaze tracking (left / center / right) with micro 3D parallax
            * Raised-cosine mechanical shutter blink with continuous velocity profile
        """
        # -------------------------------------------------------------
        # 1. Ultra-Smooth Animation Lifecycle Calculations
        # -------------------------------------------------------------
        # Dual-harmonic organic hover bobbing (completely continuous and silky)
        bob_y = math.sin(t * 2.2) * 0.38 + math.sin(t * 4.4) * 0.08
        cx = center.x()
        cy = center.y() + bob_y

        # Smooth Gaze Cycle (7.2s total cycle, buttery smooth transitions)
        # 0.0 - 2.2s: Center (forward gaze)
        # 2.2 - 2.9s: Smooth glide to Left
        # 2.9 - 4.3s: Stare Left
        # 4.3 - 5.1s: Smooth glide to Right
        # 5.1 - 6.5s: Stare Right
        # 6.5 - 7.2s: Smooth glide to Center
        phase = t % 7.2
        if phase < 2.2:
            gaze_x = 0.0
        elif phase < 2.9:
            # Quintic smoothstep: 6p^5 - 15p^4 + 10p^3 (zero jerk, C2 continuous)
            p = (phase - 2.2) / 0.7
            s = p * p * p * (p * (p * 6.0 - 15.0) + 10.0)
            gaze_x = -1.0 * s
        elif phase < 4.3:
            gaze_x = -1.0
        elif phase < 5.1:
            p = (phase - 4.3) / 0.8
            s = p * p * p * (p * (p * 6.0 - 15.0) + 10.0)
            gaze_x = -1.0 + 2.0 * s
        elif phase < 6.5:
            gaze_x = 1.0
        else:
            p = (phase - 6.5) / 0.7
            s = p * p * p * (p * (p * 6.0 - 15.0) + 10.0)
            gaze_x = 1.0 * (1.0 - s)

        # Smooth Mechanical Blink (~4.0s cycle, 0.20s silky raised-cosine profile)
        blink_phase = t % 4.0
        if blink_phase < 0.20:
            # Raised cosine wave for infinitely smooth acceleration and deceleration
            b = 0.5 * (1.0 - math.cos((blink_phase / 0.20) * 2.0 * math.pi))
            eye_open = max(0.04, 1.0 - b * 0.96)
        else:
            eye_open = 1.0

        # Organic idle breathing / energy pulse (modulates neon glow)
        energy_pulse = 0.88 + 0.12 * math.cos(t * 2.6)

        # Subtle 3D parallax micro-shift on internal facial features
        parallax_x = gaze_x * 0.35

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if scale != 1.0:
            painter.translate(center.x(), center.y())
            painter.scale(scale, scale)
            cx = 0.0
            cy = bob_y

        # -------------------------------------------------------------
        # 2. Back Neon Cyber-Shield Aura (Cyan Left, Magenta Right)
        # -------------------------------------------------------------
        shield_l = QPainterPath()
        shield_l.moveTo(cx, cy - 9.4)
        shield_l.lineTo(cx - 7.2, cy - 7.2)
        shield_l.lineTo(cx - 8.5, cy + 0.2)
        shield_l.lineTo(cx - 5.5, cy + 6.8)
        shield_l.lineTo(cx, cy + 9.6)

        shield_r = QPainterPath()
        shield_r.moveTo(cx, cy - 9.4)
        shield_r.lineTo(cx + 7.2, cy - 7.2)
        shield_r.lineTo(cx + 8.5, cy + 0.2)
        shield_r.lineTo(cx + 5.5, cy + 6.8)
        shield_r.lineTo(cx, cy + 9.6)

        # Ambient Outer Glow
        glow_alpha = int(45 * energy_pulse)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 245, 255, glow_alpha), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(shield_l)
        painter.setPen(QPen(QColor(255, 0, 127, glow_alpha), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(shield_r)

        # Sharp Neon Outline
        painter.setPen(QPen(QColor(0, 245, 255, int(155 * energy_pulse)), 0.85, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(shield_l)
        painter.setPen(QPen(QColor(255, 0, 127, int(155 * energy_pulse)), 0.85, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(shield_r)

        # -------------------------------------------------------------
        # 3. Outer Power Cables Looping Around Cheeks & Jaw
        # -------------------------------------------------------------
        cables_left = [
            (QPointF(cx - 2.2, cy + 6.6), QPointF(cx - 6.8, cy + 7.0), QPointF(cx - 7.6, cy + 2.8), QPointF(cx - 6.0, cy + 1.2), _ROBOT_CYAN, 1.2),
            (QPointF(cx - 1.5, cy + 7.2), QPointF(cx - 8.2, cy + 8.0), QPointF(cx - 9.0, cy + 2.0), QPointF(cx - 6.4, cy - 0.4), _ROBOT_LIGHT_CYAN, 0.9),
        ]
        cables_right = [
            (QPointF(cx + 2.2, cy + 6.6), QPointF(cx + 6.8, cy + 7.0), QPointF(cx + 7.6, cy + 2.8), QPointF(cx + 6.0, cy + 1.2), _ROBOT_MAGENTA, 1.2),
            (QPointF(cx + 1.5, cy + 7.2), QPointF(cx + 8.2, cy + 8.0), QPointF(cx + 9.0, cy + 2.0), QPointF(cx + 6.4, cy - 0.4), _ROBOT_LIGHT_MAGENTA, 0.9),
        ]

        for start_pt, c1, c2, end_pt, col, w in cables_left + cables_right:
            p = QPainterPath()
            p.moveTo(start_pt)
            p.cubicTo(c1, c2, end_pt)
            painter.setPen(QPen(_ROBOT_DARK_BG, w + 0.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)
            painter.setPen(QPen(_ROBOT_SLATE, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)
            # Glowing fiber line
            c_glow = QColor(col.red(), col.green(), col.blue(), int(195 * energy_pulse))
            painter.setPen(QPen(c_glow, 0.55, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)

        # -------------------------------------------------------------
        # 4. Cranial Power Conduit Dreadlocks (Overhead Mohawk Crest)
        # -------------------------------------------------------------
        crest_cables = [
            (QPointF(cx - 0.7, cy - 4.8), QPointF(cx - 1.0, cy - 8.6), QPointF(cx - 1.3, cy - 9.6), QPointF(cx - 1.5, cy - 10.0), _ROBOT_CYAN),
            (QPointF(cx + 0.7, cy - 4.8), QPointF(cx + 1.0, cy - 8.6), QPointF(cx + 1.3, cy - 9.6), QPointF(cx + 1.5, cy - 10.0), _ROBOT_MAGENTA),
            (QPointF(cx - 1.8, cy - 4.4), QPointF(cx - 2.8, cy - 7.8), QPointF(cx - 3.4, cy - 9.0), QPointF(cx - 3.8, cy - 9.4), _ROBOT_LIGHT_CYAN),
            (QPointF(cx + 1.8, cy - 4.4), QPointF(cx + 2.8, cy - 7.8), QPointF(cx + 3.4, cy - 9.0), QPointF(cx + 3.8, cy - 9.4), _ROBOT_LIGHT_MAGENTA),
            (QPointF(cx - 3.0, cy - 3.6), QPointF(cx - 4.6, cy - 6.6), QPointF(cx - 5.6, cy - 7.4), QPointF(cx - 6.2, cy - 7.6), _ROBOT_CYAN),
            (QPointF(cx + 3.0, cy - 3.6), QPointF(cx + 4.6, cy - 6.6), QPointF(cx + 5.6, cy - 7.4), QPointF(cx + 6.2, cy - 7.6), _ROBOT_MAGENTA),
        ]

        for start_pt, c1, c2, end_pt, glow_col in crest_cables:
            p = QPainterPath()
            p.moveTo(start_pt)
            p.cubicTo(c1, c2, end_pt)
            painter.setPen(QPen(_ROBOT_DARK_BG, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)
            painter.setPen(QPen(_ROBOT_SLATE, 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)
            # Conduit rib pulse
            painter.setPen(QPen(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), int(210 * energy_pulse)), 0.6, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(p)
            # Fiber node tip
            painter.setBrush(QBrush(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), int(230 * energy_pulse))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(end_pt, 0.45, 0.45)

        # -------------------------------------------------------------
        # 5. Titanium Skull Main Chassis (Tapered chiseled skull)
        # -------------------------------------------------------------
        skull_poly = QPolygonF([
            QPointF(cx - 3.6, cy - 4.5),  # Top cranium left
            QPointF(cx + 3.6, cy - 4.5),  # Top cranium right
            QPointF(cx + 5.4, cy - 2.8),  # Upper temple right
            QPointF(cx + 5.8, cy + 0.4),  # Ear junction right
            QPointF(cx + 4.8, cy + 3.6),  # Cheekbone right
            QPointF(cx + 3.2, cy + 6.0),  # Jaw right
            QPointF(cx + 1.6, cy + 7.6),  # Chin right
            QPointF(cx - 1.6, cy + 7.6),  # Chin left
            QPointF(cx - 3.2, cy + 6.0),  # Jaw left
            QPointF(cx - 4.8, cy + 3.6),  # Cheekbone left
            QPointF(cx - 5.8, cy + 0.4),  # Ear junction left
            QPointF(cx - 5.4, cy - 2.8),  # Upper temple left
        ])

        skull_path = QPainterPath()
        skull_path.addPolygon(skull_poly)
        skull_path.closeSubpath()

        # Deep titanium gunmetal gradient
        skull_grad = QLinearGradient(cx, cy - 5.0, cx, cy + 8.0)
        skull_grad.setColorAt(0.0, QColor("#334155"))
        skull_grad.setColorAt(0.35, QColor("#1E293B"))
        skull_grad.setColorAt(0.75, QColor("#0F172A"))
        skull_grad.setColorAt(1.0, QColor("#020617"))

        pen_skull = QPen(QColor(255, 255, 255, 50), 0.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
        painter.setBrush(QBrush(skull_grad))
        painter.setPen(pen_skull)
        painter.drawPath(skull_path)

        # -------------------------------------------------------------
        # 6. Symmetrical Ear Modules with Hazard Stripes & Antenna Pins
        # -------------------------------------------------------------
        for side in (-1, 1):
            ear_x = cx + side * 6.3
            ear_y = cy - 0.2

            # Outer rectangular ear block
            ear_rect = QRectF(ear_x - 1.0, ear_y - 2.2, 2.0, 4.4)
            painter.setBrush(QBrush(QColor("#0F172A")))
            painter.setPen(QPen(QColor(255, 255, 255, 45), 0.5))
            painter.drawRoundedRect(ear_rect, 0.6, 0.6)

            # Hazard warning stripes on the lower ear block
            h_rect = QRectF(ear_x - 0.8, ear_y + 0.4, 1.6, 1.5)
            painter.setBrush(QBrush(QColor("#0B0F19")))
            painter.setPen(QPen(QColor("#EAB308"), 0.4))
            painter.drawRect(h_rect)
            painter.setPen(QPen(QColor("#FACC15"), 0.55))
            painter.drawLine(QPointF(ear_x - 0.6, ear_y + 0.6), QPointF(ear_x + 0.2, ear_y + 1.6))

            # Horizontal antenna pin extending outward
            pin_start_x = ear_x + (side * 1.0)
            pin_end_x = ear_x + (side * 2.8)
            painter.setPen(QPen(QColor("#060A12"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(pin_start_x, ear_y), QPointF(pin_end_x, ear_y))
            painter.setPen(QPen(QColor("#64748B"), 0.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(pin_start_x, ear_y), QPointF(pin_end_x, ear_y))

            # Glowing antenna tip
            tip_c = QColor("#00F5FF") if side == -1 else QColor("#FF007F")
            painter.setBrush(QBrush(QColor(tip_c.red(), tip_c.green(), tip_c.blue(), int(230 * energy_pulse))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(pin_end_x, ear_y), 0.5, 0.5)

        # -------------------------------------------------------------
        # 7. Forehead Shield Crest with Magenta Border & Cyan Core
        # -------------------------------------------------------------
        crest_poly = QPolygonF([
            QPointF(cx - 2.5 + parallax_x, cy - 4.6),
            QPointF(cx + 2.5 + parallax_x, cy - 4.6),
            QPointF(cx + 1.8 + parallax_x, cy - 2.4),
            QPointF(cx + parallax_x, cy - 1.8),
            QPointF(cx - 1.8 + parallax_x, cy - 2.4),
        ])
        painter.setBrush(QBrush(QColor("#0B0F19")))
        painter.setPen(QPen(QColor(56, 189, 248, 140), 0.5))
        painter.drawPolygon(crest_poly)

        # Outer Magenta Inverted Triangle Shield
        tri_outer = QPolygonF([
            QPointF(cx - 1.4 + parallax_x, cy - 4.0),
            QPointF(cx + 1.4 + parallax_x, cy - 4.0),
            QPointF(cx + parallax_x, cy - 2.3),
        ])
        painter.setBrush(QBrush(QColor("#0B0F19")))
        painter.setPen(QPen(QColor("#FF007F"), 0.5))
        painter.drawPolygon(tri_outer)

        # Inner Glowing Electric Cyan Core
        tri_core = QPolygonF([
            QPointF(cx - 0.9 + parallax_x, cy - 3.8),
            QPointF(cx + 0.9 + parallax_x, cy - 3.8),
            QPointF(cx + parallax_x, cy - 2.6),
        ])
        painter.setBrush(QBrush(QColor("#00F5FF")))
        painter.setPen(QPen(QColor("#FFFFFF"), 0.35))
        painter.drawPolygon(tri_core)

        # -------------------------------------------------------------
        # 8. Aggressive Brow Armor Plates
        # -------------------------------------------------------------
        brow_l = QPolygonF([
            QPointF(cx - 5.2 + parallax_x, cy - 2.2),
            QPointF(cx - 1.0 + parallax_x, cy - 1.5),
            QPointF(cx - 0.8 + parallax_x, cy - 0.9),
            QPointF(cx - 4.6 + parallax_x, cy - 1.2),
        ])
        brow_r = QPolygonF([
            QPointF(cx + 5.2 + parallax_x, cy - 2.2),
            QPointF(cx + 1.0 + parallax_x, cy - 1.5),
            QPointF(cx + 0.8 + parallax_x, cy - 0.9),
            QPointF(cx + 4.6 + parallax_x, cy - 1.2),
        ])
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.setPen(QPen(QColor(255, 255, 255, 60), 0.45))
        painter.drawPolygon(brow_l)
        painter.drawPolygon(brow_r)

        # -------------------------------------------------------------
        # 9. Dual Cyber-Optics: Ocular Sockets, Gaze & Blinking
        # -------------------------------------------------------------
        shutter_h = max(0.12, 1.25 * eye_open)
        shutter_glow_h = max(0.35, 2.2 * eye_open)
        eye_shift_x = gaze_x * 0.80

        # --- LEFT EYE: Electric Cyan (#00F5FF) ---
        left_sock_x = cx - 2.8 + parallax_x
        left_sock_y = cy - 0.3
        left_eye_center = QPointF(left_sock_x + eye_shift_x, left_sock_y)

        # Left Dark Ocular Socket
        sock_l = QPolygonF([
            QPointF(left_sock_x - 1.9, left_sock_y - 0.9),
            QPointF(left_sock_x + 1.7, left_sock_y - 0.7),
            QPointF(left_sock_x + 1.5, left_sock_y + 0.9),
            QPointF(left_sock_x - 1.7, left_sock_y + 0.8),
        ])
        painter.setBrush(QBrush(QColor("#02050E")))
        painter.setPen(QPen(QColor(0, 245, 255, 60), 0.35))
        painter.drawPolygon(sock_l)

        # Left Eye Horizontal Anamorphic Lens Flare
        flare_l_len = 3.8 + (2.0 if gaze_x < -0.2 else 0.0)
        flare_l_alpha = int(210 * eye_open * energy_pulse)
        if flare_l_alpha > 0:
            grad_l = QLinearGradient(
                left_eye_center.x() + 0.8, left_eye_center.y(),
                left_eye_center.x() - flare_l_len, left_eye_center.y()
            )
            grad_l.setColorAt(0.0, QColor(255, 255, 255, flare_l_alpha))
            grad_l.setColorAt(0.25, QColor(0, 245, 255, int(flare_l_alpha * 0.9)))
            grad_l.setColorAt(1.0, QColor(0, 245, 255, 0))
            painter.setPen(QPen(QBrush(grad_l), max(0.35, shutter_h * 0.85), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(left_eye_center, QPointF(left_eye_center.x() - flare_l_len, left_eye_center.y()))

        # Left Eye Ambient Bloom
        bloom_l = QColor(0, 245, 255, int(115 * eye_open * energy_pulse))
        painter.setBrush(QBrush(bloom_l))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(left_eye_center, 1.8, shutter_glow_h)

        # Left Eye Glowing Aperture Core
        slit_l = QPolygonF([
            QPointF(left_eye_center.x() - 1.1, left_eye_center.y() - shutter_h * 0.5),
            QPointF(left_eye_center.x() + 1.0, left_eye_center.y() - shutter_h * 0.4),
            QPointF(left_eye_center.x() + 1.0, left_eye_center.y() + shutter_h * 0.4),
            QPointF(left_eye_center.x() - 1.1, left_eye_center.y() + shutter_h * 0.5),
        ])
        painter.setBrush(QBrush(QColor("#00F5FF")))
        painter.setPen(QPen(QColor("#A5F3FC"), 0.3))
        painter.drawPolygon(slit_l)

        # Left Eye Pure White Hot Core
        if eye_open > 0.25:
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(left_eye_center, 0.55, 0.35 * eye_open)

        # --- RIGHT EYE: Neon Magenta (#FF007F) ---
        right_sock_x = cx + 2.8 + parallax_x
        right_sock_y = cy - 0.3
        right_eye_center = QPointF(right_sock_x + eye_shift_x, right_sock_y)

        # Right Dark Ocular Socket
        sock_r = QPolygonF([
            QPointF(right_sock_x - 1.7, right_sock_y - 0.7),
            QPointF(right_sock_x + 1.9, right_sock_y - 0.9),
            QPointF(right_sock_x + 1.7, right_sock_y + 0.8),
            QPointF(right_sock_x - 1.5, right_sock_y + 0.9),
        ])
        painter.setBrush(QBrush(QColor("#02050E")))
        painter.setPen(QPen(QColor(255, 0, 127, 60), 0.35))
        painter.drawPolygon(sock_r)

        # Right Eye Horizontal Anamorphic Lens Flare
        flare_r_len = 3.8 + (2.0 if gaze_x > 0.2 else 0.0)
        flare_r_alpha = int(210 * eye_open * energy_pulse)
        if flare_r_alpha > 0:
            grad_r = QLinearGradient(
                right_eye_center.x() - 0.8, right_eye_center.y(),
                right_eye_center.x() + flare_r_len, right_eye_center.y()
            )
            grad_r.setColorAt(0.0, QColor(255, 255, 255, flare_r_alpha))
            grad_r.setColorAt(0.25, QColor(255, 0, 127, int(flare_r_alpha * 0.9)))
            grad_r.setColorAt(1.0, QColor(255, 0, 127, 0))
            painter.setPen(QPen(QBrush(grad_r), max(0.35, shutter_h * 0.85), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(right_eye_center, QPointF(right_eye_center.x() + flare_r_len, right_eye_center.y()))

        # Right Eye Ambient Bloom
        bloom_r = QColor(255, 0, 127, int(115 * eye_open * energy_pulse))
        painter.setBrush(QBrush(bloom_r))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(right_eye_center, 1.8, shutter_glow_h)

        # Right Eye Glowing Aperture Core
        slit_r = QPolygonF([
            QPointF(right_eye_center.x() - 1.0, right_eye_center.y() - shutter_h * 0.4),
            QPointF(right_eye_center.x() + 1.1, right_eye_center.y() - shutter_h * 0.5),
            QPointF(right_eye_center.x() + 1.1, right_eye_center.y() + shutter_h * 0.5),
            QPointF(right_eye_center.x() - 1.0, right_eye_center.y() + shutter_h * 0.4),
        ])
        painter.setBrush(QBrush(QColor("#FF007F")))
        painter.setPen(QPen(QColor("#FBCFE8"), 0.3))
        painter.drawPolygon(slit_r)

        # Right Eye Pure White Hot Core
        if eye_open > 0.25:
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(right_eye_center, 0.55, 0.35 * eye_open)

        # -------------------------------------------------------------
        # 10. Skull Nasal Cavity (Center Mecha Skull Feature)
        # -------------------------------------------------------------
        nose_poly = QPolygonF([
            QPointF(cx - 0.7 + parallax_x, cy + 1.2),
            QPointF(cx + 0.7 + parallax_x, cy + 1.2),
            QPointF(cx + 1.1 + parallax_x, cy + 3.0),
            QPointF(cx + parallax_x, cy + 3.4),
            QPointF(cx - 1.1 + parallax_x, cy + 3.0),
        ])
        painter.setBrush(QBrush(QColor("#02050E")))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 0.35))
        painter.drawPolygon(nose_poly)

        # Center vertical nasal septum pin
        painter.setPen(QPen(QColor("#475569"), 0.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(cx + parallax_x, cy + 1.5), QPointF(cx + parallax_x, cy + 3.1))

        # -------------------------------------------------------------
        # 11. Cheeks & Rebreather Chin / Jaw Module
        # -------------------------------------------------------------
        painter.setPen(QPen(QColor(255, 255, 255, 40), 0.45))
        painter.drawLine(QPointF(cx - 4.4 + parallax_x, cy + 1.8), QPointF(cx - 2.3 + parallax_x, cy + 3.4))
        painter.drawLine(QPointF(cx + 4.4 + parallax_x, cy + 1.8), QPointF(cx + 2.3 + parallax_x, cy + 3.4))

        # Rebreather Chin Piece
        chin_poly = QPolygonF([
            QPointF(cx - 2.4 + parallax_x, cy + 4.8),
            QPointF(cx + 2.4 + parallax_x, cy + 4.8),
            QPointF(cx + 1.7 + parallax_x, cy + 7.4),
            QPointF(cx - 1.7 + parallax_x, cy + 7.4),
        ])
        painter.setBrush(QBrush(QColor("#080D16")))
        painter.setPen(QPen(QColor(56, 189, 248, 110), 0.5))
        painter.drawPolygon(chin_poly)

        # Chin Vertical Vent Slots
        painter.setPen(QPen(QColor("#64748B"), 0.5))
        painter.drawLine(QPointF(cx - 1.0 + parallax_x, cy + 5.4), QPointF(cx - 1.0 + parallax_x, cy + 6.8))
        painter.drawLine(QPointF(cx + parallax_x, cy + 5.2), QPointF(cx + parallax_x, cy + 7.0))
        painter.drawLine(QPointF(cx + 1.0 + parallax_x, cy + 5.4), QPointF(cx + 1.0 + parallax_x, cy + 6.8))

        # Glowing Chin Micro Diode (Cyan)
        painter.setBrush(QBrush(QColor(0, 245, 255, int(220 * energy_pulse))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(cx - 0.7 + parallax_x, cy + 4.2, 1.4, 0.6), 0.2, 0.2)

        painter.restore()

    def _paint_scaling_clock(self, painter: QPainter, center_x: float = None):
        """
        Apple Dynamic Island Living Unified Center Clock.
        Features permanent rock-solid center anchoring with zero bobbing,
        unified matching size across both compact and expanded modes (8.2pt DemiBold, 18px pill),
        and zero jitter.
        Dynamically follows the media player center throughout drawer/lyrics animations.
        """
        painter.save()
        p = self.expand_progress
        if center_x is not None:
            island_center_x = center_x
        else:
            island_center_x = self.canvas_w / 2.0
        cy = 17.0
        pill_h = 18.0
        pill_r = 5.0
        top_y = cy - pill_h / 2.0  # 8.0px

        clock_text = self.local_clock_text or self._format_local_clock()
        font_clock = _font("Segoe UI", 8.2, QFont.Weight.DemiBold)

        # Matched geometry metrics (exact same size in compact & expand)
        fm = QFontMetricsF(font_clock)
        tw = fm.horizontalAdvance(clock_text)
        pill_w = tw + 14.0

        clock_pill_rect = QRectF(island_center_x - pill_w / 2.0, top_y, pill_w, pill_h)

        # Elegant frosted glass capsule (constant matching size across all states)
        fill_alpha = int(12 + 4 * p)
        border_alpha = int(20 + 4 * p)
        painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1.0))
        painter.setBrush(QBrush(QColor(255, 255, 255, fill_alpha)))
        painter.drawRoundedRect(clock_pill_rect, pill_r, pill_r)

        # Crisp vector text rendering (100% stable font size)
        painter.setFont(font_clock)
        painter.setPen(QColor("#F1F5F9"))
        painter.drawText(clock_pill_rect, Qt.AlignmentFlag.AlignCenter, clock_text)

        painter.restore()

    @staticmethod
    def _draw_tab_nav_button(painter, rect: QRectF, forward: bool, opacity: float = 1.0):
        """Draw an icon-only slender chevron button with smooth fade and slide."""
        if opacity <= 0.01:
            return
        painter.save()
        painter.setOpacity(painter.opacity() * max(0.0, min(1.0, opacity)))

        center = rect.center()
        direction = 1.0 if forward else -1.0

        # Subtle slide-in micro-animation as opacity approaches 1.0
        slide_offset = (1.0 - opacity) * (4.0 if forward else -4.0)
        pill_w = 16.0
        pill_h = 44.0
        pill_rect = QRectF(
            center.x() - (pill_w / 2.0) + slide_offset,
            center.y() - (pill_h / 2.0),
            pill_w,
            pill_h,
        )

        # Apple frosted glass capsule background
        painter.setBrush(QBrush(QColor(255, 255, 255, 28)))
        painter.setPen(QPen(QColor(255, 255, 255, 42), 1.0))
        painter.drawRoundedRect(pill_rect, 8.0, 8.0)

        # Pipih slender arrow (slender height 15px, width 5.2px)
        arrow = QPainterPath()
        cx = pill_rect.center().x()
        cy = pill_rect.center().y()
        arrow.moveTo(cx - direction * 2.6, cy - 7.5)
        arrow.lineTo(cx + direction * 2.6, cy)
        arrow.lineTo(cx - direction * 2.6, cy + 7.5)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                QColor(255, 255, 255, 230),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(arrow)
        painter.restore()

    def _paint_empty_tab_content(self, painter, expanded_x: float, expanded_w: float, tab_index: int, opacity: float = 1.0):
        """Render an empty tab page placeholder with subtle styling and clean center positioning."""
        card_w = min(220.0, max(140.0, expanded_w - 120.0))
        h = self.cur_h
        avail_cy = (28.0 + (h - 18.0)) / 2.0
        card_h = min(54.0, max(44.0, h - 68.0))
        card_x = (self.canvas_w - card_w) / 2.0
        card_y = avail_cy - (card_h / 2.0)
        card_rect = QRectF(card_x, card_y, card_w, card_h)

        painter.save()
        painter.setOpacity(painter.opacity() * max(0.0, min(1.0, opacity)))
        dash_pen = QPen(QColor(150, 175, 235, 60), 1.2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(dash_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 8)))
        painter.drawRoundedRect(card_rect, 14.0, 14.0)

        # Tab 1 is the primary media/profile page, so empty tabs are numbered 2, 3, 4
        display_tab_num = tab_index + 1
        painter.setFont(_font("Segoe UI", 11.5, QFont.Weight.DemiBold))
        painter.setPen(QColor("#E2E8F0"))
        painter.drawText(
            QRectF(card_x, card_y + (card_h * 0.16), card_w, 20.0),
            Qt.AlignmentFlag.AlignCenter,
            f"Tab {display_tab_num}",
        )

        painter.setFont(_font("Segoe UI", 8.0, QFont.Weight.Medium))
        painter.setPen(QColor("#7E8CA2"))
        painter.drawText(
            QRectF(card_x, card_y + (card_h * 0.54), card_w, 16.0),
            Qt.AlignmentFlag.AlignCenter,
            "Tab Kosong",
        )
        painter.restore()

    def _paint_page_navigation(self, painter, indicator_y: float, center_x: float | None = None):
        self.tab_dots_rects = []
        dots_center_x = self.canvas_w / 2.0 if center_x is None else center_x
        t = getattr(self, "scroll_indicator_t", 0.0)

        # -----------------------------------------------------------------
        # LAYER A: PAGINATION DOTS (Fades & subtly scales out as t -> 1.0)
        # -----------------------------------------------------------------
        if t < 0.995:
            painter.save()
            dots_opacity = max(0.0, 1.0 - t)
            painter.setOpacity(painter.opacity() * dots_opacity)

            # Apple-style subtle contraction scale as dots fade out (1.0 -> 0.78)
            dots_scale = 1.0 - (0.22 * t)
            painter.translate(dots_center_x, indicator_y)
            painter.scale(dots_scale, dots_scale)
            painter.translate(-dots_center_x, -indicator_y)

            spacing = 14.0
            total_width = (self.total_pages - 1) * spacing
            start_x = dots_center_x - (total_width / 2.0)

            # 1. Background inactive dots
            for index in range(self.total_pages):
                dot_x = start_x + (index * spacing)
                hit_rect = QRectF(dot_x - 7.0, indicator_y - 7.0, 14.0, 14.0)
                if t < 0.5:
                    self.tab_dots_rects.append(hit_rect)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(140, 155, 180, 80)))
                painter.drawEllipse(QPointF(dot_x, indicator_y), 2.2, 2.2)

            # 2. Dynamic Worm / Elastic Stretch active mint indicator (Apple iOS Worm design)
            r = 2.5
            p_clamped = max(0.0, min(float(self.total_pages - 1), self.page_scroll_pos))
            i = int(math.floor(p_clamped))
            f = max(0.0, min(1.0, p_clamped - i))
            if i >= self.total_pages - 1:
                i = self.total_pages - 1
                f = 0.0

            if f <= 0.5:
                head_t = math.sin((f / 0.5) * (math.pi / 2.0))
                tail_t = 0.0
            else:
                head_t = 1.0
                tail_t = 1.0 - math.cos(((f - 0.5) / 0.5) * (math.pi / 2.0))

            x_i = start_x + (i * spacing)
            head_x = x_i + (head_t * spacing)
            tail_x = x_i + (tail_t * spacing)
            left = tail_x - r
            right = head_x + r
            width = max(r * 2.0, right - left)

            worm_rect = QRectF(left, indicator_y - r, width, r * 2.0)
            glow_pad = 2.0
            glow_rect = QRectF(left - glow_pad, indicator_y - r - glow_pad, width + 2.0 * glow_pad, (r + glow_pad) * 2.0)

            painter.setPen(Qt.PenStyle.NoPen)
            # Soft ambient glow aura that follows the stretching worm shape
            painter.setBrush(QBrush(QColor(167, 243, 208, 38)))
            painter.drawRoundedRect(glow_rect, r + glow_pad, r + glow_pad)
            # Active mint worm / dot (pure round dot at rest, liquid stretch during transit)
            painter.setBrush(QBrush(QColor("#A7F3D0")))
            painter.drawRoundedRect(worm_rect, r, r)

            painter.restore()

        # -----------------------------------------------------------------
        # LAYER B: HORIZONTAL SCROLLBAR (Blooms, expands & fades in as t -> 1.0)
        # -----------------------------------------------------------------
        if t > 0.005:
            painter.save()
            scroll_opacity = max(0.0, min(1.0, t))
            painter.setOpacity(painter.opacity() * scroll_opacity)

            # Apple spring scale (0.82 -> 1.0) centered on track
            scroll_scale = 0.82 + (0.18 * t)
            painter.translate(dots_center_x, indicator_y)
            painter.scale(scroll_scale, scroll_scale)
            painter.translate(-dots_center_x, -indicator_y)

            # Morphing track geometry: width expands smoothly from 32px to 54px
            track_w = 32.0 + (22.0 * t)
            track_h = 3.2
            track_x = dots_center_x - (track_w / 2.0)
            track_y = indicator_y - (track_h / 2.0)

            if t >= 0.5:
                self.vault_scroll_track_rect = QRectF(track_x - 6.0, track_y - 6.0, track_w + 12.0, track_h + 12.0)
            else:
                self.vault_scroll_track_rect = QRectF()

            painter.setPen(Qt.PenStyle.NoPen)
            # Track background (frosted subtle capsule)
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.drawRoundedRect(QRectF(track_x, track_y, track_w, track_h), 1.6, 1.6)

            # Active thumb pill calculation
            margin = 14.0
            content_w = min(self.expanded_w, self.cur_w) - (margin * 2.0)
            inner_w = max(1.0, content_w - 20.0)
            total_items = len(self.drop_vault.items) if hasattr(self, "drop_vault") else 0
            item_w = 82.0
            item_gap = 12.0
            total_w = max(1.0, (total_items * (item_w + item_gap)) - item_gap)
            max_scroll = max(0.0, total_w - inner_w)

            visible_ratio = min(1.0, max(0.18, inner_w / total_w))
            full_thumb_w = max(16.0, track_w * visible_ratio)
            # Morphing thumb width: starts smaller and expands into full thumb width
            thumb_w = max(8.0, 8.0 + ((full_thumb_w - 8.0) * t))

            scroll_ratio = min(1.0, max(0.0, getattr(self, "vault_scroll_x", 0.0) / max(1.0, max_scroll))) if max_scroll > 0.0 else 0.0
            thumb_x = track_x + (scroll_ratio * (track_w - thumb_w))

            # Cyan vibrant thumb with slight ambient glow
            painter.setBrush(QBrush(QColor(56, 189, 248, 50)))
            painter.drawRoundedRect(QRectF(thumb_x - 1.0, track_y - 1.0, thumb_w + 2.0, track_h + 2.0), 2.2, 2.2)
            painter.setBrush(QBrush(QColor("#38BDF8")))
            painter.drawRoundedRect(QRectF(thumb_x, track_y, thumb_w, track_h), 1.6, 1.6)

            painter.restore()
        else:
            self.vault_scroll_track_rect = QRectF()

    @staticmethod
    def _draw_settings_icon(painter, rect: QRectF, color: QColor):
        """Draw a compact gear with vector strokes for consistent rendering."""
        center = rect.center()
        painter.save()
        painter.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for spoke in range(8):
            angle = math.radians(spoke * 45.0)
            inner = QPointF(
                center.x() + math.cos(angle) * 3.8,
                center.y() + math.sin(angle) * 3.8,
            )
            outer = QPointF(
                center.x() + math.cos(angle) * 6.2,
                center.y() + math.sin(angle) * 6.2,
            )
            painter.drawLine(inner, outer)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 3.8, 3.8)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 1.4, 1.4)
        painter.restore()

    @staticmethod
    def format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        return f"{total // 60:02d}:{total % 60:02d}"

    @staticmethod
    def _friendly_app_name(executable_path: str, window_title: str) -> str:
        executable = os.path.basename(executable_path).lower()
        known_names = {
            "chrome.exe": "Chrome",
            "msedge.exe": "Microsoft Edge",
            "firefox.exe": "Firefox",
            "brave.exe": "Brave",
            "opera.exe": "Opera",
            "explorer.exe": "File Explorer",
            "code.exe": "Visual Studio Code",
            "devenv.exe": "Visual Studio",
            "spotify.exe": "Spotify",
            "vlc.exe": "VLC",
            "notepad.exe": "Notepad",
            "applicationframehost.exe": window_title or "Windows App",
        }
        if executable in known_names:
            return known_names[executable]
        name = os.path.splitext(os.path.basename(executable_path))[0]
        return name.replace("_", " ").replace("-", " ").title() or window_title or "Desktop"

    @staticmethod
    def _format_local_clock() -> str:
        local_time = time.localtime()
        hour = local_time.tm_hour % 12 or 12
        period = "AM" if local_time.tm_hour < 12 else "PM"
        return f"{hour}.{local_time.tm_min:02d} {period}"

    def _update_compact_status(self, now_perf: float):
        # The clock follows the machine's configured local time zone.
        if now_perf >= getattr(self, "_next_clock_poll", 0.0):
            self.local_clock_text = self._format_local_clock()
            self._next_clock_poll = now_perf + 0.5
        if sys.platform != "win32" or now_perf < self.next_active_app_poll:
            return
        # Polling responsif 60ms (~0.003ms CPU) agar robot mascot langsung muncul seketika saat aplikasi diminimalkan
        self.next_active_app_poll = now_perf + 0.06

        try:
            def _set_desktop():
                if self.is_browser_active or self.is_browser_maximized or self.is_tab_occluded:
                    self.is_browser_active = False
                    self.is_browser_maximized = False
                    self.is_tab_occluded = False
                    self.update()
                if self.active_app_identity != "desktop":
                    self.active_app_identity = "desktop"
                    self.active_app_path = ""
                    self.active_app_name = "Desktop"
                    self.active_app_icon = QIcon()
                    self.update()

            hwnd = user32.GetForegroundWindow()
            # 1. Jika hwnd NULL, atau sama dengan ShellWindow (Progman) / DesktopWindow
            if not hwnd or hwnd == user32.GetShellWindow() or hwnd == user32.GetDesktopWindow():
                self._last_polled_hwnd = None
                _set_desktop()
                return

            # 2. Jika jendela aktif berstatus minimized (IsIconic) -> Kembali ke desktop
            if user32.IsIconic(hwnd):
                self._last_polled_hwnd = None
                _set_desktop()
                return

            # 3. Fast-path: jika hwnd sama dengan yang sebelumnya, lewati OpenProcess & QueryImageName
            if hwnd == self._last_polled_hwnd:
                if self.is_browser_active:
                    is_max = bool(user32.IsZoomed(hwnd))
                    if is_max != self.is_browser_maximized:
                        self.is_browser_maximized = is_max
                        self.update()
                    if is_max and not self.is_hovered and now_perf >= self.next_tab_occlusion_poll:
                        self.next_tab_occlusion_poll = now_perf + 0.35
                        notch_screen_x = self.geometry().left() + (self.canvas_w - self.collapsed_w) / 2.0
                        tab_occluded = self.tab_detector.has_tab_under_notch(
                            notch_screen_x, self.collapsed_w, tab_y=18, exclude_hwnd=self.hwnd
                        )
                        if tab_occluded != self.is_tab_occluded:
                            self.is_tab_occluded = tab_occluded
                            self.update()
                return

            self._last_polled_hwnd = hwnd

            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)
            class_name = class_buffer.value.strip()

            # 3. Jendela shell desktop / taskbar / worker Windows
            desktop_classes = (
                "Progman",
                "WorkerW",
                "Shell_TrayWnd",
                "Shell_SecondaryTrayWnd",
                "DV2ControlHost",
                "ImmersiveLauncher",
            )
            if class_name in desktop_classes:
                _set_desktop()
                return

            process_id = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            pid_val = process_id.value

            # 4. Jika PID adalah 0 (System Idle / DWM background / tidak ada aplikasi), langsung aktifkan Desktop
            if not pid_val or pid_val == 0:
                _set_desktop()
                return

            # Abaikan jika proses yang aktif adalah Dynamic Island itu sendiri
            if pid_val == os.getpid():
                return

            title_buffer = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            window_title = title_buffer.value.strip()

            executable_path = ""
            process_handle = kernel32.OpenProcess(0x1000, False, pid_val)
            if process_handle:
                try:
                    path_buffer = ctypes.create_unicode_buffer(32768)
                    path_size = wintypes.DWORD(len(path_buffer))
                    if kernel32.QueryFullProcessImageNameW(
                        process_handle, 0, path_buffer, ctypes.byref(path_size)
                    ):
                        executable_path = path_buffer.value
                finally:
                    kernel32.CloseHandle(process_handle)

            # 5. Cek apakah ini explorer.exe tetapi bukan jendela File Explorer (CabinetWClass)
            exe_lower = os.path.basename(executable_path).lower() if executable_path else ""
            if not executable_path or (
                exe_lower == "explorer.exe" and class_name not in ("CabinetWClass", "ExploreWClass")
            ):
                _set_desktop()
                return

            # Deteksi otomatis browser aktif & maximized (fitur auto-shrink 4px micro-notch)
            browser_exes = (
                "chrome.exe",
                "msedge.exe",
                "firefox.exe",
                "brave.exe",
                "opera.exe",
                "opera_gx.exe",
                "vivaldi.exe",
                "arc.exe",
                "zen.exe",
                "waterfox.exe",
                "tor.exe",
            )
            is_browser = exe_lower in browser_exes
            is_max = False
            if is_browser:
                user32.IsZoomed.argtypes = (wintypes.HWND,)
                user32.IsZoomed.restype = wintypes.BOOL
                is_max = bool(user32.IsZoomed(hwnd))
                if not is_max:
                    w_rect = wintypes.RECT()
                    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
                    if user32.GetWindowRect(hwnd, ctypes.byref(w_rect)):
                        if w_rect.top <= 2 and (w_rect.bottom - w_rect.top) >= 450 and (w_rect.right - w_rect.left) >= (self.canvas_w * 0.7):
                            is_max = True

            if is_browser != self.is_browser_active or is_max != self.is_browser_maximized:
                self.is_browser_active = is_browser
                self.is_browser_maximized = is_max
                if not is_browser or not is_max:
                    self.is_tab_occluded = False
                self.update()

            # Validasi spesifik: Hanya auto-shrink jika ADA tab yang benar-benar tertutup oleh notch
            if is_browser and is_max:
                if not self.is_hovered and now_perf >= self.next_tab_occlusion_poll:
                    self.next_tab_occlusion_poll = now_perf + 0.35
                    notch_screen_x = self.geometry().left() + (self.canvas_w - self.collapsed_w) / 2.0
                    tab_occluded = self.tab_detector.has_tab_under_notch(
                        notch_screen_x, self.collapsed_w, tab_y=18, exclude_hwnd=self.hwnd
                    )
                    if tab_occluded != self.is_tab_occluded:
                        self.is_tab_occluded = tab_occluded
                        self.update()
            else:
                if self.is_tab_occluded:
                    self.is_tab_occluded = False
                    self.update()

            # 6. Komponen shell Windows seperti Start Menu / Search jika tanpa jendela aplikasi aktif
            if exe_lower in ("shellexperiencehost.exe", "startmenuexperiencehost.exe", "searchhost.exe"):
                if not window_title or window_title.lower() in ("start", "search", ""):
                    _set_desktop()
                    return

            identity = executable_path.casefold() if executable_path else f"title:{window_title}"
            if not identity or identity == self.active_app_identity:
                return

            self.active_app_identity = identity
            self.active_app_path = executable_path
            self.active_app_name = self._friendly_app_name(executable_path, window_title)
            if executable_path:
                cached_icon = self.active_app_icon_cache.get(executable_path.casefold())
                if cached_icon is None:
                    cached_icon = QFileIconProvider().icon(QFileInfo(executable_path))
                    if len(self.active_app_icon_cache) >= 32:
                        self.active_app_icon_cache.pop(next(iter(self.active_app_icon_cache)))
                    self.active_app_icon_cache[executable_path.casefold()] = cached_icon
                self.active_app_icon = cached_icon
            else:
                self.active_app_icon = QIcon()
            self.update()
        except Exception:
            return

    def set_click_through(self, enable: bool):
        """Mengatur agar area kanvas tembus klik saat mouse di luar Notch."""
        if sys.platform != "win32" or self.click_through_active == enable:
            return
        if not getattr(self, "hwnd", None):
            return
        try:
            self.click_through_active = enable
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if enable:
                user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
            else:
                user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
        except Exception:
            pass

    def _get_target_height_for_tab(self, tab_index: int) -> float:
        """
        Dynamically calculate height for any island tab:
        - Tab 0 (Tab 1): Media height (media_expanded_h=168.0) if media active, else Profile height (empty_expanded_h=124.0).
        - Other tabs (Tabs 2, 3, 4):
            If tab has custom content height registered, use that content's dynamic height.
            If tab is empty placeholder, dynamically match Tab 1's height (124px when idle, 168px when media active).
        """
        skip_ready = self.youtube_ad_detected and self.youtube_can_skip
        tab1_h = self.media_expanded_h if (self.has_media or skip_ready) else self.empty_expanded_h

        if tab_index == 0:
            return tab1_h

        # Future extensions hook: dynamic content height per tab
        custom_h = getattr(self, f"_tab_{tab_index}_content_h", None)
        if custom_h is not None:
            return float(custom_h)

        # Empty tabs dynamically match Tab 1's height
        return tab1_h

    def tick(self):
        now = time.perf_counter()
        self._update_compact_status(now)
        # Batasi dt maksimal agar tidak loncat jika PC sempat freeze
        dt = min(max(now - self.last_time, 0.001), 0.025)
        self.last_time = now

        # Update notch_rect geometry langsung di awal tick agar hit tests selalu 100% sinkron
        cur_x = (self.canvas_w - self.cur_w) / 2.0
        self.notch_rect = QRectF(cur_x, 0.0, self.cur_w, self.cur_h)

        # 1. Cek posisi kursor global secara real-time (100% akurat walau mouse digerakkan cepat)
        local_pos = QPointF(self.mapFromGlobal(QCursor.pos()))
        in_micro_mode = self.is_browser_active and self.is_browser_maximized and self.is_tab_occluded
        if in_micro_mode and not self.is_hovered and self.cur_h <= 12.0:
            # Micro-notch mode: touch zone 8px tall at screen top edge, keeping browser tabs 100% accessible
            touch_zone = QRectF(cur_x - 14.0, 0.0, self.cur_w + 28.0, 8.0)
            self.is_hovered = touch_zone.contains(local_pos)
        else:
            # Beri sedikit margin toleransi saat sudah terbuka agar tidak mudah tertutup sendiri
            hit_margin = 14.0 if self.is_hovered else 0.0
            active_zone = self.notch_rect.adjusted(
                -hit_margin, -hit_margin, hit_margin, hit_margin
            )
            self.is_hovered = active_zone.contains(local_pos)

        # Aktifkan/matikan click-through otomatis
        self.set_click_through(not self.is_hovered)

        # Deteksi hover pada tombol kontrol
        if self.is_hovered:
            self.hovered_btn = self._button_at(local_pos)
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
                if self.hovered_btn and self.hovered_btn != "skip_ad_stale"
                else Qt.CursorShape.ArrowCursor
            )
        else:
            self.hovered_btn = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # 2. Fisika Pegas Asimetris (Lebar & Tinggi dinamis mengikuti konten media & lirik aktif)
        keep_expanded = self.is_hovered or self.settings_open or self.profile_editor_open
        if keep_expanded:
            if self.settings_open or self.profile_editor_open:
                target_w = self.expanded_w
            elif self.lyrics_open and self.island_page_index == 0 and self.is_spotify_active:
                target_w = getattr(self, "lyrics_expanded_w", 640.0)
            else:
                target_w = self.expanded_w
        else:
            target_w = self.micro_notch_w if in_micro_mode else self.collapsed_w
        if keep_expanded:
            if self.settings_open or self.profile_editor_open:
                self.open_height = self.expanded_h
            else:
                self.open_height = self._get_target_height_for_tab(self.island_page_index)
        target_h = self.open_height if keep_expanded else (self.micro_notch_h if in_micro_mode else self.collapsed_h)

        # Apple iOS fluid spring tuning: critically damped harmonic oscillator (zeta = 1.000)
        # Uniform natural frequency (omega = 20.98 rad/s) for both axes guarantees zero phase lag,
        # zero geometric wobble, zero overshoot, and buttery smooth deceleration.
        sub_dt = dt * 0.25
        if abs(target_w - self.cur_w) > 0.04 or abs(self.vel_w) > 0.08 or abs(target_h - self.cur_h) > 0.04 or abs(self.vel_h) > 0.08:
            spring_k = 480.0
            spring_c = 44.0  # 2 * sqrt(480) = 43.82 -> zeta = 44.0 / 43.82 = 1.004 (critically damped)
            for _ in range(4):
                acc_w = spring_k * (target_w - self.cur_w) - spring_c * self.vel_w
                acc_h = spring_k * (target_h - self.cur_h) - spring_c * self.vel_h

                self.vel_w += acc_w * sub_dt
                self.vel_h += acc_h * sub_dt
                self.cur_w += self.vel_w * sub_dt
                self.cur_h += self.vel_h * sub_dt

            # Crisp settling threshold: eliminates long sub-pixel crawl shimmer
            if abs(target_w - self.cur_w) < 0.75 and abs(self.vel_w) < 14.0:
                self.cur_w, self.vel_w = target_w, 0.0
            if abs(target_h - self.cur_h) < 0.75 and abs(self.vel_h) < 14.0:
                self.cur_h, self.vel_h = target_h, 0.0
        else:
            self.cur_w, self.vel_w = target_w, 0.0
            self.cur_h, self.vel_h = target_h, 0.0

        # Direct physical coupling of lyrics animation progress with notch width (zero latency, zero phase lag)
        w_closed = self.expanded_w
        w_open = getattr(self, "lyrics_expanded_w", 640.0)
        span = max(1.0, w_open - w_closed)
        self.lyrics_anim_progress = max(0.0, min(1.0, (self.cur_w - w_closed) / span))

        # Sinkronkan status animasi ke audio meter untuk menghindari COM endpoint refresh saat bergerak
        self.audio_meter._is_animating = abs(self.vel_w) > 1.0 or abs(self.vel_h) > 1.0

        # Update notch_rect geometry post-integration
        self.notch_rect = QRectF((self.canvas_w - self.cur_w) / 2.0, 0.0, self.cur_w, self.cur_h)

        # Hitung progres ekspansi (0.0 -> 1.0)
        open_range = max(1.0, self.open_height - self.collapsed_h)
        raw_prog = (self.cur_h - self.collapsed_h) / open_range
        self.expand_progress = max(0.0, min(1.0, raw_prog))

        # Drive page scroll spring physics (critically damped)
        target_page = float(self.island_page_index)
        if abs(target_page - self.page_scroll_pos) > 0.001 or abs(self.page_scroll_vel) > 0.005:
            for _ in range(2):
                acc_page = 360.0 * (target_page - self.page_scroll_pos) - 38.0 * self.page_scroll_vel
                self.page_scroll_vel += acc_page * sub_dt
                self.page_scroll_pos += self.page_scroll_vel * sub_dt
            if abs(target_page - self.page_scroll_pos) < 0.002 and abs(self.page_scroll_vel) < 0.02:
                self.page_scroll_pos, self.page_scroll_vel = target_page, 0.0
        else:
            self.page_scroll_pos, self.page_scroll_vel = target_page, 0.0

        # Drive sequential Apple-style tab scale-fade transition (crisp, zero ghosting)
        if getattr(self, "tab_transition_t", 1.0) < 1.0:
            self.tab_transition_t = min(1.0, self.tab_transition_t + (dt / 0.22))

        # Frame-rate independent continuous exponential decay for micro-interactions
        decay_chevron = 1.0 - math.exp(-18.0 * dt)
        target_prev_op = 1.0 if (self.hovered_btn == "tab_previous" and not self.settings_open) else 0.0
        target_next_op = 1.0 if (self.hovered_btn == "tab_next" and not self.settings_open) else 0.0
        self.chevron_prev_opacity += (target_prev_op - self.chevron_prev_opacity) * decay_chevron
        self.chevron_next_opacity += (target_next_op - self.chevron_next_opacity) * decay_chevron
        # Drive smooth appearance/shift of profile edit pencil & speed pill
        target_pencil = 1.0 if not self.has_media else 0.0
        decay_pencil = 1.0 - math.exp(-16.0 * dt)
        self.pencil_presence += (target_pencil - self.pencil_presence) * decay_pencil

        # Drive button hover micro-animations with exact mathematical decay (tau = ~0.18s)
        decay_hover = 1.0 - math.exp(-22.0 * dt)
        button_names = (
            "profile_edit", "profile_cancel", "profile_reset", "profile_save",
            "settings", "settings_cancel", "settings_reset", "settings_save",
            "lyrics", "speaker_mute", "volume_slider", "volume_down", "volume_up", "prev", "play", "next", "skip_ad",
            "vault_qr_close", "vault_clear_all"
        )
        if getattr(self, "volume_pulse", 0.0) > 0.001:
            self.volume_pulse = max(0.0, self.volume_pulse - dt * 2.5)
        for key in button_names:
            target = 1.0 if self.hovered_btn == key else 0.0
            cur = self.btn_hover_anim.get(key, 0.0)
            if target > 0.0 or cur > 0.001:
                new_val = cur + (target - cur) * decay_hover
                self.btn_hover_anim[key] = 0.0 if (target == 0.0 and new_val < 0.002) else new_val

        # Drive vault item hover animations & QR modal fade/scale animation
        vault_active_qr = hasattr(self, "drop_vault") and bool(self.drop_vault.active_qr_item_id and self.drop_vault.get_item_by_id(self.drop_vault.active_qr_item_id))
        target_qr_anim = 1.0 if vault_active_qr else 0.0
        decay_qr = 1.0 - math.exp(-24.0 * dt)
        self.vault_qr_modal_anim += (target_qr_anim - self.vault_qr_modal_anim) * decay_qr
        if not vault_active_qr and self.vault_qr_modal_anim < 0.002:
            self.vault_qr_modal_anim = 0.0
            self.vault_qr_closing_item = None
            self.vault_qr_closing_qr = None

        # Drive smooth morph between pagination dots and vault horizontal scrollbar
        vault_overflows = False
        if hasattr(self, "drop_vault") and len(self.drop_vault.items) > 0:
            margin = 14.0
            content_w = min(self.expanded_w, self.cur_w) - (margin * 2.0)
            inner_w = content_w - 20.0
            total_items = len(self.drop_vault.items)
            item_w = 82.0
            item_gap = 12.0
            total_w = (total_items * (item_w + item_gap)) - item_gap
            vault_overflows = (total_w - inner_w) > 0.0

        vault_qr_showing = (
            hasattr(self, "drop_vault")
            and bool(self.drop_vault.active_qr_item_id and self.drop_vault.get_item_by_id(self.drop_vault.active_qr_item_id))
        ) or getattr(self, "vault_qr_modal_anim", 0.0) > 0.05

        wants_scroll_indicator = (self.island_page_index == 1) and vault_overflows and (not vault_qr_showing)
        target_indicator_t = 1.0 if wants_scroll_indicator else 0.0
        decay_indicator = 1.0 - math.exp(-20.0 * dt)
        self.scroll_indicator_t += (target_indicator_t - self.scroll_indicator_t) * decay_indicator
        if abs(target_indicator_t - self.scroll_indicator_t) < 0.002:
            self.scroll_indicator_t = target_indicator_t

        if hasattr(self, "drop_vault"):
            for item in self.drop_vault.items:
                h_key = f"vault_card:{item.id}"
                target_h = 1.0 if (self.hovered_btn == h_key or (self.hovered_btn and self.hovered_btn.endswith(f":{item.id}"))) else 0.0
                cur_h = self.vault_item_hover_anims.get(item.id, 0.0)
                if target_h > 0.0 or cur_h > 0.001:
                    new_h = cur_h + (target_h - cur_h) * decay_hover
                    self.vault_item_hover_anims[item.id] = 0.0 if (target_h == 0.0 and new_h < 0.002) else new_h

        # Drive smooth lyrics scrolling with continuous decay
        if self.lyrics_cues:
            target_cue = bisect.bisect_right(
                self.lyrics_timestamps, self.display_position_seconds(now)
            ) - 1
            target_cue = max(0, min(len(self.lyrics_cues) - 1, target_cue))
            decay_lyrics = 1.0 - math.exp(-14.0 * dt)
            self.lyrics_smooth_index += (float(target_cue) - self.lyrics_smooth_index) * decay_lyrics

        # 3. Update fase gelombang visualizer & audio-reactive spectrum
        if self.is_playing:
            self.wave_phase += dt * 8.5
        if self.is_playing or (self.expand_progress > 0.05 and self.island_page_index == 0):
            self._update_audio_reactive_spectrum(dt, now)

        # 4. Update system stats periodically when expanded
        if self.expand_progress > 0.4:
            self._update_system_stats(now)

        # 5. Smart Render Throttling:
        # Determine whether high-refresh-rate 125 FPS rendering is needed this tick
        is_animating = (
            abs(self.vel_w) > 0.05
            or abs(self.vel_h) > 0.05
            or abs(target_w - self.cur_w) > 0.08
            or abs(target_h - self.cur_h) > 0.08
            or getattr(self, "tab_transition_t", 1.0) < 1.0
            or abs(target_page - self.page_scroll_pos) > 0.002
            or abs(self.page_scroll_vel) > 0.01
            or abs(target_prev_op - self.chevron_prev_opacity) > 0.005
            or abs(target_next_op - self.chevron_next_opacity) > 0.005
            or abs(target_pencil - self.pencil_presence) > 0.005
            or any(v > 0.005 for v in self.btn_hover_anim.values())
            or getattr(self, "view_transition_t", 1.0) < 1.0
            or getattr(self, "volume_pulse", 0.0) > 0.005
            or (self.lyrics_open and self.lyrics_anim_progress < 0.99)
            or (not self.lyrics_open and self.lyrics_anim_progress > 0.01)
            or abs(target_qr_anim - getattr(self, "vault_qr_modal_anim", 0.0)) > 0.005
            or abs(target_indicator_t - getattr(self, "scroll_indicator_t", 0.0)) > 0.005
        )
        is_audio_active = self.is_playing or getattr(self, "_system_audio_active", False)
        is_hover_active = (
            self.is_hovered
            or self.chevron_prev_opacity > 0.005
            or self.chevron_next_opacity > 0.005
        )
        is_expanded = self.expand_progress > 0.05 or keep_expanded

        # Robot mascot animation on desktop (when collapsed and idle)
        show_robot_mascot = (
            (not is_expanded)
            and (
                self.active_app_icon.isNull()
                or self.active_app_name.lower() in ("desktop", "")
                or not self.active_app_path
            )
        )

        if is_animating or is_audio_active or is_hover_active or is_expanded:
            self.update()
        elif show_robot_mascot:
            # Silky 60 FPS animation for robot mascot idle bobbing/gazing on desktop (every 2nd tick ~16ms)
            self._robot_render_tick = getattr(self, "_robot_render_tick", 0) + 1
            if self._robot_render_tick % 2 == 0:
                self.update()
        else:
            # Completely idle compact pill with active window:
            # Update once per second for local clock
            sec_now = int(now)
            if sec_now != getattr(self, "_last_idle_update_sec", 0):
                self._last_idle_update_sec = sec_now
                self.update()

        # 6. Smart Working Set Memory Management:
        # Purge temporary objects and trim working set when island collapses back down
        if is_expanded:
            self._was_expanded = True
        elif getattr(self, "_was_expanded", False) and not is_animating:
            self._was_expanded = False
            QTimer.singleShot(1200, self._trim_memory)

        # Gentle periodic maintenance trim (every 2.5 minutes) when completely stationary & idle
        if not is_animating and not is_hover_active and not is_audio_active and not is_expanded:
            if now - getattr(self, "_last_memory_trim", 0.0) > 150.0:
                self._last_memory_trim = now
                self._trim_memory()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            button = self._button_at(event.position())
            if button == "profile_edit":
                self.open_profile_editor()
                event.accept()
                return
            if button == "profile_cancel":
                self._close_profile_editor(save=False)
                event.accept()
                return
            if button == "profile_reset":
                self._reset_profile_editor()
                event.accept()
                return
            if button == "profile_save":
                self._close_profile_editor(save=True)
                event.accept()
                return
            if button == "settings":
                self.open_appearance_settings()
                event.accept()
                return
            if button == "settings_cancel":
                self._close_appearance_settings(save=False)
                event.accept()
                return
            if button == "settings_reset":
                self._reset_appearance_settings()
                event.accept()
                return
            if button == "settings_save":
                self._close_appearance_settings(save=True)
                event.accept()
                return
            # The Drop Vault button actions
            if button == "vault_clear_all":
                if hasattr(self, "drop_vault"):
                    if self.drop_vault.active_qr_item_id:
                        cur_qr_it = self.drop_vault.get_item_by_id(self.drop_vault.active_qr_item_id)
                        if cur_qr_it:
                            self.vault_qr_closing_item = cur_qr_it
                            self.vault_qr_closing_qr = getattr(cur_qr_it, "teleport_qr", None)
                    self.drop_vault.clear_all()
                self.update()
                event.accept()
                return
            if button == "vault_qr_close":
                if hasattr(self, "drop_vault") and self.drop_vault.active_qr_item_id:
                    cur_qr_it = self.drop_vault.get_item_by_id(self.drop_vault.active_qr_item_id)
                    if cur_qr_it:
                        self.vault_qr_closing_item = cur_qr_it
                        self.vault_qr_closing_qr = getattr(cur_qr_it, "teleport_qr", None)
                self.drop_vault.stop_all_teleports()
                self.update()
                event.accept()
                return
            if button and button.startswith("vault_cut:"):
                item_id = button.removeprefix("vault_cut:")
                self.drop_vault.cut_file(item_id)
                self.update()
                event.accept()
                return
            if button and button.startswith("vault_qr:"):
                item_id = button.removeprefix("vault_qr:")
                if hasattr(self, "drop_vault") and self.drop_vault.active_qr_item_id == item_id:
                    cur_qr_it = self.drop_vault.get_item_by_id(item_id)
                    if cur_qr_it:
                        self.vault_qr_closing_item = cur_qr_it
                        self.vault_qr_closing_qr = getattr(cur_qr_it, "teleport_qr", None)
                self.drop_vault.toggle_teleport(item_id)
                self.update()
                event.accept()
                return
            if button and button.startswith("vault_remove:"):
                item_id = button.removeprefix("vault_remove:")
                if hasattr(self, "drop_vault") and self.drop_vault.active_qr_item_id == item_id:
                    cur_qr_it = self.drop_vault.get_item_by_id(item_id)
                    if cur_qr_it:
                        self.vault_qr_closing_item = cur_qr_it
                        self.vault_qr_closing_qr = getattr(cur_qr_it, "teleport_qr", None)
                self.drop_vault.remove_item(item_id)
                self.update()
                event.accept()
                return
            if button and button.startswith("vault_card:"):
                item_id = button.removeprefix("vault_card:")
                self.drag_start_pos = event.position().toPoint()
                self.dragged_vault_item = self.drop_vault.get_item_by_id(item_id)
                self.is_panning_vault = True
                self.pan_start_x = event.position().x()
                self.pan_start_scroll_x = getattr(self, "vault_scroll_x", 0.0)
                event.accept()
                return
            if self.island_page_index == 1 and not button:
                self.is_panning_vault = True
                self.pan_start_x = event.position().x()
                self.pan_start_scroll_x = getattr(self, "vault_scroll_x", 0.0)

            if button in ("tab_previous", "tab_next"):
                direction = -1 if button == "tab_previous" else 1
                new_idx = (self.island_page_index + direction) % self.total_pages
                if new_idx != self.island_page_index:
                    self.prev_island_page_index = self.island_page_index
                    self.island_page_index = new_idx
                    self.tab_transition_t = 0.0
                self.update()
                event.accept()
                return
            if getattr(self, "seek_rect", QRectF()).contains(event.position()):
                self.is_seeking = True
                self._seek_from_pos(event.position().x())
                event.accept()
                return
            if button == "lyrics":
                if self.is_spotify_active:
                    self.lyrics_open = not self.lyrics_open
                    self.last_time = time.perf_counter()
                    self.update()
                event.accept()
                return
            if button == "speaker_mute":
                self.toggle_mute()
                self.volume_pulse = 0.35
                self.update()
                event.accept()
                return
            if button == "volume_slider":
                self.is_dragging_volume = True
                self._update_volume_from_pos(event.position().x())
                self.volume_pulse = 0.25
                self.update()
                event.accept()
                return
            if button and button.startswith("tab_dot:"):
                new_idx = int(button.removeprefix("tab_dot:"))
                if new_idx != self.island_page_index:
                    self.prev_island_page_index = self.island_page_index
                    self.island_page_index = new_idx
                    self.tab_transition_t = 0.0
                self.update()
                event.accept()
                return
            if button and button.startswith("gradient_"):
                side, value = button.removeprefix("gradient_").split(":", 1)
                self._select_gradient_color(side, QColor(value))
                event.accept()
                return
            if button == "skip_ad":
                if not self.youtube_bridge.request_skip():
                    self.tray.showMessage(
                        "Tombol Skip iklan tidak tersedia",
                        "Tunggu sampai tombol Skip ad muncul di YouTube.",
                        QSystemTrayIcon.MessageIcon.Information,
                        3000,
                    )
                event.accept()
                return
            if button == "skip_ad_stale":
                self.youtube_skip_stale_clicked = True
                self.update()
                event.accept()
                return
            commands = {
                "play": "play_pause",
                "prev": "previous",
                "next": "next",
                "volume_down": "volume_down",
                "volume_up": "volume_up",
            }
            if button in commands:
                self.media_controller.command(commands[button])
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Drag-out stashed item to external apps (Discord, Photoshop, Explorer)
        if getattr(self, "drag_start_pos", None) and getattr(self, "dragged_vault_item", None):
            delta = event.position().toPoint() - self.drag_start_pos
            if delta.manhattanLength() > QApplication.startDragDistance():
                if abs(delta.y()) > 8 or event.position().y() > self.cur_h or event.position().y() < 0:
                    drag = QDrag(self)
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile(self.dragged_vault_item.path)])
                    drag.setMimeData(mime)
                    if self.dragged_vault_item.thumbnail and not self.dragged_vault_item.thumbnail.isNull():
                        drag.setPixmap(self.dragged_vault_item.thumbnail)
                    elif getattr(self.dragged_vault_item, 'system_icon', None) and not self.dragged_vault_item.system_icon.isNull():
                        drag.setPixmap(self.dragged_vault_item.system_icon)
                    dropped_item_id = self.dragged_vault_item.id
                    self.drag_start_pos = None
                    self.dragged_vault_item = None
                    self.is_panning_vault = False
                    action = drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
                    # Automatically remove from Notch if dropped externally!
                    if action != Qt.DropAction.IgnoreAction or not self.rect().contains(event.position().toPoint()):
                        self.drop_vault.remove_item(dropped_item_id)
                    self.update()
                    event.accept()
                    return
                elif getattr(self, "is_panning_vault", False):
                    dx = event.position().x() - self.pan_start_x
                    content_w = max(100.0, self.cur_w - 28.0)
                    total_w = len(self.drop_vault.items) * 96.0 - 14.0
                    max_scroll = max(0.0, total_w - content_w)
                    self.vault_scroll_x = max(0.0, min(max_scroll, self.pan_start_scroll_x - dx))
                    self.update()
                    event.accept()
                    return
        elif getattr(self, "is_panning_vault", False):
            dx = event.position().x() - self.pan_start_x
            content_w = max(100.0, self.cur_w - 28.0)
            total_w = len(self.drop_vault.items) * 96.0 - 14.0
            max_scroll = max(0.0, total_w - content_w)
            self.vault_scroll_x = max(0.0, min(max_scroll, self.pan_start_scroll_x - dx))
            self.update()
            event.accept()
            return
        if getattr(self, "is_seeking", False):
            self._seek_from_pos(event.position().x())
            self.update()
            event.accept()
            return
        if getattr(self, "is_dragging_volume", False):
            self._update_volume_from_pos(event.position().x())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "is_panning_vault", False):
            self.is_panning_vault = False
        self.drag_start_pos = None
        self.dragged_vault_item = None
        if getattr(self, "is_seeking", False):
            self.is_seeking = False
            self.update()
            event.accept()
            return
        if getattr(self, "is_dragging_volume", False):
            self.is_dragging_volume = False
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)
    def wheelEvent(self, event):
        pos = event.position()
        if self.island_page_index == 1:
            delta = event.angleDelta().y() or event.angleDelta().x()
            content_w = max(100.0, self.cur_w - 28.0)
            total_w = len(self.drop_vault.items) * 96.0 - 14.0
            max_scroll = max(0.0, total_w - content_w)
            if max_scroll > 0.0:
                self.vault_scroll_x = max(0.0, min(max_scroll, getattr(self, "vault_scroll_x", 0.0) - (delta * 0.75)))
                self.update()
                event.accept()
                return
        if getattr(self, "vol_group_rect", QRectF()).contains(pos):
            delta = event.angleDelta().y()
            step = 0.03 if delta > 0 else -0.03
            cur_vol = self.audio_controller.get_volume()
            new_vol = max(0.0, min(1.0, cur_vol + step))
            self.audio_controller.set_volume(new_vol)
            self.current_volume_scalar = new_vol
            self.volume_pulse = 0.22
            self.update()
            event.accept()
            return
        super().wheelEvent(event)

    def _seek_from_pos(self, px: float):
        if getattr(self, "seek_rect", None) and self.seek_rect.width() > 0 and self.duration_seconds > 0:
            rel = (px - self.seek_rect.left()) / self.seek_rect.width()
            target_sec = max(0.0, min(self.duration_seconds, rel * self.duration_seconds))
            self.position_seconds = target_sec
            self.position_updated_at = time.perf_counter()
            self.media_controller.command(f"seek:{target_sec}")

    def _update_volume_from_pos(self, px: float):
        if getattr(self, "vol_track_rect", None) and self.vol_track_rect.width() > 0:
            rel = (px - self.vol_track_rect.left()) / self.vol_track_rect.width()
            new_vol = max(0.0, min(1.0, rel))
            self.audio_controller.set_volume(new_vol)
            self.current_volume_scalar = new_vol
            self.is_audio_muted = (new_vol <= 0.001)

    def toggle_mute(self):
        new_mute = not self.audio_controller.is_muted()
        self.audio_controller.set_mute(new_mute)
        self.is_audio_muted = new_mute

    def create_notch_path(self, x: float, w: float, h: float, ear_r: float, bottom_r: float):
        """
        Membuat bentuk Desktop Notch yang menyatu dengan tepi atas layar (y=0).
        Menggunakan kurva Bezier cekung (concave ears) di kiri-kanan atas.
        """
        ear_r = min(ear_r, h * 0.45)
        bottom_r = min(bottom_r, h * 0.5)

        key = (round(x, 1), round(w, 1), round(h, 1), round(ear_r, 1), round(bottom_r, 1))
        if getattr(self, "_cached_notch_key", None) == key and getattr(self, "_cached_notch_path", None) is not None:
            return self._cached_notch_path

        left = x
        right = x + w

        path = QPainterPath()
        # Mulai dari bibir atas layar di sebelah kiri Notch
        path.moveTo(left - ear_r, 0.0)
        # Telinga cekung kiri atas (melengkung mulus masuk ke dinding kiri)
        path.quadTo(left, 0.0, left, ear_r)
        # Turun ke sudut kiri bawah
        path.lineTo(left, h - bottom_r)
        # Sudut cembung kiri bawah
        path.quadTo(left, h, left + bottom_r, h)
        # Garis lurus di dasar bawah Notch
        path.lineTo(right - bottom_r, h)
        # Sudut cembung kanan bawah
        path.quadTo(right, h, right, h - bottom_r)
        # Naik di dinding kanan menuju telinga atas
        path.lineTo(right, ear_r)
        # Telinga cekung kanan atas (melengkung mulus kembali ke bibir layar y=0)
        path.quadTo(right, 0.0, right + ear_r, 0.0)
        path.closeSubpath()

        self._cached_notch_key = key
        self._cached_notch_path = path
        return path

    # =========================================================================
    # THE DROP VAULT: DRAG & DROP EVENT HANDLERS
    # =========================================================================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.is_drag_hovered = True
            self.update()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.is_drag_hovered = False
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.is_drag_hovered = False
        added_count = 0
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path and os.path.exists(local_path):
                    self.drop_vault.add_path(local_path)
                    added_count += 1
        
        if added_count > 0:
            self.vault_scroll_x = 0.0
            if self.island_page_index != 1:
                self.prev_island_page_index = self.island_page_index
                self.island_page_index = 1
                self.tab_transition_t = 0.0
            event.acceptProposedAction()
            self.update()
        else:
            super().dropEvent(event)

    # =========================================================================
    # THE DROP VAULT: TAB 2 RENDERING
    # =========================================================================
    def _paint_drop_vault(self, painter, expanded_x: float, expanded_w: float, opacity: float = 1.0):
        """Render Tab 2: The Drop Vault borderless shelf, full rich icons, dynamic transform hover."""
        self.btn_vault_qr_close_rect = QRectF()
        self.vault_item_rects = []

        painter.save()
        painter.setOpacity(painter.opacity() * max(0.0, min(1.0, opacity)))

        margin = 14.0
        content_x = expanded_x + margin
        content_w = expanded_w - (margin * 2.0)
        h = self.cur_h

        # Main Content Area (Starting with generous breathing gap below top status bar)
        shelf_y = 42.0
        shelf_h = min(106.0, max(80.0, h - shelf_y - 18.0))

        # Check if QR Teleport modal is active or exiting
        active_qr_id = self.drop_vault.active_qr_item_id
        active_item = self.drop_vault.get_item_by_id(active_qr_id) if active_qr_id else None
        modal_item = active_item or getattr(self, "vault_qr_closing_item", None)
        modal_anim = getattr(self, "vault_qr_modal_anim", 0.0)

        # 1. RENDER DROP VAULT SHELF (Fades in/out smoothly inverse to QR modal)
        shelf_opacity = 1.0 - modal_anim
        if shelf_opacity > 0.005:
            painter.save()
            painter.setOpacity(painter.opacity() * shelf_opacity)

            # --- THE DROP VAULT CONTAINER BOX (ALWAYS PRESERVED) ---
            drop_rect = QRectF(content_x, 36.0, content_w, 102.0)
            is_active_drop = getattr(self, "is_drag_hovered", False)

            dash_color = QColor("#38BDF8") if is_active_drop else QColor(56, 189, 248, 80)
            dash_pen = QPen(dash_color, 1.4 if is_active_drop else 1.1, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(dash_pen)
            painter.setBrush(QBrush(QColor(56, 189, 248, 20 if is_active_drop else 5)))
            painter.drawRoundedRect(drop_rect, 12.0, 12.0)

            if len(self.drop_vault.items) == 0:
                # --- EMPTY STATE: Show icon & texts ---
                icon_cx = drop_rect.center().x()
                icon_cy = drop_rect.top() + (drop_rect.height() * 0.36)

                # Suction tray
                painter.setPen(QPen(QColor("#38BDF8"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                tray = QPainterPath()
                tray.moveTo(icon_cx - 9.0, icon_cy + 1.0)
                tray.lineTo(icon_cx - 9.0, icon_cy + 6.0)
                tray.lineTo(icon_cx + 9.0, icon_cy + 6.0)
                tray.lineTo(icon_cx + 9.0, icon_cy + 1.0)
                painter.drawPath(tray)

                # Downward arrow
                arrow = QPainterPath()
                arrow.moveTo(icon_cx, icon_cy - 7.0)
                arrow.lineTo(icon_cx, icon_cy + 2.0)
                arrow.moveTo(icon_cx - 3.5, icon_cy - 1.5)
                arrow.lineTo(icon_cx, icon_cy + 2.0)
                arrow.lineTo(icon_cx + 3.5, icon_cy - 1.5)
                painter.drawPath(arrow)

                # Labels
                painter.setFont(_font("Segoe UI", 9.0, QFont.Weight.Bold))
                painter.setPen(QColor("#38BDF8" if is_active_drop else "#FFFFFF"))
                label_text = "LEPASKAN UNTUK MENGGANTUNG FILE" if is_active_drop else "Tarik & Lepas File ke Sini"
                painter.drawText(QRectF(content_x, icon_cy + 11.0, content_w, 16.0), Qt.AlignmentFlag.AlignCenter, label_text)

                painter.setFont(_font("Segoe UI", 7.4, QFont.Weight.Medium))
                painter.setPen(QColor("#7DD3FC" if is_active_drop else "#CBD5E1"))
                painter.drawText(QRectF(content_x, icon_cy + 28.0, content_w, 14.0), Qt.AlignmentFlag.AlignCenter, "QR Teleport ke HP • 1-Klik Cut • Drag-Out ke Mana Saja")

            else:
                # --- POPULATED STATE: Render files inside the box, text is hidden ---
                item_w = 82.0
                item_gap = 12.0
                total_items = len(self.drop_vault.items)
                total_w = (total_items * (item_w + item_gap)) - item_gap
                inner_w = drop_rect.width() - 20.0
                max_scroll = max(0.0, total_w - inner_w)
                self.vault_scroll_x = max(0.0, min(max_scroll, getattr(self, "vault_scroll_x", 0.0)))

                shelf_clip_rect = drop_rect.adjusted(2.0, 2.0, -2.0, -2.0)
                painter.save()
                painter.setClipRect(shelf_clip_rect)

                cat_colors = {
                    "code": QColor("#0284C7"),
                    "doc": QColor("#3B82F6"),
                    "image": QColor("#A78BFA"),
                    "video": QColor("#F472B6"),
                    "audio": QColor("#34D399"),
                    "archive": QColor("#F59E0B"),
                }

                start_x = drop_rect.left() + 10.0
                for idx, item in enumerate(self.drop_vault.items):
                    ix = start_x + (idx * (item_w + item_gap)) - self.vault_scroll_x
                    # Culling offscreen items
                    if ix + item_w < content_x - 50.0 or ix > content_x + content_w + 50.0:
                        continue

                    item_anim = self.vault_item_hover_anims.get(item.id, 0.0)
                    lift = item_anim * 3.0

                    icon_size = 56.0
                    icon_x = ix + (item_w - icon_size) / 2.0
                    icon_y = shelf_y - lift
                    icon_rect = QRectF(icon_x, icon_y, icon_size, icon_size)

                    bottom_y = 104.0 - lift
                    bottom_h = 32.0
                    bottom_rect = QRectF(ix, bottom_y, item_w, bottom_h)
                    item_full_rect = icon_rect | bottom_rect

                    # Smooth hover glow card background
                    if item_anim > 0.005:
                        painter.save()
                        card_bg_rect = item_full_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
                        painter.setBrush(QBrush(QColor(56, 189, 248, int(20 * item_anim))))
                        painter.setPen(QPen(QColor(56, 189, 248, int(70 * item_anim)), 0.8))
                        painter.drawRoundedRect(card_bg_rect, 10.0, 10.0)
                        painter.restore()

                    # Detect if hovered
                    is_hovered = (self.hovered_btn == f"vault_card:{item.id}" or
                                  (self.hovered_btn and self.hovered_btn.endswith(f":{item.id}")))

                    # 1. FULL Icon rendering (Real system shell icon, image thumbnail, zip zipper, or folder)
                    if item.thumbnail and not item.thumbnail.isNull():
                        thumb_path = QPainterPath()
                        thumb_path.addRoundedRect(icon_rect, 13.0, 13.0)
                        painter.save()
                        painter.setClipPath(thumb_path)
                        painter.drawPixmap(int(icon_x), int(icon_y), int(icon_size), int(icon_size), item.thumbnail)
                        painter.restore()
                        painter.setPen(QPen(QColor(255, 255, 255, 35), 0.8))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRoundedRect(icon_rect, 13.0, 13.0)
                    elif getattr(item, "is_dir", False) or item.category == "folder":
                        if getattr(item, "system_icon", None) and not item.system_icon.isNull():
                            painter.drawPixmap(int(icon_x + 2), int(icon_y + 2), int(icon_size - 4), int(icon_size - 4), item.system_icon)
                        else:
                            grad = QLinearGradient(icon_x, icon_y, icon_x, icon_y + icon_size)
                            grad.setColorAt(0.0, QColor("#FBBF24"))
                            grad.setColorAt(1.0, QColor("#D97706"))
                            painter.setBrush(QBrush(grad))
                            painter.setPen(QPen(QColor(255, 255, 255, 50), 0.8))
                            painter.drawRoundedRect(icon_rect, 13.0, 13.0)
                    elif item.ext in ('.zip', '.rar', '.7z', '.tar', '.gz') or item.category == "archive":
                        grad = QLinearGradient(icon_x, icon_y, icon_x, icon_y + icon_size)
                        grad.setColorAt(0.0, QColor("#F59E0B"))
                        grad.setColorAt(1.0, QColor("#B45309"))
                        painter.setBrush(QBrush(grad))
                        painter.setPen(QPen(QColor(255, 255, 255, 50), 0.8))
                        painter.drawRoundedRect(icon_rect, 13.0, 13.0)

                        cx = icon_rect.center().x()
                        painter.setPen(QPen(QColor(0, 0, 0, 70), 2.0))
                        painter.drawLine(QPointF(cx, icon_y + 7.0), QPointF(cx, icon_y + icon_size - 16.0))

                        painter.setPen(QPen(QColor(255, 255, 255, 180), 1.6))
                        for zy in range(int(icon_y + 9.0), int(icon_y + icon_size - 17.0), 5):
                            painter.drawLine(QPointF(cx - 3.0, zy), QPointF(cx + 3.0, zy))

                        slider_y = icon_y + 23.0
                        painter.setBrush(QBrush(QColor("#FDE68A")))
                        painter.setPen(QPen(QColor("#78350F"), 0.8))
                        painter.drawRoundedRect(QRectF(cx - 4.5, slider_y, 9.0, 10.0), 2.0, 2.0)

                        painter.setFont(_font("Segoe UI", 7.5, QFont.Weight.Bold))
                        painter.setPen(QColor("#FFFFFF"))
                        painter.drawText(QRectF(icon_x, icon_y + icon_size - 16.0, icon_size, 13.0), Qt.AlignmentFlag.AlignCenter, "ZIP")
                    elif getattr(item, "system_icon", None) and not item.system_icon.isNull():
                        painter.drawPixmap(int(icon_x + 2), int(icon_y + 2), int(icon_size - 4), int(icon_size - 4), item.system_icon)
                    else:
                        c = cat_colors.get(item.category, QColor("#94A3B8"))
                        painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 30)))
                        painter.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 110), 1.0))
                        painter.drawRoundedRect(icon_rect, 13.0, 13.0)

                        painter.setFont(_font("Segoe UI", 13.0, QFont.Weight.Bold))
                        painter.setPen(c)
                        ext_tag = item.ext.replace(".", "").upper()[:4] or "FILE"
                        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, ext_tag)

                    # 2. Bottom Area: Name+Size OR Transformed 3 Icon Buttons
                    btn_w = 22.0
                    btn_h = 22.0
                    btn_gap = 4.0
                    total_bw = (btn_w * 3.0) + (btn_gap * 2.0)
                    btn_start_x = ix + (item_w - total_bw) / 2.0
                    btn_y = bottom_y + 4.0

                    btn_cut_rect = QRectF(btn_start_x, btn_y, btn_w, btn_h)
                    btn_qr_rect = QRectF(btn_start_x + btn_w + btn_gap, btn_y, btn_w, btn_h)
                    btn_del_rect = QRectF(btn_start_x + (btn_w + btn_gap) * 2.0, btn_y, btn_w, btn_h)

                    if not is_hovered:
                        # Unhovered: Name and Size
                        painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.DemiBold))
                        painter.setPen(QColor("#FFFFFF"))
                        elided_name = QFontMetricsF(painter.font()).elidedText(item.name, Qt.TextElideMode.ElideMiddle, item_w)
                        painter.drawText(QRectF(ix, bottom_y + 1.0, item_w, 14.0), Qt.AlignmentFlag.AlignCenter, elided_name)

                        painter.setFont(_font("Segoe UI", 6.2, QFont.Weight.Normal))
                        painter.setPen(QColor("#94A3B8"))
                        painter.drawText(QRectF(ix, bottom_y + 16.0, item_w, 12.0), Qt.AlignmentFlag.AlignCenter, item.size_str)
                    else:
                        # Hovered: Transforms into 3 micro buttons [ ✂ ] [ 📱 ] [ ✕ ] with frosted transparent glass
                        bar_rect = QRectF(btn_start_x - 3.0, btn_y - 2.0, total_bw + 6.0, btn_h + 4.0)
                        painter.setBrush(QBrush(QColor(255, 255, 255, 24)))
                        painter.setPen(QPen(QColor(255, 255, 255, 45), 0.8))
                        painter.drawRoundedRect(bar_rect, 7.0, 7.0)

                        # 1. CUT [ ✂ ]
                        cut_hvd = self.hovered_btn == f"vault_cut:{item.id}"
                        painter.setBrush(QBrush(QColor(255, 255, 255, 35 if cut_hvd else 16)))
                        painter.setPen(QPen(QColor(255, 255, 255, 55 if cut_hvd else 24), 0.6))
                        painter.drawRoundedRect(btn_cut_rect, 5.0, 5.0)
                        painter.setFont(_font("Segoe UI Emoji", 8.0))
                        painter.setPen(QColor("#FFFFFF" if cut_hvd else "#CBD5E1"))
                        painter.drawText(btn_cut_rect, Qt.AlignmentFlag.AlignCenter, "✂")

                        # 2. QR Code Vector Icon
                        qr_hvd = self.hovered_btn == f"vault_qr:{item.id}"
                        painter.setBrush(QBrush(QColor(56, 189, 248, 55 if qr_hvd else 22)))
                        painter.setPen(QPen(QColor(56, 189, 248, 160 if qr_hvd else 70), 0.6))
                        painter.drawRoundedRect(btn_qr_rect, 5.0, 5.0)

                        # Clean vector QR Code icon (3 corner finders + data pixels)
                        qr_col = QColor("#38BDF8" if qr_hvd else "#7DD3FC")
                        qcx = btn_qr_rect.center().x()
                        qcy = btn_qr_rect.center().y()
                        qx0 = qcx - 5.5
                        qy0 = qcy - 5.5

                        painter.setPen(QPen(qr_col, 0.9))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRect(QRectF(qx0, qy0, 4.0, 4.0))
                        painter.drawRect(QRectF(qx0 + 7.0, qy0, 4.0, 4.0))
                        painter.drawRect(QRectF(qx0, qy0 + 7.0, 4.0, 4.0))

                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(qr_col))
                        painter.drawRect(QRectF(qx0 + 1.2, qy0 + 1.2, 1.6, 1.6))
                        painter.drawRect(QRectF(qx0 + 8.2, qy0 + 1.2, 1.6, 1.6))
                        painter.drawRect(QRectF(qx0 + 1.2, qy0 + 8.2, 1.6, 1.6))
                        painter.drawRect(QRectF(qx0 + 7.0, qy0 + 7.0, 1.8, 1.8))
                        painter.drawRect(QRectF(qx0 + 9.4, qy0 + 7.0, 1.6, 1.6))
                        painter.drawRect(QRectF(qx0 + 7.0, qy0 + 9.4, 1.6, 1.6))
                        painter.drawRect(QRectF(qx0 + 9.4, qy0 + 9.4, 1.6, 1.6))

                        # 3. Hapus [ ✕ ]
                        del_hvd = self.hovered_btn == f"vault_remove:{item.id}"
                        painter.setBrush(QBrush(QColor(239, 68, 68, 55 if del_hvd else 22)))
                        painter.setPen(QPen(QColor(239, 68, 68, 160 if del_hvd else 70), 0.6))
                        painter.drawRoundedRect(btn_del_rect, 5.0, 5.0)
                        painter.setFont(_font("Segoe UI", 8.0, QFont.Weight.Bold))
                        painter.setPen(QColor("#F87171" if del_hvd else "#EF4444"))
                        painter.drawText(btn_del_rect, Qt.AlignmentFlag.AlignCenter, "✕")

                    # Record hitboxes
                    if getattr(self, "vault_qr_modal_anim", 0.0) < 0.5:
                        self.vault_item_rects.append((item.id, item_full_rect, btn_cut_rect, btn_qr_rect, btn_del_rect, is_hovered))

                painter.restore()

            painter.restore()

        # 2. RENDER QR TELEPORT MODAL OVERLAY (Smooth scale & fade in/out)
        modal_qr = getattr(modal_item, "teleport_qr", None) or getattr(self, "vault_qr_closing_qr", None)
        if modal_anim > 0.005 and modal_item and modal_qr:
            painter.save()
            modal_rect = QRectF(content_x, 34.0, content_w, 108.0)

            # Apple spring scale (0.92 -> 1.0) centered on modal
            painter.translate(modal_rect.center())
            scale_f = 0.92 + (0.08 * modal_anim)
            painter.scale(scale_f, scale_f)
            painter.translate(-modal_rect.center())
            painter.setOpacity(painter.opacity() * modal_anim)

            # Frosted glass background card
            painter.setBrush(QBrush(QColor(255, 255, 255, 14)))
            painter.setPen(QPen(QColor(255, 255, 255, 38), 0.8))
            painter.drawRoundedRect(modal_rect, 14.0, 14.0)

            # Close Button [ ✕ ] in top-right corner
            btn_size = 20.0
            close_btn_rect = QRectF(modal_rect.right() - btn_size - 10.0, modal_rect.top() + 10.0, btn_size, btn_size)
            if modal_anim > 0.5 and active_item:
                self.btn_vault_qr_close_rect = close_btn_rect

            close_h_val = self.btn_hover_anim.get("vault_qr_close", 0.0)
            close_bg_a = int(12 + (20 * close_h_val))
            close_border_a = int(24 + (35 * close_h_val))
            painter.setBrush(QBrush(QColor(255, 255, 255, close_bg_a)))
            painter.setPen(QPen(QColor(255, 255, 255, close_border_a), 0.6))
            painter.drawRoundedRect(close_btn_rect, 5.0, 5.0)

            painter.setFont(_font("Segoe UI", 9.0, QFont.Weight.Bold))
            painter.setPen(QColor(_interpolate_color(QColor("#94A3B8"), QColor("#FFFFFF"), close_h_val)))
            painter.drawText(close_btn_rect, Qt.AlignmentFlag.AlignCenter, "✕")

            # High-contrast crisp QR Pixmap
            qr_size = 80.0
            qr_x = modal_rect.left() + 16.0
            qr_y = modal_rect.center().y() - (qr_size / 2.0)
            qr_rect = QRectF(qr_x, qr_y, qr_size, qr_size)

            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(qr_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 8.0, 8.0)
            painter.drawPixmap(qr_rect.toRect(), modal_qr)

            # Text Info Block (Vertically centered with QR code)
            info_x = qr_rect.right() + 16.0
            info_w = max(40.0, close_btn_rect.left() - info_x - 8.0)
            info_y = qr_y + 1.0

            # Line 1: Badge + Subtitle
            painter.setFont(_font("Segoe UI", 6.8, QFont.Weight.Bold))
            painter.setPen(QColor("#38BDF8"))
            painter.drawText(QRectF(info_x, info_y, info_w, 13.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "⚡ TELEPORT KE HP")

            # Line 2: File Name
            painter.setFont(_font("Segoe UI", 9.6, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            elided_fname = QFontMetricsF(painter.font()).elidedText(modal_item.name, Qt.TextElideMode.ElideMiddle, info_w)
            painter.drawText(QRectF(info_x, info_y + 16.0, info_w, 18.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_fname)

            # Line 3: File Size
            painter.setFont(_font("Segoe UI", 7.2, QFont.Weight.Normal))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(QRectF(info_x, info_y + 36.0, info_w, 14.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"Ukuran: {modal_item.size_str}")

            # Line 4: Helper hint
            painter.setFont(_font("Segoe UI", 7.0, QFont.Weight.Normal))
            painter.setPen(QColor("#64748B"))
            painter.drawText(QRectF(info_x, info_y + 54.0, info_w, 14.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Scan dengan kamera HP dalam 1 WiFi")

            painter.restore()

        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.btn_tab_previous_rect = QRectF()
        self.btn_tab_next_rect = QRectF()

        x = (self.canvas_w - self.cur_w) / 2.0
        w = self.cur_w
        h = self.cur_h
        self.notch_rect = QRectF(x, 0.0, w, h)

        media_x = x
        media_w = min(self.expanded_w, w)
        margin = 16.0
        comp_vis_x = x + w - 31.0

        # Radius telinga atas & sudut bawah membesar dinamis mengikuti ukuran Notch
        ear_r = 12.0 + (6.0 * self.expand_progress)
        bottom_r = 16.0 + (10.0 * self.expand_progress)

        notch_path = self.create_notch_path(x, w, h, ear_r, bottom_r)

        # User-customizable two-color surface gradient. The center stop keeps
        # the transition polished while preserving the selected top/bottom hues.
        body_gradient = QLinearGradient(0.0, 0.0, 0.0, max(1.0, h))
        body_gradient.setColorAt(0.0, self.gradient_top)
        middle_color = getattr(self, "gradient_middle", None)
        if middle_color is None:
            self._update_gradient_middle()
            middle_color = self.gradient_middle
        body_gradient.setColorAt(0.52, middle_color)
        body_gradient.setColorAt(1.0, self.gradient_bottom)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(body_gradient))
        painter.drawPath(notch_path)

        border_gradient = QLinearGradient(x, 0.0, x + w, h)
        border_gradient.setColorAt(0.0, QColor(255, 255, 255, 14))
        border_gradient.setColorAt(0.5, QColor(255, 255, 255, 28))
        border_gradient.setColorAt(1.0, QColor(144, 164, 255, 42))
        border_pen = QPen(QBrush(border_gradient), 1.0)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(notch_path)

        # Kunci area gambar di dalam bentuk Notch agar konten tidak pernah bocor keluar
        painter.setClipPath(notch_path)

        if h <= 12.0:
            # Micro-Notch Mode: Minimalist cyber-glow accent bar and center diode
            micro_accent = QLinearGradient(x, 0.0, x + w, 0.0)
            micro_accent.setColorAt(0.0, QColor(0, 245, 255, 230))
            micro_accent.setColorAt(0.5, QColor(168, 85, 247, 255))
            micro_accent.setColorAt(1.0, QColor(255, 0, 127, 230))
            painter.setPen(QPen(QBrush(micro_accent), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x + 2.0, h - 1.0), QPointF(x + w - 2.0, h - 1.0))

            # Cyan optical diode at exact center
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 245, 255, 240)))
            painter.drawEllipse(QPointF(x + w / 2.0, h / 2.0), 1.2, 1.2)
        else:
            accent_line = QLinearGradient(x + bottom_r, 0.0, x + w - bottom_r, 0.0)
            accent_line.setColorAt(0.0, QColor(144, 164, 255, 0))
            accent_line.setColorAt(0.5, QColor(144, 164, 255, int(12 + 18 * self.expand_progress)))
            accent_line.setColorAt(1.0, QColor(144, 164, 255, 0))
            painter.setPen(QPen(QBrush(accent_line), 1.2))
            painter.drawLine(QPointF(x + bottom_r, h - 1.2), QPointF(x + w - bottom_r, h - 1.2))

        # --- KONTEN MODE KECIL (COMPACT PILL) ---
        # Apple fluid spring crossfade (fades out naturally as island expands OR shrinks to micro-notch)
        shrink_fade = max(0.0, min(1.0, (h - 12.0) / 16.0))
        if self.expand_progress < 0.32:
            header_opacity = (1.0 - (self.expand_progress / 0.32)) * shrink_fade
        else:
            header_opacity = 0.0

        if header_opacity > 0.005:
            painter.save()
            painter.setOpacity(header_opacity)

            # In compact mode the app icon has generous 14px padding and a frosted glass container tile
            mini_size = 20.0
            album_mini = QRectF(x + 14.0, 7.0, mini_size, mini_size)
            painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
            painter.drawRoundedRect(album_mini, 6.0, 6.0)
            show_robot = (
                self.active_app_icon.isNull()
                or self.active_app_name.lower() in ("desktop", "")
                or not self.active_app_path
            )
            if not show_robot and not self.active_app_icon.isNull():
                icon_size = 16
                icon_rect = album_mini.adjusted(2.0, 2.0, -2.0, -2.0)
                app_icon = self.active_app_icon.pixmap(QSize(icon_size, icon_size))
                mini_clip = QPainterPath()
                mini_clip.addRoundedRect(album_mini, 6.0, 6.0)
                painter.save()
                painter.setClipPath(mini_clip)
                painter.drawPixmap(icon_rect, app_icon, QRectF(app_icon.rect()))
                painter.restore()
            else:
                self._draw_robot_mascot(painter, album_mini.center(), time.perf_counter())

            # Compact 7-bar Cyan-to-Magenta spectrum visualizer
            bar_w = 2.0
            gap = 1.6
            num_bars = 7
            vis_w = num_bars * bar_w + (num_bars - 1) * gap  # 23.6px
            vis_x = x + w - 14.0 - vis_w  # Symmetrical 14.0px right margin mirroring left tile
            cy = 17.0
            r = bar_w / 2.0

            is_active_audio = self.is_playing or getattr(self, "_system_audio_active", False)
            beat_boost = getattr(self, "_audio_beat_punch", 0.0) * 5.0
            sample_bands = (1, 3, 6, 8, 10, 13, 15)
            idle_h = (3.0, 4.5, 6.0, 7.5, 6.0, 4.5, 3.0)

            for i in range(num_bars):
                u = i / float(num_bars - 1)
                bx = vis_x + i * (bar_w + gap)
                if is_active_audio:
                    col_idx = sample_bands[i]
                    act_energy = min(1.0, max(0.0, self.eq_col_heights[col_idx] / 11.0))
                    wave = math.sin(self.wave_phase * 1.5 + i * 0.9) * 0.15
                    bar_h = max(3.0, 3.5 + act_energy * 14.0 + beat_boost * (1.2 if 2 <= i <= 4 else 0.6) + wave * 3.0)
                    bar_rect = QRectF(bx, cy - bar_h / 2.0, bar_w, bar_h)
                    grad = self._get_spectrum_gradient(bar_rect, u)
                    painter.setBrush(QBrush(grad))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(bar_rect, r, r)
                else:
                    bar_h = idle_h[i]
                    bar_rect = QRectF(bx, cy - bar_h / 2.0, bar_w, bar_h)
                    painter.setBrush(QBrush(QColor(148, 163, 184, 120)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(bar_rect, r, r)

            painter.restore()

        # --- KONTEN MODE BESAR (EXPANDED NOTCH) ---
        # Seamless Apple crossfade from 0.18 to 0.70 eliminates empty void without double-easing stutter
        if self.expand_progress > 0.18:
            detail_op = min(1.0, (self.expand_progress - 0.18) / 0.52)

            if self.settings_open:
                painter.save()
                painter.setOpacity(detail_op)
                expanded_x = (self.canvas_w - self.expanded_w) / 2.0
                self._paint_appearance_settings(painter, expanded_x, self.expanded_w)
                self._paint_view_transition(painter)
                painter.restore()
                painter.end()
                return

            if self.profile_editor_open:
                painter.save()
                painter.setOpacity(detail_op)
                expanded_x = (self.canvas_w - self.expanded_w) / 2.0
                self._paint_profile_editor(painter, expanded_x, self.expanded_w)
                self._paint_view_transition(painter)
                painter.restore()
                painter.end()
                return

            painter.save()
            painter.setOpacity(detail_op)
            painter.setClipPath(notch_path)
            media_x = x
            media_w = min(self.expanded_w, w)
            header_center_y = 70.0  # Mathematically & optically centered between top status bar (y=26) and bottom controls (y=114)
            margin = 16.0

            media_left = x + margin
            w_closed = self.expanded_w
            w_open = getattr(self, "lyrics_expanded_w", 640.0)
            span = max(1.0, w_open - w_closed)
            lp = max(0.0, min(1.0, (w - w_closed) / span))
            self.lyrics_anim_progress = lp

            base_media_w = min(self.expanded_w, w) - (margin * 2.0)
            # Solid media width: eliminates accordion squeeze/stretch jitter so all controls glide as a rigid body
            media_w_area = base_media_w

            # Direct physical centering: algebraically identical to canvas_w/2 when closed,
            # and smoothly moves to media area center with 100% frame-1 physical synchronization!
            dots_center_x = media_left + (media_w_area / 2.0)

            # Previous & Next tab button hitboxes (centered vertically on the island)
            btn_hit_w = 24.0
            btn_hit_h = 50.0
            btn_y = (h - btn_hit_h) / 2.0
            self.btn_tab_previous_rect = QRectF(x + 2.0, btn_y, btn_hit_w, btn_hit_h)
            media_divider_x = media_left + media_w_area + 14.0
            # Smoothly anchored: when closed sits 14px from right notch edge; when lyrics open sits locked at media right boundary (in red box, never in lyrics layout)
            closed_nav_x = (x + w - 2.0 - btn_hit_w)
            open_nav_x = (media_left + media_w_area) - (btn_hit_w / 2.0) + 4.0
            next_nav_x = (1.0 - lp) * closed_nav_x + lp * open_nav_x
            self.btn_tab_next_rect = QRectF(next_nav_x, btn_y, btn_hit_w, btn_hit_h)

            # 1. Top Notification & Status Bar (Battery, CPU, RAM, Wi-Fi, Bluetooth, Gradient Settings Gear)
            self._paint_top_status_bar(painter, x, w, margin, draw_clock=False)

            # 1. Determine which tab to render based on sequential scale-fade lifecycle
            u = getattr(self, "tab_transition_t", 1.0)
            if u >= 1.0:
                cur_tab = self.island_page_index
                tab_op = 1.0
                tab_scale = 1.0
            elif u < 0.42:
                # Phase 1: Outgoing tab smoothly shrinks (1.0 -> 0.95) and fades out (1.0 -> 0.0)
                cur_tab = getattr(self, "prev_island_page_index", self.island_page_index)
                p = u / 0.42
                tab_op = 1.0 - p
                tab_scale = 1.0 - 0.05 * p
            else:
                # Phase 2: Incoming tab smoothly expands (0.95 -> 1.0) and fades in (0.0 -> 1.0)
                cur_tab = self.island_page_index
                q = (u - 0.42) / 0.58
                tab_op = q
                tab_scale = 0.95 + 0.05 * q

            # Clear button hitboxes when not actively settled on Page 0
            if self.island_page_index != 0 or u < 0.95:
                self.btn_lyrics_rect = QRectF()
                self.btn_prev_rect = QRectF()
                self.btn_play_rect = QRectF()
                self.btn_next_rect = QRectF()
                self.btn_volume_down_rect = QRectF()
                self.btn_volume_up_rect = QRectF()
                self.btn_speaker_rect = QRectF()
                self.vol_group_rect = QRectF()
                self.vol_track_rect = QRectF()
                self.btn_skip_ad_rect = QRectF()

            # 2. Render other tabs (Tabs 1, 2, 3...) when cur_tab != 0
            if cur_tab != 0:
                painter.save()
                if abs(tab_scale - 1.0) > 0.001:
                    cx = self.canvas_w / 2.0
                    cy = 75.0
                    painter.translate(cx, cy)
                    painter.scale(tab_scale, tab_scale)
                    painter.translate(-cx, -cy)
                if cur_tab == 1:
                    self._paint_drop_vault(painter, x, w, opacity=tab_op)
                else:
                    self._paint_empty_tab_content(painter, x, w, cur_tab, opacity=tab_op)
                painter.restore()

            # 3. Dynamic scale & fade for Page 0 (Media / Profile)
            p0_opacity = tab_op if cur_tab == 0 else 0.0

            painter.save()
            painter.setOpacity(painter.opacity() * p0_opacity)
            if cur_tab == 0 and abs(tab_scale - 1.0) > 0.001:
                cx = self.canvas_w / 2.0
                cy = 75.0
                painter.translate(cx, cy)
                painter.scale(tab_scale, tab_scale)
                painter.translate(-cx, -cy)

            # Layout parameters (media_left, media_w_area, dots_center_x, lp) are precomputed above

            # =========================================================================
            # CASE A: PROFILE MODE (NO MEDIA DETECTED - SNUG 124px)
            # =========================================================================
            if not self.has_media:
                card_y = 38.0
                tile_size = 46.0
                tile_rect = QRectF(media_left, card_y, tile_size, tile_size)

                # Robot Mascot Avatar Tile
                tile_grad = QLinearGradient(tile_rect.topLeft(), tile_rect.bottomRight())
                tile_grad.setColorAt(0.0, QColor("#111827"))
                tile_grad.setColorAt(1.0, QColor("#0B0F19"))
                painter.setBrush(QBrush(tile_grad))
                painter.setPen(QPen(QColor(56, 189, 248, 60), 1.0))
                painter.drawRoundedRect(tile_rect, 12.0, 12.0)
                self._draw_robot_mascot(painter, tile_rect.center(), time.perf_counter())

                # Profile Name + Verified Cyan Badge
                text_x = tile_rect.right() + 14.0
                name_y = card_y + 4.0
                painter.setFont(_font("Segoe UI", 11.2, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF"))
                fm_name = painter.fontMetrics()
                display_name = fm_name.elidedText(self.profile_name, Qt.TextElideMode.ElideRight, 160)
                painter.drawText(QRectF(text_x, name_y, 160.0, 20.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display_name)

                # Verified Badge
                drawn_name_w = fm_name.horizontalAdvance(display_name)
                badge_cx = text_x + drawn_name_w + 10.0
                badge_cy = name_y + 10.0
                badge_r = 5.5
                painter.setPen(Qt.PenStyle.NoPen)
                badge_grad = QLinearGradient(badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r)
                badge_grad.setColorAt(0.0, QColor("#00F5FF"))
                badge_grad.setColorAt(1.0, QColor("#3B82F6"))
                painter.setBrush(QBrush(badge_grad))
                painter.drawEllipse(QPointF(badge_cx, badge_cy), badge_r, badge_r)
                painter.setPen(QPen(QColor("#FFFFFF"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.drawLine(QPointF(badge_cx - 2.0, badge_cy - 0.2), QPointF(badge_cx - 0.4, badge_cy + 1.6))
                painter.drawLine(QPointF(badge_cx - 0.4, badge_cy + 1.6), QPointF(badge_cx + 2.0, badge_cy - 1.4))

                # Glowing Online Diode + Status Subtitle
                status_y = name_y + 22.0
                diode_cx = text_x + 4.0
                diode_cy = status_y + 8.5
                painter.setBrush(QBrush(QColor(74, 222, 128, 50)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(diode_cx, diode_cy), 4.5, 4.5)
                painter.setBrush(QBrush(QColor("#4ADE80")))
                painter.drawEllipse(QPointF(diode_cx, diode_cy), 2.5, 2.5)

                painter.setFont(_font("Segoe UI", 8.8, QFont.Weight.Medium))
                painter.setPen(QColor("#94A3B8"))
                display_status = painter.fontMetrics().elidedText(self.profile_status, Qt.TextElideMode.ElideRight, 170)
                painter.drawText(QRectF(text_x + 14.0, status_y, 170.0, 17.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display_status)

                # Ambient Idle Wavebars (Right Side) - Eliminates empty void!
                waves_w = 80.0
                waves_start_x = x + w - margin - waves_w
                waves_count = 11
                waves_spacing = waves_w / waves_count
                for wi in range(waves_count):
                    val = 0.4 + 0.3 * math.sin(wi * 0.7 + self.wave_phase * 0.5)
                    bh = max(3.0, val * 18.0)
                    bx = waves_start_x + wi * waves_spacing
                    by = card_y + 23.0 - (bh / 2.0)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(56, 189, 248, int(80 + val * 120))))
                    painter.drawRoundedRect(QRectF(bx, by, 2.2, bh), 1.1, 1.1)

                # Clear playback and volume controls in profile mode
                self.btn_lyrics_rect = QRectF()
                self.btn_prev_rect = QRectF()
                self.btn_play_rect = QRectF()
                self.btn_next_rect = QRectF()
                self.btn_volume_down_rect = QRectF()
                self.btn_volume_up_rect = QRectF()
                self.btn_skip_ad_rect = QRectF()
                self.btn_speaker_rect = QRectF()
                self.vol_group_rect = QRectF()
                self.vol_track_rect = QRectF()
                self.seek_rect = QRectF()

            # =========================================================================
            # CASE B: MEDIA PLAYER HUB (PLAYING OR PAUSED)
            # =========================================================================
            else:
                track_y = 38.0
                art_size = 46.0
                art_rect = QRectF(media_left, track_y, art_size, art_size)

                # 1. Album Artwork Squircle (12px radius)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
                painter.drawRoundedRect(art_rect.translated(0.0, 2.0), 12.0, 12.0)

                if not self.album_art.isNull():
                    art_clip = QPainterPath()
                    art_clip.addRoundedRect(art_rect, 12.0, 12.0)
                    painter.save()
                    painter.setClipPath(art_clip)
                    painter.drawPixmap(art_rect, self.album_art, QRectF(self.album_art.rect()))
                    painter.restore()
                else:
                    art_grad = QLinearGradient(art_rect.topLeft(), art_rect.bottomRight())
                    art_grad.setColorAt(0.0, QColor("#6366F1"))
                    art_grad.setColorAt(1.0, QColor("#3B82F6"))
                    painter.setBrush(QBrush(art_grad))
                    painter.drawRoundedRect(art_rect, 12.0, 12.0)
                    painter.setFont(_font("Segoe UI Symbol", 16.0, QFont.Weight.Bold))
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(art_rect, Qt.AlignmentFlag.AlignCenter, "♫")

                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, 30), 0.8))
                painter.drawRoundedRect(art_rect, 12.0, 12.0)

                # 2. Song Title & Subtitle (Cassandra · Cinta Terbaik)
                text_left = media_left + art_size + 10.0
                eq_w = 84.0
                text_max_w = max(40.0, media_w_area - art_size - 14.0 - eq_w - 6.0)

                has_distinct_album = (
                    bool(self.track_album)
                    and self.track_album.strip()
                    and self.track_album.strip().lower() not in (
                        self.track_title.strip().lower(),
                        self.track_artist.strip().lower(),
                        "unknown album", "single",
                    )
                )
                if self.track_artist and has_distinct_album:
                    subtitle = f"{self.track_artist} · {self.track_album}"
                elif self.track_artist:
                    subtitle = self.track_artist
                else:
                    subtitle = self.track_album or ""

                painter.setFont(_font("Segoe UI", 10.2, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF"))
                elided_title = painter.fontMetrics().elidedText(self.track_title, Qt.TextElideMode.ElideRight, int(text_max_w))
                painter.drawText(QRectF(text_left, track_y + 4.0, text_max_w, 20.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

                painter.setFont(_font("Segoe UI", 8.6, QFont.Weight.Medium))
                painter.setPen(QColor("#94A3B8"))
                elided_subtitle = painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideRight, int(text_max_w))
                painter.drawText(QRectF(text_left, track_y + 24.0, text_max_w, 18.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_subtitle)

                # 3. Silk Audio Equalizer (13 bars) on Right
                eq_start_x = media_left + media_w_area - eq_w
                bar_count = 13
                bar_spacing = eq_w / bar_count
                eq_grad = QLinearGradient(eq_start_x, track_y + 10.0, eq_start_x + eq_w, track_y + 36.0)
                eq_grad.setColorAt(0.0, QColor("#38BDF8"))
                eq_grad.setColorAt(1.0, QColor("#C084FC"))

                is_active_audio = self.is_playing or getattr(self, "_system_audio_active", False)
                for i in range(bar_count):
                    if is_active_audio:
                        col_idx = min(len(self.eq_col_heights) - 1, int(i * (len(self.eq_col_heights) / bar_count)))
                        act_energy = min(1.0, max(0.0, self.eq_col_heights[col_idx] / 11.0))
                        bh = max(3.5, act_energy * 22.0)
                    else:
                        bh = 4.0
                    bx = eq_start_x + i * bar_spacing
                    by = track_y + 23.0 - (bh / 2.0)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(eq_grad if is_active_audio else QColor(148, 163, 184, 120)))
                    painter.drawRoundedRect(QRectF(bx, by, 2.4, bh), 1.2, 1.2)

                # 4. Dedicated Full-Width Seekbar Row (seek_y = 94.0)
                seek_y = 94.0
                seek_w = media_w_area
                self.seek_rect = QRectF(media_left, seek_y - 4.0, seek_w, 16.0)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
                painter.drawRoundedRect(QRectF(media_left, seek_y, seek_w, 3.2), 1.6, 1.6)

                display_pos = self.display_position_seconds()
                dur = self.duration_seconds
                progress = min(1.0, max(0.0, display_pos / dur)) if dur > 0 else 0.0
                prog_w = seek_w * progress

                if prog_w > 0.0:
                    played_grad = QLinearGradient(media_left, seek_y, media_left + prog_w, seek_y)
                    played_grad.setColorAt(0.0, QColor("#38BDF8"))
                    played_grad.setColorAt(1.0, QColor("#60A5FA"))
                    painter.setBrush(QBrush(played_grad))
                    painter.drawRoundedRect(QRectF(media_left, seek_y, prog_w, 3.2), 1.6, 1.6)

                # Thumb
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.setPen(QPen(QColor(56, 189, 248, 180), 1.2))
                painter.drawEllipse(QPointF(media_left + prog_w, seek_y + 1.6), 4.2, 4.2)

                # Time Labels
                painter.setFont(_font("Segoe UI", 7.6, QFont.Weight.Medium))
                painter.setPen(QColor("#64748B"))
                painter.drawText(QRectF(media_left, seek_y + 4.0, 50.0, 14.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.format_time(display_pos))
                painter.drawText(QRectF(media_left + seek_w - 50.0, seek_y + 4.0, 50.0, 14.0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.format_time(dur))

                # 5. Bottom Row: Controls & Volume Slider (ctrl_y = 116.0, unified centerline y=129.0)
                ctrl_y = 116.0
                row_h = 26.0
                cy_row = ctrl_y + (row_h / 2.0)
                media_right = media_left + media_w_area

                # 5a. Speaker Icon + Volume Slider Capsule [ 🔈 ═════●───── ] (FAR LEFT)
                vol_group_x = media_left
                vol_group_w = 112.0
                self.vol_group_rect = QRectF(vol_group_x, ctrl_y, vol_group_w, 26.0)
                self.btn_speaker_rect = QRectF(vol_group_x, ctrl_y, 30.0, 26.0)

                vol_track_x = vol_group_x + 32.0
                vol_track_w = 70.0
                vol_track_y = ctrl_y + 11.5
                self.vol_track_rect = QRectF(vol_track_x, vol_track_y, vol_track_w, 3.0)

                # Capsule Background
                speaker_hovered = self.hovered_btn == "speaker_mute"
                slider_hovered = self.hovered_btn == "volume_slider" or getattr(self, "is_dragging_volume", False)
                painter.setBrush(QBrush(QColor(255, 255, 255, 18 if (speaker_hovered or slider_hovered) else 11)))
                painter.setPen(QPen(QColor(255, 255, 255, 16), 0.8))
                painter.drawRoundedRect(self.vol_group_rect, 7.5, 7.5)

                if not getattr(self, "is_dragging_volume", False):
                    self.current_volume_scalar = self.audio_controller.get_volume()
                    self.is_audio_muted = self.audio_controller.is_muted()

                cur_vol = getattr(self, "current_volume_scalar", 0.5)
                is_muted = getattr(self, "is_audio_muted", False)
                vol_pulse = getattr(self, "volume_pulse", 0.0)

                # Draw Animated Speaker Icon (Clean 6.5px left padding, elegant waves)
                speaker_col = QColor("#F87171") if (is_muted or cur_vol <= 0.001) else (
                    _interpolate_color(QColor("#94A3B8"), QColor("#FFFFFF"), 1.0 if speaker_hovered else 0.0)
                )
                self._draw_animated_speaker_icon(
                    painter,
                    vol_group_x + 13.0,
                    cy_row,
                    0.0 if is_muted else cur_vol,
                    pulse=vol_pulse,
                    is_mute=is_muted,
                    color=speaker_col,
                )

                # Volume Track Background
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 255, 24)))
                painter.drawRoundedRect(self.vol_track_rect, 1.5, 1.5)

                # Volume Track Filled
                fill_ratio = 0.0 if is_muted else max(0.0, min(1.0, cur_vol))
                vol_val_w = vol_track_w * fill_ratio
                if vol_val_w > 0.0:
                    vol_fill_grad = QLinearGradient(vol_track_x, vol_track_y, vol_track_x + vol_val_w, vol_track_y)
                    vol_fill_grad.setColorAt(0.0, QColor("#38BDF8"))
                    vol_fill_grad.setColorAt(1.0, QColor("#60A5FA"))
                    painter.setBrush(QBrush(vol_fill_grad))
                    painter.drawRoundedRect(QRectF(vol_track_x, vol_track_y, vol_val_w, 3.0), 1.5, 1.5)

                # Thumb (centered at cy_row, clean cushion from right capsule border)
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.setPen(QPen(QColor(56, 189, 248, 200), 1.0))
                painter.drawEllipse(QPointF(vol_track_x + vol_val_w, cy_row), 3.5, 3.5)

                # 5b. Lyrics Button (FAR RIGHT - Butter-smooth color & glow transition)
                if self.is_spotify_active:
                    lyr_w = 26.0
                    self.btn_lyrics_rect = QRectF(media_right - lyr_w, ctrl_y, lyr_w, 26.0)
                    lyr_hover_t = self.btn_hover_anim.get("lyrics", 0.0)
                    bg_inactive = QColor(255, 255, 255, int(12 + 16 * lyr_hover_t))
                    bg_active = QColor(56, 189, 248, int(40 + 20 * lyr_hover_t))
                    bg_col = _interpolate_color(bg_inactive, bg_active, lp)

                    border_inactive = QColor(255, 255, 255, int(20 + 25 * lyr_hover_t))
                    border_active = QColor(56, 189, 248, int(180 + 40 * lyr_hover_t))
                    border_col = _interpolate_color(border_inactive, border_active, lp)

                    note_inactive = _interpolate_color(QColor("#E2E8F0"), QColor("#FFFFFF"), lyr_hover_t)
                    note_active = QColor("#38BDF8")
                    note_col = _interpolate_color(note_inactive, note_active, lp)

                    painter.setBrush(QBrush(bg_col))
                    painter.setPen(QPen(border_col, 0.8))
                    painter.drawRoundedRect(self.btn_lyrics_rect, 7.5, 7.5)
                    self._draw_vector_lyrics_note(painter, self.btn_lyrics_rect.center().x(), cy_row, note_col)
                else:
                    self.btn_lyrics_rect = QRectF()

                # 5c. Transport Controls or YouTube Skip Ad (CENTERED OVER DOT INDICATORS)
                skip_ready = self.youtube_ad_detected and self.youtube_can_skip
                if skip_ready:
                    skip_width = min(126.0, max(92.0, media_w_area * 0.30))
                    self.btn_skip_ad_rect = QRectF(media_right - skip_width, ctrl_y, skip_width, 26.0)
                    self.btn_prev_rect = QRectF()
                    self.btn_play_rect = QRectF()
                    self.btn_next_rect = QRectF()

                    skip_stale = self.youtube_skip_stale
                    skip_t = self.btn_hover_anim.get("skip_ad", 0.0)
                    skip_bg = _interpolate_color(QColor("#F59E0B"), QColor("#FBBF24"), skip_t) if not skip_stale else QColor(140, 130, 100)
                    skip_border = QColor(255, 255, 255, 60) if not skip_stale else QColor(100, 95, 80)
                    painter.setPen(QPen(skip_border, 1.0))
                    painter.setBrush(QBrush(skip_bg))
                    painter.drawRoundedRect(self.btn_skip_ad_rect, 13.0, 13.0)

                    skip_icon = QPainterPath()
                    skip_icon.moveTo(self.btn_skip_ad_rect.left() + 10.0, ctrl_y + 7.5)
                    skip_icon.lineTo(self.btn_skip_ad_rect.left() + 17.0, ctrl_y + 13.0)
                    skip_icon.lineTo(self.btn_skip_ad_rect.left() + 10.0, ctrl_y + 18.5)
                    skip_icon.closeSubpath()
                    painter.setPen(Qt.PenStyle.NoPen)
                    skip_text_color = QColor("#090D16" if not skip_stale else "#2A261C")
                    painter.setBrush(QBrush(skip_text_color))
                    painter.drawPath(skip_icon)
                    painter.drawRoundedRect(QRectF(self.btn_skip_ad_rect.left() + 19.0, ctrl_y + 7.5, 2.0, 11.0), 1.0, 1.0)
                    painter.setPen(skip_text_color)
                    painter.setFont(_font("Segoe UI", 7.8, QFont.Weight.Bold))
                    painter.drawText(QRectF(self.btn_skip_ad_rect.left() + 24.0, ctrl_y, skip_width - 28.0, 26.0), Qt.AlignmentFlag.AlignCenter, "Skip iklan")
                else:
                    self.btn_skip_ad_rect = QRectF()
                    play_cx = dots_center_x
                    self.btn_play_rect = QRectF(play_cx - 14.0, cy_row - 14.0, 28.0, 28.0)
                    prev_w = 26.0
                    next_w = 26.0
                    ctrl_gap = 8.0
                    self.btn_prev_rect = QRectF(self.btn_play_rect.left() - ctrl_gap - prev_w, ctrl_y, prev_w, 26.0)
                    self.btn_next_rect = QRectF(self.btn_play_rect.right() + ctrl_gap, ctrl_y, next_w, 26.0)
                    prev_cx = self.btn_prev_rect.center().x()
                    next_cx = self.btn_next_rect.center().x()

                    # Prev Vector
                    prev_t = self.btn_hover_anim.get("prev", 0.0)
                    prev_col = _interpolate_color(QColor("#CBD5E1"), QColor("#FFFFFF"), prev_t) if self.can_previous else QColor(148, 163, 184, 70)
                    self._draw_vector_prev(painter, prev_cx, cy_row, prev_col)

                    # Play / Pause Hero White Circle
                    play_t = self.btn_hover_anim.get("play", 0.0)
                    painter.setBrush(QBrush(_interpolate_color(QColor("#F8FAFC"), QColor("#FFFFFF"), play_t)))
                    painter.setPen(QPen(QColor(255, 255, 255, 70), 0.8))
                    painter.drawEllipse(self.btn_play_rect)
                    self._draw_vector_play_pause(painter, play_cx, cy_row, self.is_playing, QColor("#0F172A"))

                    # Next Vector
                    next_t = self.btn_hover_anim.get("next", 0.0)
                    next_col = _interpolate_color(QColor("#CBD5E1"), QColor("#FFFFFF"), next_t) if self.can_next else QColor(148, 163, 184, 70)
                    self._draw_vector_next(painter, next_cx, cy_row, next_col)

            # =========================================================================
            # CASE C: LYRICS SIDE DRAWER (SMOOTH SLIDE & FADE DRIVEN BY lp)
            # =========================================================================
            if lp > 0.005:
                painter.save()
                painter.setOpacity(painter.opacity() * lp)
                divider_x = media_left + media_w_area + 14.0
                div_grad = QLinearGradient(divider_x, 34.0, divider_x, h - 18.0)
                div_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
                div_grad.setColorAt(0.5, QColor(255, 255, 255, int(22 * lp)))
                div_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setPen(QPen(QBrush(div_grad), 1.0))
                painter.drawLine(QPointF(divider_x, 34.0), QPointF(divider_x, h - 18.0))

                lyr_x = divider_x + 16.0
                lyr_w = max(0.0, (x + w) - lyr_x - margin)
                self._paint_side_lyrics_panel(painter, QRectF(lyr_x, 0.0, lyr_w, h))
                painter.restore()

            painter.restore()  # Restores Page 0 slide & fade transform
            indicator_y = max(30.0, h - 14.0)
            # Smoothly follow the center of the media controls throughout side drawer animation (smoothly driven by lp)
            self._paint_page_navigation(painter, indicator_y, dots_center_x)

            if not self.settings_open:
                if self.chevron_prev_opacity > 0.005:
                    self._draw_tab_nav_button(painter, self.btn_tab_previous_rect, forward=False, opacity=self.chevron_prev_opacity)
                if self.chevron_next_opacity > 0.005:
                    self._draw_tab_nav_button(painter, self.btn_tab_next_rect, forward=True, opacity=self.chevron_next_opacity)

            painter.restore()

        # Living Scaling Clock (Apple Standard: mathematically locked center with zero jitter)
        if not self.settings_open and shrink_fade > 0.005:
            painter.save()
            painter.setOpacity(shrink_fade)
            media_center_x = self.canvas_w / 2.0
            self._paint_scaling_clock(painter, media_center_x)
            painter.restore()

        self._paint_view_transition(painter)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        island = DesktopDynamicIsland()
        app.aboutToQuit.connect(island.cleanup)
        app.aboutToQuit.connect(island.media_controller.stop)
        app.aboutToQuit.connect(island.stop_lyrics_fetchers)
        app.aboutToQuit.connect(island.youtube_bridge.stop)
        island.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
