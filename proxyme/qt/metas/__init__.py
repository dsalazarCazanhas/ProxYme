from pathlib import Path

_metas_dir = Path(__file__).resolve().parent

icon = {
    'window_icon':     str(_metas_dir / 'window_icon.png'),
    'icon_eye_closed':  str(_metas_dir / 'close_eye.png'),
    'icon_eye_opened':  str(_metas_dir / 'open_eye.png'),
}
