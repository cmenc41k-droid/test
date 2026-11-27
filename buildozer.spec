[app]
title = Screen Assistant
package.name = screenassistant
package.domain = org.screenassistant
source.dir = .
source.include_exts = py,png,jpg,kv,json
source.exclude_dirs = p4a_src,.buildozer,bin,.github,tools,android,.git,__pycache__
version = 1.0.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pyjnius,android,certifi
orientation = portrait
fullscreen = 0

# Android
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION,POST_NOTIFICATIONS
android.add_src = android/src
android.allow_backup = False

# p4a клонируется workflow-ом в ./p4a_src, в манифест вставляется android/manifest_extra.xml
p4a.source_dir = ./p4a_src
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
