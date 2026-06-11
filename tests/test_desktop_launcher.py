import socket

from biofilm_analyzer.desktop_launcher import _port_is_open


def test_port_is_open_detects_listening_socket() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]

        assert _port_is_open("127.0.0.1", port)


def test_port_is_open_returns_false_for_closed_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]

    assert not _port_is_open("127.0.0.1", port)
