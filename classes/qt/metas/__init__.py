import os

metas_dir = os.path.dirname(os.path.realpath(__file__))
icon_window = metas_dir + os.path.sep + 'window_icon.png'
icon_eye_closed = metas_dir + os.path.sep + 'close_eye.png'
icon_eye_opened = metas_dir + os.path.sep + 'open_eye.png'

icon = {'window_icon': icon_window,
        'icon_eye_closed': icon_eye_closed,
        'icon_eye_opened': icon_eye_opened}
