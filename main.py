"""Screen Assistant: точка входа. Стартовый экран -> проверки -> разрешения -> плавающее окно."""
import threading

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.utils import platform

import gemini
import settings
from interface import SettingsScreen

Window.softinput_mode = "below_target"


class ScreenAssistantApp(App):
    title = "Screen Assistant"

    def build(self):
        self.ui = SettingsScreen(on_start=self.on_start_pressed)
        s = settings.load()
        self.ui.load(s["api_key"], s["prompt"])
        self._waiting_overlay_perm = False
        self._notif_asked = False
        self._overlay = None
        return self.ui

    def on_pause(self):
        return True  # приложение должно жить в фоне, пока работает плавающее окно

    def on_resume(self):
        if self._waiting_overlay_perm:
            self._waiting_overlay_perm = False
            Clock.schedule_once(lambda dt: self.continue_start(), 0.4)

    # ---------- шаг 1: проверки ----------
    def on_start_pressed(self, api_key, prompt):
        err = settings.validate(api_key, prompt)
        if err:
            self.ui.set_status(err, error=True)
            return
        self.ui.set_busy(True)
        self.ui.set_status("Проверяю Gemini API и ключ…")
        threading.Thread(target=self._check_worker, args=(api_key, prompt), daemon=True).start()

    def _check_worker(self, api_key, prompt):
        try:
            model = gemini.check_api_key(api_key)
            settings.save(api_key, prompt)
        except gemini.GeminiError as e:
            self._check_done(False, str(e))
        except Exception as e:  # noqa
            self._check_done(False, "Ошибка: %s" % e)
        else:
            self._check_done(True, "Ключ принят. Модель: %s" % model)

    @mainthread
    def _check_done(self, ok, msg):
        self.ui.set_busy(False)
        self.ui.set_status(msg, error=not ok)
        if ok:
            self.continue_start()

    # ---------- шаг 2: разрешения ----------
    def continue_start(self):
        if platform != "android":
            self.ui.set_status("Плавающий режим работает только на Android.", error=True)
            return
        from jnius import autoclass
        PA = autoclass("org.kivy.android.PythonActivity")
        Settings = autoclass("android.provider.Settings")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Build = autoclass("android.os.Build$VERSION")
        act = PA.mActivity

        if not Settings.canDrawOverlays(act):
            self._waiting_overlay_perm = True
            self.ui.set_status("Разрешите «Поверх других приложений» и вернитесь в Screen Assistant.", error=True)
            i = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                       Uri.parse("package:" + act.getPackageName()))
            act.startActivity(i)
            return

        if Build.SDK_INT >= 33 and not self._notif_asked:
            self._notif_asked = True
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"],
                                lambda p, g: Clock.schedule_once(lambda dt: self.continue_start(), 0))
            return

        import screen_capture
        if screen_capture.state() != screen_capture.READY:
            self.ui.set_status("Подтвердите захват экрана в системном диалоге.")
            screen_capture.request_permission()
            self._poll_left = 180  # 90 секунд
            Clock.schedule_interval(self._poll_capture, 0.5)
            return
        self._launch_overlay()

    def _poll_capture(self, dt):
        import screen_capture
        st = screen_capture.state()
        self._poll_left -= 1
        if st == screen_capture.READY:
            self._launch_overlay()
            return False
        if st == screen_capture.DENIED:
            self.ui.set_status("Доступ к захвату экрана не выдан.", error=True)
            return False
        if self._poll_left <= 0:
            self.ui.set_status("Время ожидания разрешения истекло. Нажмите «Начать» снова.", error=True)
            return False
        return True

    # ---------- шаг 3: плавающее окно ----------
    def _launch_overlay(self):
        from jnius import autoclass
        import overlay
        if self._overlay is None:
            self._overlay = overlay.Overlay(settings.get_api_key, settings.get_prompt, self._overlay_closed)
        self._overlay.start()
        self.ui.set_status("Плавающий режим запущен.")
        autoclass("org.kivy.android.PythonActivity").mActivity.moveTaskToBack(True)

    @mainthread
    def _overlay_closed(self):
        self._overlay = None
        self.ui.set_status("Плавающий режим закрыт, захват экрана остановлен.")


if __name__ == "__main__":
    ScreenAssistantApp().run()
