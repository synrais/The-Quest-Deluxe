"""Keys: pygame's names, X's names (for xdotool), and which ones the original understands."""
from __future__ import annotations

SPECIAL = {  # X name -> pygame constant name
    'Up': 'K_UP', 'Down': 'K_DOWN', 'Left': 'K_LEFT', 'Right': 'K_RIGHT', 'Return': 'K_RETURN', 'Escape': 'K_ESCAPE', 'space': 'K_SPACE',
    'Tab': 'K_TAB', 'BackSpace': 'K_BACKSPACE', 'Home': 'K_HOME', 'End': 'K_END', 'Insert': 'K_INSERT', 'Delete': 'K_DELETE',
    'Prior': 'K_PAGEUP', 'Next': 'K_PAGEDOWN', 'plus': 'K_PLUS', 'minus': 'K_MINUS',
}
SPECIAL.update({f'F{i}': f'K_F{i}' for i in range(1, 13)})
# keys of The Quest Deluxe that the original has no meaning for: they are not sent to it (and not to ours either, so the two stay alike)
DELUXE_ONLY = {'f', 'd', 'm', 'F10', 'F11', 'F12'}


def to_pygame(name: str):
    """(pygame key, unicode) for an X key name."""
    import pygame
    if name in SPECIAL:
        return getattr(pygame, SPECIAL[name]), ('\r' if name == 'Return' else ' ' if name == 'space' else '')
    if len(name) == 1:
        return getattr(pygame, f'K_{name.lower()}'), name
    raise KeyError(name)


def from_pygame(key: int):
    """The X key name for a pygame key, or None if it has none we send."""
    import pygame
    for x, p in SPECIAL.items():
        if getattr(pygame, p, None) == key:
            return x
    name = pygame.key.name(key)
    if len(name) == 1 and (name.isalnum()):
        return name
    return None


def sendable(name: str | None) -> bool:
    return bool(name) and name not in DELUXE_ONLY
