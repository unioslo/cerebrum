# encoding: utf-8
""" Unit tests for mod:`Cerebrum.modules.job_runner.socket_ipc` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io

import pytest

from Cerebrum.modules.job_runner import socket_ipc


# Uses `new_file` fixture from `conftest`


class MockSocket(object):
    """ Mock socket send/recv using a byte buffer. """

    def __init__(self, sent_data=None):
        self.buffer = io.BytesIO(sent_data or b"")

    def send(self, data):
        return self.buffer.write(data)

    def recv(self, size):
        return self.buffer.read(size)


class BrokenSocket(object):
    """ A socket that can't send or receive. """

    def __init__(self, sent_data=None):
        pass

    def send(self, data):
        return 0

    def recv(self, size):
        return b""


#
# Test SocketConnection
#


MOCK_BYTES = """
Some text snippets from
<https://www.w3.org/2001/06/utf-8-test/UTF-8-demo.html>.
Original by Markus Kuhn, adapted for HTML by Martin Dürst.

Sample text
‾‾‾‾‾‾‾‾‾‾‾
Mathematics:
  ∮ E⋅da = Q,  n → ∞, ∑ f(i) = ∏ g(i), ∀x∈ℝ: ⌈x⌉ = −⌊−x⌋, α ∧ ¬β = ¬(¬α ∨ β),

Greek:
  Σὲ γνωρίζω ἀπὸ τὴν κόψη

Runes:
  ᚻᛖ ᚳᚹᚫᚦ ᚦᚫᛏ ᚻᛖ ᛒᚢᛞᛖ ᚩᚾ ᚦᚫᛗ ᛚᚪᚾᛞᛖ ᚾᚩᚱᚦᚹᛖᚪᚱᛞᚢᛗ ᚹᛁᚦ ᚦᚪ ᚹᛖᛥᚫ

Braille:
  ⡌⠁⠧⠑ ⠼⠁⠒  ⡍⠜⠇⠑⠹⠰⠎ ⡣⠕⠌


This text should be longer than 1024 characters, so that we can easliy
manipulate it to match the buffer_size in SocketConnection.  To do this, we
will simply add some nonsense passing characters after this section.

123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789
123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789
123456789 123456789 123456789 123456789 123456789 123456789 123456789 123456789
""".lstrip().encode("utf-8")[:1024]


def _generate_bytes(_size):
    size = int(_size)
    size += bool(size < _size)  # round up
    chunks = size // len(MOCK_BYTES)
    rest = size % len(MOCK_BYTES)
    return MOCK_BYTES * chunks + MOCK_BYTES[:rest]


def test_mock_bytes():
    # sanity check our test helper
    assert len(MOCK_BYTES) == 1024
    assert _generate_bytes(1024) == MOCK_BYTES
    assert _generate_bytes(1024.3) == MOCK_BYTES + MOCK_BYTES[:1]
    assert _generate_bytes(1023) == MOCK_BYTES[:1023]
    assert _generate_bytes(1024 + 1023) == MOCK_BYTES + MOCK_BYTES[:1023]


def test_socket_connection_send():
    mock = MockSocket()
    conn = socket_ipc.SocketConnection(mock)
    bytestr = _generate_bytes(conn.buffer_size * 3.5)
    sent = conn.send(bytestr)
    assert sent == len(bytestr) + 1  # bytestr + eof
    assert mock.buffer.getvalue() == bytestr + conn.eof


def test_socket_connection_send_unicode():
    """ send refuses to send non-byte input. """
    mock = MockSocket()
    conn = socket_ipc.SocketConnection(mock)
    with pytest.raises(ValueError):
        conn.send("some unicode text")


def test_socket_connection_send_eof():
    """ send refuses to send a literal null-byte. """
    mock = MockSocket()
    conn = socket_ipc.SocketConnection(mock)
    with pytest.raises(ValueError):
        conn.send(b"text with \x00 null-terminator")


def test_socket_connection_send_max():
    """ send refuses to send more than max_size. """
    mock = MockSocket()
    conn = socket_ipc.SocketConnection(mock)
    bytestr = _generate_bytes(conn.max_size)  # won't fit eof
    with pytest.raises(ValueError):
        conn.send(bytestr)


def test_socket_connection_send_empty():
    """ recv requires *something to be received* (at least an eof). """
    conn = socket_ipc.SocketConnection(BrokenSocket())
    with pytest.raises(RuntimeError):
        conn.send(b"bytes")


def test_socket_connection_recv():
    bytestr = _generate_bytes(socket_ipc.SocketConnection.buffer_size * 3.5)
    mock = MockSocket(bytestr + socket_ipc.SocketConnection.eof)
    conn = socket_ipc.SocketConnection(mock)
    data = conn.recv()
    assert len(data) == len(bytestr)
    assert data == bytestr


def test_socket_connection_recv_empty():
    """ recv requires *something to be received* (at least an eof). """
    conn = socket_ipc.SocketConnection(BrokenSocket())
    with pytest.raises(RuntimeError):
        conn.recv()


def test_socket_connection_recv_max():
    """ recv truncates data to max_size. """
    max_size = socket_ipc.SocketConnection.max_size
    bytestr = _generate_bytes(max_size * 1.5)
    mock = MockSocket(bytestr + socket_ipc.SocketConnection.eof)
    conn = socket_ipc.SocketConnection(mock)
    data = conn.recv()
    assert data == bytestr[:max_size]


#
# Test Commands
#


def test_commands_init():
    assert socket_ipc.Commands()


def test_commands_add():
    cmds = socket_ipc.Commands()
    add = (lambda a, b: a + b)
    cmds.add("add", 2)(add)
    assert cmds.commands['add'] is add


@pytest.fixture
def commands():
    cmds = socket_ipc.Commands()
    add = (lambda a, b: a + b)
    bool_ = (lambda v: bool(v))
    cmds.add("add", 2)(add)
    cmds.add("bool", 1)(bool_)
    return cmds


def test_commands_get_hit(commands):
    assert commands.get("add")


def test_commands_get_miss(commands):
    with pytest.raises(ValueError):
        commands.get("sub")


def test_commands_check_ok(commands):
    commands.check("add", [3, 7])


def test_commands_check_error(commands):
    with pytest.raises(ValueError):
        commands.check("add", [3])


def test_commands_parse_ok(commands):
    fn = commands.get("add")
    args = [3, 7]
    assert commands.parse(["add", args]) == (fn, args)


def test_commands_parse_err(commands):
    with pytest.raises(ValueError):
        commands.parse(["add"])
    with pytest.raises(ValueError):
        commands.parse(["sub", []])


def test_commands_build(commands):
    assert commands.build("add", [3, 7]) == ["add", [3, 7]]


#
# Test SocketProtocol
#


class MockJobRunner(object):

    class MockJobQueue(object):

        class MockJob(object):
            pass

        _jobs = {
            "foo": MockJob(),
            "bar": MockJob(),
        }

        def __init__(self):
            self._run_queue = []
            self._forced_queue = []
            self.did_reload = False

        def reload_scheduled_jobs(self):
            self.did_reload = True

        def get_known_jobs(self):
            return self._jobs

        def get_known_job(self, name):
            return self._jobs[name]

        def insert_job(self, queue, job_name):
            return

        def get_forced_run_queue(self):
            return self._forced_run

    def __init__(self):
        # JR attrs
        self.job_queue = self.MockJobQueue()
        self.ready_to_run = ()
        self.queue_paused_at = 0
        self.sleep_to = 0

        # test attrs
        self.did_wake = False
        self.did_quit = False

    def wake_runner_signal(self):
        self.did_wake = True

    def quit(self):
        self.did_quit = True


@pytest.fixture
def proto_sock():
    return MockSocket()


@pytest.fixture
def proto(proto_sock):
    conn = socket_ipc.SocketConnection(proto_sock)
    jr = MockJobRunner()
    return socket_ipc.SocketProtocol(conn, jr)


def test_proto_encode():
    enc = socket_ipc.SocketProtocol.encode
    assert enc(["foo", "bar"]) == b'["foo", "bar"]'


def test_proto_decode():
    dec = socket_ipc.SocketProtocol.decode
    assert dec(b'["foo", "bar"]') == ["foo", "bar"]


def test_proto_cmd_ping(proto, proto_sock):
    eof = proto.connection.eof
    cmd = proto.commands.get("PING")
    cmd(proto)
    assert proto_sock.buffer.getvalue() == b'"PONG"' + eof
