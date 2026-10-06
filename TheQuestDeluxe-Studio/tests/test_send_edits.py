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
        if method == 'PATCH':
            return 200, {}
        if '/git/ref/heads/edits/' in url:
            return 404, {}
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
    br = se.send([(a, 'TheQuestDeluxe-Studio/Custom Maps/x/sprites/items/1.png'),
                  (a, 'TheQuestDeluxe-Studio/Custom Maps/compare zips/c1.zip')], 'report', 'KEY', 'Bro Name', when=1760000000,
                 transport=fake, progress=seen.append, user='Bro_1')
    assert br == 'edits/bro_1', br
    ref = calls[-1]
    assert ref[0] == 'POST' and ref[2]['ref'] == 'refs/heads/' + br and ref[2]['sha'] == 'C1'
    tree = [c for c in calls if c[1].endswith('git/trees')][0][2]
    assert tree['base_tree'] == 'T0' and len(tree['tree']) == 4
    paths = [e['path'] for e in tree['tree']]
    assert paths[0] == 'edits_inbox/bro_1/files/TheQuestDeluxe-Studio/Custom Maps/x/sprites/items/1.png', paths
    assert paths[1] == 'edits_inbox/bro_1/compare zips/c1.zip', paths
    assert 'edits_inbox/bro_1/latest/WHAT_CHANGED.txt' in paths and any('/sends/2025-10-' in p for p in paths)
    assert all(p.startswith('edits_inbox/bro_1/') for p in paths), 'everything stays in the person\'s own folder'
    assert all(not c[1].endswith('heads/main') or c[0] == 'GET' for c in calls)       # main is never written
    assert seen[-1] == 'Sent.'
    # a second send goes on top of the person's own branch (kept history), moving it with PATCH, never a second branch
    calls.clear()
    own = {'on': True}

    def fake2(method, url, body, token):
        if url.endswith('git/ref/heads/edits/bro_1'):
            return 200, {'object': {'sha': 'OWN'}}
        if url.endswith('git/commits/OWN'):
            return 200, {'tree': {'sha': 'TOWN'}}
        return fake(method, url, body, token)
    se.send([(a, 'p')], 'r2', 'KEY', 'Bro Name', transport=fake2, user='bro_1')
    commit = [c for c in calls if c[1].endswith('git/commits') and c[0] == 'POST'][0][2]
    assert commit['parents'] == ['OWN'], commit
    assert [c for c in calls if c[1].endswith('git/trees')][0][2]['base_tree'] == 'TOWN'
    assert calls[-1][0] == 'PATCH' and calls[-1][1].endswith('git/refs/heads/edits/bro_1'), calls[-1]
    assert not any(c[1].endswith('git/refs') for c in calls), 'no second branch'
    assert se.username('  Bro Name!! ') == 'bro-name' and se.branch_name('Mystwisters') == 'edits/mystwisters'
    try:
        se.send([(a, 'p')], 'r', 'KEY', '', transport=fake)
        raise AssertionError
    except se.SendError as e:
        assert 'username' in str(e)
    for status, word in ((401, 'did not accept'), (403, 'refused'), (404, 'refused')):
        try:
            se.send([(a, 'p')], 'r', 'KEY', user='u', transport=lambda *x, s=status: (s, {}))
            raise AssertionError
        except se.SendError as e:
            assert word in str(e), e
    for bad in (dict(files=[], token='KEY'), dict(files=[(a, 'p')], token='')):
        try:
            se.send(bad['files'], 'r', bad['token'], user='u', transport=fake)
            raise AssertionError
        except se.SendError:
            pass
    cfg = os.path.join(tmp, 'cfg.json')
    se.save_settings({'key': 'K', 'name': 'N'}, cfg)
    se.save_settings({'name': 'M'}, cfg)
    assert se.load_settings(cfg) == {'key': 'K', 'name': 'M'} and se.load_settings(os.path.join(tmp, 'no')) == {}
    print('send edits: one branch per person with their own folder, later sends on top, main untouched, clear errors, key kept outside the game: ok')


if __name__ == '__main__':
    main()
