import argparse
from unittest.mock import patch

import pytest

from meme_games.cli import main, valid_port


def test_cli_passes_host_and_port_to_uvicorn():
    with patch('meme_games.cli.uvicorn.run') as run:
        main(['--host', '127.0.0.1', '--port', '9000'])
    assert run.call_args.kwargs['host'] == '127.0.0.1'
    assert run.call_args.kwargs['port'] == 9000


def test_port_must_be_in_tcp_range():
    with pytest.raises(argparse.ArgumentTypeError):
        valid_port('70000')
