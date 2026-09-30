"""Which port the verifiers check: the classic port (classic/engine, the default) or, with
QUEST_ENGINE=deluxe, The Quest Deluxe (TheQuestDeluxe/engine) playing its packs/TheQuest. Import
this before anything from engine:

    QUEST_ENGINE=deluxe python verify_events.py

Both editions call their code engine/, so choosing is only a matter of which folder comes first on
the path; the verifiers run unchanged.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSIC = os.path.dirname(os.path.dirname(HERE))
NAME = os.environ.get('QUEST_ENGINE', 'classic')
if NAME == 'deluxe':
    sys.path.insert(0, os.path.join(os.path.dirname(CLASSIC), 'TheQuestDeluxe'))
    import engine.formats                                               # noqa: E402  The Quest Deluxe's
    # the verifiers read the original's files (fonts, data) with the classic port's DataSource,
    # which The Quest Deluxe, standing alone, doesn't have: lend it the classic one
    spec = importlib.util.spec_from_file_location('classic_formats', os.path.join(CLASSIC, 'engine', 'formats.py'))
    classic_formats = sys.modules['classic_formats'] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classic_formats)
    engine.formats.DataSource = classic_formats.DataSource
elif NAME != 'classic':
    sys.exit(f'QUEST_ENGINE={NAME}: it is classic (the default) or deluxe')
