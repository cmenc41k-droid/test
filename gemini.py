"""Клиент Google Gemini (REST, только стандартная библиотека + certifi)."""
import base64
import json
import os
import socket
import ssl
import urllib.error
import urllib.request

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _CTX = ssl.create_default_context()

BASE = "https://generativelanguage.googleapis.com/v1beta"
# Алиас «последняя Flash-модель» (мультимодальная). Можно переопределить переменной окружения.
PREFERRED_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
MAX_TOTAL_BYTES = 18 * 1024 * 1024
_model_cache = {}


class GeminiError(Exception):
    """Ошибка с понятным пользователю текстом."""


def _request(method, url, api_key, body=None, timeout=90):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "x-goog-api-key": api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise GeminiError(_http_message(e)) from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise GeminiError("Превышено время ожидания ответа Gemini.") from None
        raise GeminiError("Нет соединения с интернетом или Gemini API недоступен.") from None
    except (socket.timeout, TimeoutError):
        raise GeminiError("Превышено время ожидания ответа Gemini.") from None
    except json.JSONDecodeError:
        raise GeminiError("Gemini вернул некорректный ответ.") from None


def _http_message(e):
    try:
        msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
    except Exception:
        msg = ""
    low = msg.lower()
    if e.code in (400, 401, 403) and ("api key" in low or "api_key" in low or e.code in (401, 403)):
        return "API Key неверный или не имеет доступа к Gemini API. " + msg[:160]
    if e.code == 429:
        return "Превышен лимит запросов Gemini API (429). Подождите и повторите."
    if e.code == 404:
        return "Модель Gemini не найдена (404). " + msg[:160]
    if e.code >= 500:
        return "Сервер Gemini временно недоступен (%d). Повторите позже." % e.code
    return "Ошибка Gemini API (%d): %s" % (e.code, msg[:240])


def resolve_model(api_key):
    """Подбирает доступную мультимодальную модель; результат кэшируется."""
    if api_key in _model_cache:
        return _model_cache[api_key]
    res = _request("GET", BASE + "/models?pageSize=200", api_key, timeout=30)
    ok = []
    for m in res.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            ok.append(m.get("name", "").replace("models/", ""))
    if PREFERRED_MODEL in ok:
        chosen = PREFERRED_MODEL
    else:
        flash = sorted(n for n in ok if "flash" in n and "gemini" in n
                       and not any(x in n for x in ("lite", "image", "tts", "live", "thinking")))
        any_g = [n for n in ok if n.startswith("gemini")]
        pool = flash or any_g
        if not pool:
            raise GeminiError("Для этого ключа нет доступных моделей Gemini.")
        chosen = pool[-1]
    _model_cache[api_key] = chosen
    return chosen


def check_api_key(api_key):
    """Проверяет доступность API и ключ. Возвращает имя модели или бросает GeminiError."""
    return resolve_model(api_key.strip())


def generate(api_key, prompt, image_paths, timeout=120):
    """Отправляет все изображения и промпт ОДНИМ запросом. Возвращает текст ответа."""
    api_key = api_key.strip()
    if not api_key:
        raise GeminiError("API Key не задан.")
    if not image_paths:
        raise GeminiError("Нет изображений для отправки.")
    parts, total = [], 0
    for p in image_paths:
        with open(p, "rb") as f:
            raw = f.read()
        total += len(raw)
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(raw).decode("ascii")}})
    if total > MAX_TOTAL_BYTES:
        raise GeminiError("Снимки слишком большие для одного запроса (%.1f МБ). "
                          "Отправьте меньше снимков." % (total / 1048576))
    parts.append({"text": prompt})
    model = resolve_model(api_key)
    res = _request("POST", "%s/models/%s:generateContent" % (BASE, model), api_key,
                   {"contents": [{"role": "user", "parts": parts}]}, timeout=timeout)
    block = res.get("promptFeedback", {}).get("blockReason")
    if block:
        raise GeminiError("Запрос заблокирован Gemini: " + block)
    cands = res.get("candidates") or []
    if not cands:
        raise GeminiError("Gemini не вернул ответ.")
    text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
    if not text.strip():
        raise GeminiError("Пустой ответ Gemini (finishReason: %s)." % cands[0].get("finishReason", "?"))
    return text.strip()
