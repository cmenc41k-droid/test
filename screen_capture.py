"""Обёртка над нативным CaptureService (MediaProjection) через PyJNIus."""
from jnius import autoclass

IDLE, PENDING, READY, DENIED = 0, 1, 2, 3
_Service = autoclass("org.screenassistant.nativeparts.CaptureService")
_PythonActivity = autoclass("org.kivy.android.PythonActivity")
_Intent = autoclass("android.content.Intent")
PKG_ACTIVITY = "org.screenassistant.nativeparts.CapturePermissionActivity"


def state():
    return int(_Service.getState())


def request_permission():
    """Показывает системный диалог MediaProjection (через прозрачную Activity)."""
    act = _PythonActivity.mActivity
    intent = _Intent()
    intent.setClassName(act.getPackageName(), PKG_ACTIVITY)
    act.startActivity(intent)


def capture(path, timeout_ms=3000):
    """Сохраняет текущий кадр экрана в JPEG. Блокирующий; вызывать из фонового потока."""
    return bool(_Service.capture(path, timeout_ms))


def stop():
    _Service.stopCapture(_PythonActivity.mActivity.getApplicationContext())
