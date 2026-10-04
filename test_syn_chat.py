from pathlib import Path
from contextlib import contextmanager
from io import StringIO

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


@pytest.fixture
def unit_cli_session(monkeypatch):
    """Unit double only: checks CLI control flow, never proves model inference."""
    import synergesis_chat
    state = {'messages': [], 'closed': False, 'max_turns': None}

    class UnitSession:
        def turn(self, message):
            state['messages'].append(message)
            return {'text': 'unit-test reply', 'cycle_glyph_id': 'unit-test trace'}

    @contextmanager
    def unit_open(_root, _backend, *, max_turns, profile=None):
        state['max_turns'] = max_turns
        try:
            yield UnitSession()
        finally:
            state['closed'] = True

    monkeypatch.setattr(synergesis_chat, 'open_conversation', unit_open)
    return state


def test_unit_blank_lines_do_not_stop_or_consume_turn_budget(tmp_path, monkeypatch, unit_cli_session):
    """More than 32 blank lines may separate actual user turns."""
    monkeypatch.setattr('sys.stdin', StringIO('\n \n\t\n' * 40 + 'Bonjour\n' + '\n' * 80 + 'Encore\n/quitter\n'))
    assert main(['--output', str(tmp_path / 'session'), '--max-turns', '2']) == 0
    assert unit_cli_session['messages'] == ['Bonjour', 'Encore']
    assert unit_cli_session['closed']


@pytest.mark.parametrize('input_text', ['', '\n \n\r\n', '/quitter\nBonjour\n', '\n' * 80 + ' /quitter \nBonjour\n'])
def test_unit_eof_and_quit_close_without_model_call(tmp_path, monkeypatch, unit_cli_session, input_text):
    """True EOF and quit are distinct from a readable empty line."""
    monkeypatch.setattr('sys.stdin', StringIO(input_text))
    assert main(['--output', str(tmp_path / 'session')]) == 0
    assert unit_cli_session['messages'] == []
    assert unit_cli_session['closed']


def test_unit_blank_lines_do_not_relax_twenty_turn_cap(tmp_path, monkeypatch, unit_cli_session):
    monkeypatch.setattr('sys.stdin', StringIO(('\n' * 40 + 'Bonjour\n') * 21))
    assert main(['--output', str(tmp_path / 'session'), '--max-turns', '20']) == 0
    assert unit_cli_session['messages'] == ['Bonjour'] * 20
    assert unit_cli_session['max_turns'] == 20
    assert unit_cli_session['closed']


def test_unit_profile_command_budget_stays_thirty_two(tmp_path, monkeypatch, unit_cli_session):
    import synergesis_initiative
    commands = []

    class UnitProfile:
        def __init__(self, _root):
            pass

        def recall(self, body):
            commands.append(body)
            return {'unit_test': True}

    monkeypatch.setattr(synergesis_initiative, 'InitiativeProfile', UnitProfile)
    monkeypatch.setattr('sys.stdin', StringIO(('\n' * 40 + '/memoire\n') * 33 + 'Bonjour\n'))
    assert main(['--output', str(tmp_path / 'session'), '--profile', str(tmp_path / 'profile')]) == 0
    assert len(commands) == 32
    assert unit_cli_session['messages'] == []
    assert unit_cli_session['closed']
