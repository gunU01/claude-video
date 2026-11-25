"""VTT syntax, independent repeated speech, and source segment validation."""
import pytest
from transcribe import parse_vtt, normalize_segments


def parse(tmp_path, body):
    path = tmp_path / 'captions.vtt'
    path.write_bytes(body.encode('utf-8'))  # Exact bytes: text mode on Windows would turn \r\n into \r\r\n.
    return parse_vtt(str(path))


def test_blocks_ids_settings_padding_and_missing_separator(tmp_path):
    out = parse(tmp_path, '\ufeffWEBVTT\r\n\r\nNOTE comment\r\n00:00.000 --> 00:01.000\r\nskip\r\n\r\nSTYLE\r\n::cue {}\r\n\r\nREGION\r\nid:one\r\n\r\ncue-id\r\n00:01.000 --> 00:02.000 align:start\r\nfirst\r\n   \r\n<c>last</c>\r\n00:03.000 --> 00:04.000\r\nnext\r\n')
    assert [s['text'] for s in out] == ['first  last', 'next']


def test_valid_long_hours_and_invalid_minutes(tmp_path):
    out = parse(tmp_path, 'WEBVTT\n\n100:02:03.004 --> 100:02:04.000\nx\n\n00:60.000 --> 01:01.000\ninvalid\n')
    assert len(out) == 1 and out[0]['start'] == 360123.004


def test_overlapping_prefix_only_and_mixed_karaoke(tmp_path):
    out = parse(tmp_path, 'WEBVTT\n\n00:01.000 --> 00:03.000\nThank you\n\n00:02.000 --> 00:04.000\nThank you all\n\n00:04.000 --> 00:05.000\nThank you all\n\n00:05.000 --> 00:06.000\nplain <00:05.100><c>spoken</c> ending &lt;literal&gt;\n')
    assert [s['text'] for s in out] == ['Thank you all', 'Thank you all', 'plain spoken ending <literal>']


@pytest.mark.parametrize('segment', [
    {'start': float('nan'), 'end': 1, 'text': 'hi'}, {'start': 2, 'end': 1, 'text': 'hi'},
    {'start': True, 'end': 1, 'text': 'hi'}, {'start': 0, 'end': 1, 'text': ' '},
    {'start': 0, 'end': float('inf'), 'text': 'hi'},
])
def test_rejects_invalid_segments(segment):
    with pytest.raises((ValueError, TypeError)):
        normalize_segments({'segments': [segment]})


def test_overlapping_separate_display_regions_are_not_merged(tmp_path):
    out = parse(tmp_path, 'WEBVTT\n\n00:00.000 --> 00:02.000 line:10%\nHello\n\n00:01.000 --> 00:03.000 line:90%\nHello\n')
    assert len(out) == 2
    assert all(set(s) == {'start', 'end', 'text'} for s in out)


ROLLING = (
    'WEBVTT\n\n'
    '00:00.000 --> 00:02.000 align:start position:0%\n \nfirst line <00:00.500><c>here</c>\n\n'
    '00:02.000 --> 00:02.050 align:start position:0%\nfirst line here\n \n\n'
    '00:02.050 --> 00:04.000 align:start position:0%\nfirst line here\n second line <00:03.000><c>now</c>\n\n'
    '00:04.000 --> 00:04.050 align:start position:0%\nsecond line now\n \n\n'
    '00:04.050 --> 00:06.000 align:start position:0%\nsecond line now\n third line\n'
)


def test_rolling_auto_captions_keep_each_line_once(tmp_path):
    out = parse(tmp_path, ROLLING)
    assert [s['text'] for s in out] == ['first line here', 'second line now', 'third line']
    assert [s['start'] for s in out] == [0.0, 2.05, 4.05]


def test_plain_repeated_phrase_survives_in_non_rolling_captions(tmp_path):
    out = parse(tmp_path, 'WEBVTT\n\n00:00.000 --> 00:01.000\nNo.\n\n00:01.000 --> 00:02.000\nNo.\n')
    assert [s['text'] for s in out] == ['No.', 'No.']
