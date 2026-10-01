"""The Quest Deluxe — launcher.

    python run_deluxe.py                       a new game of packs/TheQuest, from the title
    python run_deluxe.py --pack mypack         play packs/mypack (or any pack folder)
    python run_deluxe.py --level 3             new games start on level 3
    python run_deluxe.py --fixes off           this time, keep the original's bugs (settings.ini says
                                               what to do otherwise: fixes = on, off or pack)
    python run_deluxe.py --sound off           this time, no PC-speaker tones

Test play (what the editor's Play button runs): skip the title and character creation and put a
new hero of the given class straight on a level, optionally on a square:

    python run_deluxe.py --pack mypack --quick 1 --level 2 --at 45,60
"""
import argparse
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', help='a pack folder, or a name under packs/')
    ap.add_argument('--level', type=int, default=None)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--quick', type=int, metavar='CLASS', help='start at once with a hero of this class')
    ap.add_argument('--at', help='x,y: where the quick-start hero stands')
    ap.add_argument('--fixes', choices=('on', 'off', 'pack'), help="the original's bugs (default: settings.ini)")
    ap.add_argument('--sound', choices=('on', 'off'), help='the PC-speaker tones (default: settings.ini)')
    args = ap.parse_args()
    if args.pack:
        os.environ['QUEST_PACK'] = args.pack          # before the engine loads the pack

    os.environ.setdefault('SDL_VIDEO_CENTERED', '1')     # the window opens in the middle of the screen
    import pygame
    from engine.game import Game
    from engine import settings as player_settings

    pygame.init()
    scale = args.scale
    try:                                                 # no bigger than the screen holds (title bar and taskbar too)
        dw, dh = pygame.display.get_desktop_sizes()[0]
        scale = max(1, min(scale, dw // 640, (dh - 120) // 480))
    except (pygame.error, IndexError):
        pass
    window = pygame.display.set_mode((640 * scale, 480 * scale), pygame.RESIZABLE)
    settings = player_settings.load()
    for key in ('fixes', 'sound'):
        if getattr(args, key):
            settings[key] = getattr(args, key)
    game = Game(window, start_level=args.level or 1, settings=settings)
    title = game.pack.quest.get('title', 'The Quest')
    pygame.display.set_caption('The Quest Deluxe' if title == 'The Quest' else f'{title} - The Quest Deluxe')
    if args.quick:
        at = tuple(int(v) for v in args.at.split(',')) if args.at else None
        game.quick_start(args.quick, args.level or game.pack.quest.get('first_level', 1), at)
    game.run()
    pygame.quit()


if __name__ == '__main__':
    main()
