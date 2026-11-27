import traceback

try:
    from app_main import ScreenAssistantApp
    ScreenAssistantApp().run()
except Exception:
    err = traceback.format_exc()
    from kivy.app import App
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    class ErrApp(App):
        def build(self):
            lbl = Label(text=err[-2500:], size_hint_y=None, halign="left", valign="top")
            lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
            lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
            sv = ScrollView()
            sv.add_widget(lbl)
            return sv

    ErrApp().run()
