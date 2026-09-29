from pathlib import Path

import pytest

from synergesis_chat import main, terminal_text


def test_demo_cli_uses_real_stack_without_key(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv('SYN_OPENAI_API_KEY', raising=False)
    root = tmp_path / 'conversation'
    assert main(['--output', str(root), '--message', 'Bonjour Syn']) == 0
    output = capsys.readouterr().out
    assert 'sans modèle ni réseau' in output
    assert 'Syn >' in output
    assert 'Trace :' in output
    assert list(root.rglob('glyph_ledger.jsonl'))


def test_output_never_reused(tmp_path):
    root = tmp_path / 'existing'
    root.mkdir()
    sentinel = root / 'keep.txt'
    sentinel.write_text('unchanged')
    with pytest.raises(SystemExit):
        main(['--output', str(root), '--message', 'Bonjour'])
    assert sentinel.read_text() == 'unchanged'


def test_terminal_control_sequences_are_inert():
    result = terminal_text('Hi\x1b[31m\x07\u202eevil\ntext\tX')
    assert '\x1b' not in result and '\x07' not in result and '\u202e' not in result
    assert '\ntext\tX' in result


def test_remote_configuration_fails_before_session(tmp_path):
    root = tmp_path / 'unused'
    with pytest.raises(SystemExit):
        main(['--provider', 'openai', '--output', str(root), '--message', 'Hi'])
    assert not root.exists()


def test_cli_error_never_echoes_provider_content(tmp_path, capsys, monkeypatch):
    import synergesis_chat
    def fail(_self, _messages):
        raise RuntimeError('private-sentinel-value')
    monkeypatch.setattr(synergesis_chat.DemoBackend, 'reply', fail)
    assert main(['--output', str(tmp_path / 'failed'), '--message', 'Bonjour']) == 1
    output = capsys.readouterr()
    assert 'private-sentinel-value' not in output.out + output.err


def test_blank_or_oversized_message_rejected_before_output(tmp_path):
    root = tmp_path / 'unused'
    for message in (' ', 'x' * 8193):
        with pytest.raises(SystemExit):
            main(['--output', str(root), '--message', message])
    assert not root.exists()
