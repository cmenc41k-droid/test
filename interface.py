"""Стартовый экран настроек (Kivy)."""
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput


class SettingsScreen(BoxLayout):
    def __init__(self, on_start, **kw):
        super().__init__(orientation="vertical", padding=dp(16), spacing=dp(10), **kw)
        self._on_start = on_start

        self.add_widget(Label(text="Screen Assistant", font_size=sp(28), bold=True,
                              size_hint_y=None, height=dp(56)))

        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.key_input = TextInput(hint_text="Gemini API Key", password=True, multiline=False,
                                   write_tab=False, font_size=sp(16))
        self.toggle = Button(text="Показать", size_hint_x=None, width=dp(110))
        self.toggle.bind(on_release=self._toggle_key)
        row.add_widget(self.key_input)
        row.add_widget(self.toggle)
        self.add_widget(row)

        self.add_widget(Label(text="Ваш промпт для Gemini:", size_hint_y=None, height=dp(28),
                              halign="left", text_size=(dp(300), None)))
        self.prompt_input = TextInput(hint_text="Например: реши задачу со скриншота и объясни кратко",
                                      font_size=sp(16))
        self.add_widget(self.prompt_input)

        self.status = Label(text="", size_hint_y=None, height=dp(72), color=(1, .6, .4, 1))
        self.status.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        self.add_widget(self.status)

        self.start_btn = Button(text="Начать", size_hint_y=None, height=dp(60), font_size=sp(20))
        self.start_btn.bind(on_release=self._start)
        self.add_widget(self.start_btn)

    def _toggle_key(self, *_):
        self.key_input.password = not self.key_input.password
        self.toggle.text = "Скрыть" if not self.key_input.password else "Показать"

    def _start(self, *_):
        self._on_start(self.key_input.text.strip(), self.prompt_input.text.strip())

    def load(self, api_key, prompt):
        self.key_input.text = api_key
        self.prompt_input.text = prompt

    def set_status(self, text, error=False):
        self.status.color = (1, .55, .45, 1) if error else (.6, .9, .6, 1)
        self.status.text = text

    def set_busy(self, busy):
        self.start_btn.disabled = busy
