try:
    from . import uikit  # noqa: F401  (drop-downs that fit their choices, for every window)
except ImportError:      # no tkinter: the editor can't open, but its pure parts (event_code) still import
    pass
