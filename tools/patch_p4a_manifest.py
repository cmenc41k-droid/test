"""Вставляет android/manifest_extra.xml в шаблоны AndroidManifest python-for-android."""
import glob, os, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
extra = open(os.path.join(root, "android", "manifest_extra.xml"), encoding="utf-8").read()
marker = "SCREEN_ASSISTANT_EXTRA"
files = glob.glob(os.path.join(root, "p4a_src", "pythonforandroid", "bootstraps", "**",
                               "AndroidManifest.tmpl.xml"), recursive=True)
if not files:
    sys.exit("ERROR: AndroidManifest.tmpl.xml не найден в p4a_src")
for f in files:
    s = open(f, encoding="utf-8").read()
    if marker in s:
        print("already patched:", f); continue
    if "</application>" not in s:
        sys.exit("ERROR: нет </application> в " + f)
    s = s.replace("</application>", extra + "\n</application>", 1)
    open(f, "w", encoding="utf-8").write(s)
    print("patched:", f)
