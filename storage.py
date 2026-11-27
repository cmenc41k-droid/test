"""Хранилище: JSON-файл в приватной папке приложения; API Key шифруется Android Keystore."""
import base64
import json
import os

from kivy.utils import platform

SECURE = None
if platform == "android":
    from jnius import autoclass
    SECURE = autoclass("org.screenassistant.nativeparts.SecureStore")


def _dir():
    if platform == "android":
        from android.storage import app_storage_path
        return app_storage_path()
    return os.path.join(os.path.expanduser("~"), ".screen_assistant")


def _path():
    d = _dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")


def load_all():
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_all(data):
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, _path())


def encrypt_secret(text):
    if not text:
        return ""
    if SECURE is not None:
        enc = SECURE.encrypt(text)
        if enc is None:
            raise RuntimeError("Не удалось зашифровать API Key (Android Keystore).")
        return "ks:" + str(enc)
    # Только для запуска на ПК при разработке (НЕ шифрование!)
    return "dev:" + base64.b64encode(text.encode("utf-8")).decode("ascii")


def decrypt_secret(blob):
    if not blob:
        return ""
    try:
        if blob.startswith("ks:") and SECURE is not None:
            dec = SECURE.decrypt(blob[3:])
            return str(dec) if dec is not None else ""
        if blob.startswith("dev:"):
            return base64.b64decode(blob[4:]).decode("utf-8")
    except Exception:
        pass
    return ""
