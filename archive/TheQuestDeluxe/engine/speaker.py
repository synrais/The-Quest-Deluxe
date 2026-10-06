"""The PC speaker: Borland's sound(freq) / nosound(), as a square wave through pygame.mixer.

The original's asound() plays a tone only when sound.txt holds 1 (the manual: "1=sound, 0=no
sound"). The Quest Deluxe reads sound.txt from its folder, else from the quest pack (as sound.txt); with
neither, the sound is on.
"""
from __future__ import annotations

import array
import os

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the TheQuestDeluxe folder

RATE = 22050
VOLUME = 0.12


def sound_setting(source=None) -> bool:
    path = os.path.join(ROOT, 'sound.txt')
    try:
        if os.path.exists(path):
            with open(path, 'rb') as fh:
                raw = fh.read()
        elif source is not None:
            raw = source.read('sound.txt')
        else:
            return True
        return raw.split()[0] == b'1' if raw.split() else False
    except (OSError, FileNotFoundError):
        return True


class Speaker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.channel = None
        self.freq = 0
        self._cache: dict[int, pygame.mixer.Sound] = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=RATE, size=-16, channels=1)
            self.rate, _, self.chans = pygame.mixer.get_init()
            self.channel = pygame.mixer.Channel(0)
        except pygame.error:
            self.enabled = False

    def _wave(self, freq: int) -> pygame.mixer.Sound:
        snd = self._cache.get(freq)
        if snd is None:
            cycles = max(1, round(freq * 0.1))               # ~0.1 s of whole cycles, looped
            n = max(2, round(cycles * self.rate / freq))
            amp = int(32767 * VOLUME)
            samples = array.array('h')
            for k in range(n):
                v = amp if (k * cycles * 2 // n) % 2 == 0 else -amp
                samples.extend([v] * self.chans)
            snd = pygame.mixer.Sound(buffer=samples.tobytes())
            self._cache[freq] = snd
        return snd

    def sound(self, freq: int):
        if not self.enabled or freq == self.freq:
            return
        freq &= 0xFFFF
        self.freq = freq
        if 20 <= freq <= 20000:
            self.channel.play(self._wave(freq), loops=-1)
        else:
            self.channel.stop()

    def nosound(self):
        if self.enabled and self.freq:
            self.channel.stop()
        self.freq = 0
