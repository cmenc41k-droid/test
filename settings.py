"""Настройки приложения: ключ, промпт, геометрия окна."""
import storage

DEFAULT_PROMPT = ("Проанализируй приложенные скриншоты и кратко, по делу ответь "
                  "на вопрос или выполни задачу, которая на них изображена.")


def load():
    d = storage.load_all()
    return {
        "api_key": storage.decrypt_secret(d.get("api_key", "")),
        "prompt": d.get("prompt", ""),
    }


def save(api_key, prompt):
    d = storage.load_all()
    d["api_key"] = storage.encrypt_secret(api_key)
    d["prompt"] = prompt
    storage.save_all(d)


def get_prompt():
    return load()["prompt"].strip() or DEFAULT_PROMPT


def get_api_key():
    return load()["api_key"]


def validate(api_key, prompt):
    """Возвращает текст ошибки или None."""
    if not api_key.strip():
        return "Введите Gemini API Key."
    if not prompt.strip():
        return "Введите свой промпт."
    return None


def get_geometry():
    return storage.load_all().get("geometry")  # dict x,y,w,h или None


def save_geometry(x, y, w, h):
    d = storage.load_all()
    d["geometry"] = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    storage.save_all(d)


def get_dot_position():
    return storage.load_all().get("dot")


def save_dot_position(x, y):
    d = storage.load_all()
    d["dot"] = {"x": int(x), "y": int(y)}
    storage.save_all(d)
