# Screen Assistant (Android, Python + Kivy)

Плавающее окно поверх приложений: делает снимки экрана (MediaProjection), копит их и отправляет одним запросом в Google Gemini вместе с вашим промптом.

> ⚠️ Проект собран и проверен только статически (синтаксис Python, YAML, spec). **На реальном Android-устройстве и в реальной сборке он НЕ запускался.** Первая сборка может потребовать правок — смотрите лог GitHub Actions.

## Структура
| Файл | Назначение |
|---|---|
| `main.py` | вход, поток: настройки → проверка ключа → разрешения → оверлей |
| `interface.py` | стартовый экран Kivy |
| `settings.py`, `storage.py` | сохранение настроек; API Key шифруется AES-GCM в Android Keystore |
| `gemini.py` | запросы к Gemini API (несколько изображений в одном запросе) |
| `overlay.py` | плавающее окно (WindowManager, перетаскивание, ресайз, точка) |
| `screen_capture.py` | обёртка над нативным сервисом захвата |
| `android/src/.../CaptureService.java` | foreground-сервис + MediaProjection + ImageReader |
| `android/src/.../CapturePermissionActivity.java` | системный диалог разрешения захвата |
| `android/src/.../SecureStore.java` | Android Keystore |
| `android/manifest_extra.xml` + `tools/patch_p4a_manifest.py` | добавляют сервис и activity в AndroidManifest |
| `buildozer.spec`, `.github/workflows/build-apk.yml` | сборка |

## Как получить APK через GitHub
1. Создайте на github.com новый репозиторий (например `ScreenAssistant`), ветка по умолчанию — `main`.
2. Распакуйте ZIP. Загрузите **содержимое папки** `ScreenAssistant` в корень репозитория (кнопка *Add file → Upload files*; папку `.github` нужно загрузить тоже — она скрытая, на Windows включите «показывать скрытые файлы», либо используйте `git`):
   ```
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/ВАШ_ЛОГИН/ScreenAssistant.git
   git push -u origin main
   ```
3. Откройте вкладку **Actions** → «Build APK». Сборка стартует сама после push; вручную — *Run workflow*.
4. Первая сборка 25–50 минут (скачивается SDK/NDK). Дальше быстрее благодаря кэшу.
5. После зелёной галочки откройте запуск → раздел **Artifacts** → `ScreenAssistant-debug-apk` → скачайте ZIP, внутри `.apk`.
6. Скопируйте APK на телефон и установите (разрешите установку из неизвестных источников).

## Использование
1. Введите Gemini API Key (получить: aistudio.google.com/apikey) и промпт → «Начать».
2. Выдайте: «Поверх других приложений», уведомления, захват экрана.
3. Приложение уйдёт в фон, появится окно. «Сфотографировать» — добавляет снимок (панель на момент снимка скрывается), «Отправить» — все снимки одним запросом.
4. «−» сворачивает в полупрозрачную точку (тап по ней — вернуть), «X» закрывает режим и останавливает захват.

## Ограничения
* Защищённое содержимое (FLAG_SECURE: банки, DRM-видео) Android отдаёт чёрным кадром — обход не предусмотрен.
* Модель: алиас `gemini-flash-latest`, при его отсутствии выбирается доступная Flash-модель (можно задать переменной `GEMINI_MODEL`).
* Размер экрана фиксируется при старте захвата; при повороте экрана перезапустите режим.
* Сборка только arm64-v8a (подавляющее большинство современных телефонов).
