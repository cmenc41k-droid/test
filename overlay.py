"""Плавающее окно поверх приложений (WindowManager через PyJNIus)."""
import os
import threading
import time
import traceback

from android.runnable import run_on_ui_thread
from jnius import PythonJavaClass, autoclass, cast, java_method

import gemini
import screen_capture
import settings

PythonActivity = autoclass("org.kivy.android.PythonActivity")
Context = autoclass("android.content.Context")
Build = autoclass("android.os.Build$VERSION")
LP = autoclass("android.view.WindowManager$LayoutParams")
LinearLayout = autoclass("android.widget.LinearLayout")
LLP = autoclass("android.widget.LinearLayout$LayoutParams")
ScrollView = autoclass("android.widget.ScrollView")
TextView = autoclass("android.widget.TextView")
GradientDrawable = autoclass("android.graphics.drawable.GradientDrawable")
Color = autoclass("android.graphics.Color")
PixelFormat = autoclass("android.graphics.PixelFormat")
ClipData = autoclass("android.content.ClipData")
Gravity = autoclass("android.view.Gravity")

DOWN, UP, MOVE, CANCEL = 0, 1, 2, 3
INVISIBLE, VISIBLE = 4, 0


class _Touch(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnTouchListener"]
    __javacontext__ = "app"

    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
    def onTouch(self, v, e):
        try:
            return bool(self.cb(e))
        except Exception:
            traceback.print_exc()
            return False


class _Click(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnClickListener"]
    __javacontext__ = "app"

    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    @java_method("(Landroid/view/View;)V")
    def onClick(self, v):
        try:
            self.cb()
        except Exception:
            traceback.print_exc()


class Overlay:
    def __init__(self, get_api_key, get_prompt, on_close):
        self.get_api_key, self.get_prompt, self.on_close = get_api_key, get_prompt, on_close
        self.ctx = PythonActivity.mActivity.getApplicationContext()
        self.wm = cast("android.view.WindowManager", self.ctx.getSystemService(Context.WINDOW_SERVICE))
        self.density = self.ctx.getResources().getDisplayMetrics().density
        self.shots = []
        self.busy = False
        self.shown = False
        self.minimized = False
        self._keep = []  # ссылки на слушатели, чтобы их не удалил GC
        self.root = self.dot = None
        self._drag = None

    def dp(self, v):
        return int(v * self.density)

    def _screen(self):
        dm = self.ctx.getResources().getDisplayMetrics()
        return dm.widthPixels, dm.heightPixels

    # ---------- построение ----------
    def _bg(self, color, radius, shape=0):
        g = GradientDrawable()
        g.setShape(shape)
        g.setColor(color)
        g.setCornerRadius(float(self.dp(radius)))
        return g

    def _tv(self, text, size=14, color=None, bold=False):
        t = TextView(self.ctx)
        t.setText(text)
        t.setTextSize(float(size))
        t.setTextColor(color if color is not None else Color.WHITE)
        return t

    def _btn(self, text, color, click):
        t = self._tv(text, 14, bold=True)
        t.setGravity(Gravity.CENTER)
        t.setBackground(self._bg(color, 8))
        p = self.dp(10)
        t.setPadding(p, p, p, p)
        c = _Click(click)
        self._keep.append(c)
        t.setOnClickListener(c)
        return t

    def _touch(self, view, cb):
        t = _Touch(cb)
        self._keep.append(t)
        view.setOnTouchListener(t)

    def _wlp(self, w, h, x, y):
        typ = LP.TYPE_APPLICATION_OVERLAY if Build.SDK_INT >= 26 else LP.TYPE_PHONE
        lp = LP(w, h, typ, LP.FLAG_NOT_FOCUSABLE | LP.FLAG_NOT_TOUCH_MODAL, PixelFormat.TRANSLUCENT)
        lp.gravity = Gravity.TOP | Gravity.LEFT
        lp.x, lp.y = int(x), int(y)
        return lp

    @run_on_ui_thread
    def start(self):
        if self.shown:
            return
        sw, sh = self._screen()
        g = settings.get_geometry() or {}
        w = min(g.get("w", self.dp(320)), sw)
        h = min(g.get("h", self.dp(440)), sh)
        x = max(0, min(g.get("x", self.dp(30)), sw - self.dp(60)))
        y = max(0, min(g.get("y", self.dp(120)), sh - self.dp(60)))
        self.lp = self._wlp(w, h, x, y)

        # корневая панель
        root = LinearLayout(self.ctx)
        root.setOrientation(1)
        root.setBackground(self._bg(Color.argb(240, 24, 26, 34), 12))
        pad = self.dp(8)
        root.setPadding(pad, pad, pad, pad)

        # заголовок (перетаскивание)
        bar = LinearLayout(self.ctx)
        bar.setOrientation(0)
        bar.setGravity(Gravity.CENTER_VERTICAL)
        title = self._tv("Screen Assistant", 15, bold=True)
        bar.addView(title, LLP(0, self.dp(36), 1.0))
        for label, cb in (("−", self.minimize), ("X", self.close)):
            b = self._tv(label, 20, bold=True)
            b.setGravity(Gravity.CENTER)
            c = _Click(cb)
            self._keep.append(c)
            b.setOnClickListener(c)
            bar.addView(b, LLP(self.dp(40), self.dp(36)))
        self._touch(bar, self._on_title_touch)
        root.addView(bar, LLP(-1, -2))

        # ответ
        self.answer = self._tv("Ответ Gemini появится здесь.", 14)
        self.answer.setTextIsSelectable(True)
        q = self.dp(8)
        self.answer.setPadding(q, q, q, q)
        sv = ScrollView(self.ctx)
        sv.setBackground(self._bg(Color.argb(255, 12, 13, 18), 8))
        sv.addView(self.answer)
        lp_sv = LLP(-1, 0, 1.0)
        lp_sv.setMargins(0, q, 0, q)
        root.addView(sv, lp_sv)

        # кнопки
        row = LinearLayout(self.ctx)
        row.setOrientation(0)
        b1 = self._btn("Сфотографировать", Color.rgb(46, 110, 220), self._on_capture)
        b2 = self._btn("Отправить", Color.rgb(36, 150, 90), self._on_send)
        self.btn_capture, self.btn_send = b1, b2
        l1 = LLP(0, -2, 1.0); l1.setMargins(0, 0, q // 2, 0)
        l2 = LLP(0, -2, 1.0); l2.setMargins(q // 2, 0, 0, 0)
        row.addView(b1, l1)
        row.addView(b2, l2)
        root.addView(row, LLP(-1, -2))

        # нижняя строка
        foot = LinearLayout(self.ctx)
        foot.setOrientation(0)
        foot.setGravity(Gravity.CENTER_VERTICAL)
        self.counter = self._tv("Снимков: 0", 13, Color.rgb(190, 195, 210))
        foot.addView(self.counter, LLP(0, -2, 1.0))
        copy = self._tv("Копировать", 13, Color.rgb(120, 170, 255))
        copy.setPadding(q, q, q, q)
        c = _Click(self._on_copy)
        self._keep.append(c)
        copy.setOnClickListener(c)
        foot.addView(copy, LLP(-2, -2))
        handle = self._tv("◢", 22, Color.rgb(200, 200, 210))
        handle.setGravity(Gravity.CENTER)
        self._touch(handle, self._on_resize_touch)
        foot.addView(handle, LLP(self.dp(40), self.dp(36)))
        root.addView(foot, LLP(-1, -2))

        self.root = root
        self.wm.addView(root, self.lp)
        self.shown, self.minimized = True, False

        # точка (в свёрнутом режиме)
        d = self.dp(44)
        dot = self._tv("", 10)
        dot.setBackground(self._bg(Color.argb(150, 70, 130, 255), 22, shape=1))
        dp_pos = settings.get_dot_position() or {"x": x, "y": y}
        self.dot_lp = self._wlp(d, d, dp_pos["x"], dp_pos["y"])
        self._touch(dot, self._on_dot_touch)
        self.dot = dot
        self._update_counter()

    # ---------- перетаскивание ----------
    def _save_geo(self):
        try:
            settings.save_geometry(self.lp.x, self.lp.y, self.lp.width, self.lp.height)
        except Exception:
            traceback.print_exc()

    def _on_title_touch(self, e):
        a = e.getActionMasked()
        if a == DOWN:
            self._drag = (e.getRawX(), e.getRawY(), self.lp.x, self.lp.y)
        elif a == MOVE and self._drag:
            self.lp.x = int(self._drag[2] + e.getRawX() - self._drag[0])
            self.lp.y = int(self._drag[3] + e.getRawY() - self._drag[1])
            self.wm.updateViewLayout(self.root, self.lp)
        elif a in (UP, CANCEL):
            self._save_geo()
        return True

    def _on_resize_touch(self, e):
        a = e.getActionMasked()
        if a == DOWN:
            self._drag = (e.getRawX(), e.getRawY(), self.lp.width, self.lp.height)
        elif a == MOVE and self._drag:
            sw, sh = self._screen()
            self.lp.width = int(max(self.dp(220), min(sw, self._drag[2] + e.getRawX() - self._drag[0])))
            self.lp.height = int(max(self.dp(260), min(sh, self._drag[3] + e.getRawY() - self._drag[1])))
            self.wm.updateViewLayout(self.root, self.lp)
        elif a in (UP, CANCEL):
            self._save_geo()
        return True

    def _on_dot_touch(self, e):
        a = e.getActionMasked()
        if a == DOWN:
            self._drag = (e.getRawX(), e.getRawY(), self.dot_lp.x, self.dot_lp.y, False)
        elif a == MOVE and self._drag:
            dx, dy = e.getRawX() - self._drag[0], e.getRawY() - self._drag[1]
            moved = self._drag[4] or abs(dx) > self.dp(8) or abs(dy) > self.dp(8)
            self._drag = self._drag[:4] + (moved,)
            if moved:
                self.dot_lp.x, self.dot_lp.y = int(self._drag[2] + dx), int(self._drag[3] + dy)
                self.wm.updateViewLayout(self.dot, self.dot_lp)
        elif a == UP and self._drag:
            if not self._drag[4]:
                self.expand()
            else:
                settings.save_dot_position(self.dot_lp.x, self.dot_lp.y)
        return True

    # ---------- свернуть / развернуть / закрыть ----------
    def minimize(self):
        if self.minimized or not self.shown:
            return
        self.wm.removeView(self.root)
        self.dot_lp.x, self.dot_lp.y = self.lp.x, self.lp.y
        self.wm.addView(self.dot, self.dot_lp)
        self.minimized = True

    def expand(self):
        if not self.minimized:
            return
        self.wm.removeView(self.dot)
        self.lp.x, self.lp.y = self.dot_lp.x, self.dot_lp.y
        self.wm.addView(self.root, self.lp)
        self.minimized = False
        self._save_geo()

    def close(self):
        if not self.shown:
            return
        try:
            self.wm.removeView(self.dot if self.minimized else self.root)
        except Exception:
            traceback.print_exc()
        self.shown = False
        for p in self.shots:
            self._rm(p)
        self.shots = []
        try:
            screen_capture.stop()
        finally:
            self.on_close()

    @staticmethod
    def _rm(p):
        try:
            os.remove(p)
        except OSError:
            pass

    # ---------- UI-хелперы (безопасно вызывать из любого потока) ----------
    @run_on_ui_thread
    def _ui_answer(self, text):
        self.answer.setText(text)

    @run_on_ui_thread
    def _ui_visible(self, visible):
        if self.root is not None and not self.minimized:
            self.root.setVisibility(VISIBLE if visible else INVISIBLE)

    @run_on_ui_thread
    def _ui_busy(self, busy):
        self.busy = busy
        self.btn_capture.setEnabled(not busy)
        self.btn_send.setEnabled(not busy)

    @run_on_ui_thread
    def _update_counter(self, extra=""):
        self.counter.setText("Снимков: %d%s" % (len(self.shots), extra))

    # ---------- действия ----------
    def _on_copy(self):
        cm = cast("android.content.ClipboardManager", self.ctx.getSystemService(Context.CLIPBOARD_SERVICE))
        cm.setPrimaryClip(ClipData.newPlainText("Screen Assistant", self.answer.getText().toString()))
        self._update_counter("  ·  скопировано")

    def _on_capture(self):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._capture_worker, daemon=True).start()

    def _capture_worker(self):
        self._ui_busy(True)
        ok, err = False, ""
        path = os.path.join(str(PythonActivity.mActivity.getCacheDir().getAbsolutePath()),
                            "shot_%d.jpg" % int(time.time() * 1000))
        try:
            self._ui_visible(False)  # прячем панель, чтобы она не попала на снимок
            time.sleep(0.35)
            ok = screen_capture.capture(path)
        except Exception as ex:
            err = str(ex)
        finally:
            self._ui_visible(True)
        if ok:
            self.shots.append(path)
            self._update_counter()
        else:
            self._update_counter("  ·  не удалось снять")
            self._ui_answer("Не удалось получить снимок экрана. %s\nПроверьте, что захват экрана "
                            "не остановлен (X закрывает режим), и повторите." % err)
        self._ui_busy(False)

    def _on_send(self):
        if self.busy:
            return
        if not self.shots:
            self._ui_answer("Сначала сделайте хотя бы один снимок («Сфотографировать»).")
            return
        self.busy = True
        threading.Thread(target=self._send_worker, daemon=True).start()

    def _send_worker(self):
        self._ui_busy(True)
        self._ui_answer("Отправляю %d снимк(ов) в Gemini…" % len(self.shots))
        batch = list(self.shots)
        try:
            text = gemini.generate(self.get_api_key(), self.get_prompt(), batch)
        except gemini.GeminiError as e:
            self._ui_answer("Ошибка: %s\n\nСнимки сохранены, можно нажать «Отправить» ещё раз." % e)
        except Exception as e:
            traceback.print_exc()
            self._ui_answer("Непредвиденная ошибка: %s" % e)
        else:
            self._ui_answer(text)
            self.shots = [p for p in self.shots if p not in batch]
            for p in batch:
                self._rm(p)
            self._update_counter()
        self._ui_busy(False)
