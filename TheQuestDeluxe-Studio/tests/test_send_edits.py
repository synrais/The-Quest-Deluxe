"""core/send_edits.py with a pretend GitHub.   python tests/test_send_edits.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import send_edits as se  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    a = os.path.join(tmp, 'a.png')
    open(a, 'wb').write(b'\x89PNG123')
    calls = []

    def fake(method, url, body, token):
        calls.append((method, url.split('/repos/', 1)[1], body))
        assert token == 'KEY'
        if url.endswith('git/ref/heads/main'):
            return 200, {'object': {'sha': 'H'}}
        if url.endswith('git/commits/H'):
            return 200, {'tree': {'sha': 'T0'}}
        if url.endswith('git/blobs'):
            return 201, {'sha': 'B%d' % len(calls)}
        if url.endswith('git/trees'):
            return 201, {'sha': 'T1'}
        if url.endswith('git/commits'):
            return 201, {'sha': 'C1'}
        if url.endswith('git/refs'):
            return 201, {}
        return 404, {}

    seen = []
    br = se.send([(a, 'TheQuestDeluxe-Studio/packs/x/sprites/items/1.png')], 'report', 'KEY', 'Bro Name', when=1760000000,
                 transport=fake, progress=seen.append)
    assert br.startswith('edits/bro-name-2025-10-'), br
    ref = calls[-1][2]
    assert ref['ref'] == 'refs/heads/' + br and ref['sha'] == 'C1'
    tree = [c for c in calls if c[1].endswith('git/trees')][0][2]
    assert tree['base_tree'] == 'T0' and len(tree['tree']) == 2
    assert tree['tree'][0]['path'] == 'TheQuestDeluxe-Studio/packs/x/sprites/items/1.png'
    assert all(not c[1].endswith('heads/main') or c[0] == 'GET' for c in calls)       # main is never written
    assert seen[-1] == 'Sent.'
    for status, word in ((401, 'did not accept'), (403, 'refused'), (404, 'refused')):
        try:
            se.send([(a, 'p')], 'r', 'KEY', transport=lambda *x, s=status: (s, {}))
            raise AssertionError
        except se.SendError as e:
            assert word in str(e), e
    for bad in (dict(files=[], token='KEY'), dict(files=[(a, 'p')], token='')):
        try:
            se.send(bad['files'], 'r', bad['token'], transport=fake)
            raise AssertionError
        except se.SendError:
            pass
    cfg = os.path.join(tmp, 'cfg.json')
    se.save_settings({'key': 'K', 'name': 'N'}, cfg)
    se.save_settings({'name': 'M'}, cfg)
    assert se.load_settings(cfg) == {'key': 'K', 'name': 'M'} and se.load_settings(os.path.join(tmp, 'no')) == {}
    print('send edits: a branch of its own, main untouched, clear errors, key kept outside the game: ok')


if __name__ == '__main__':
    main()
