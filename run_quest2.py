"""The Quest II — launcher.

    python run_quest2.py            start a new game
    python run_quest2.py --level 3  start directly on level 3 (testing)
"""
import argparse

import pygame

from quest2.game import Game


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--scale', type=int, default=2)
    args = ap.parse_args()
    pygame.init()
    pygame.display.set_caption('The Quest II')
    window = pygame.display.set_mode((640 * args.scale, 480 * args.scale), pygame.RESIZABLE)
    Game(window, start_level=args.level).run()
    pygame.quit()


if __name__ == '__main__':
    main()
