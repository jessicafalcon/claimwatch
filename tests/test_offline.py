"""The suite opens no socket (spec Phase 2, invariant 6): conftest's autouse
guard turns every connection attempt into an error, so a test that reaches for
the network fails loudly instead of passing on a connected machine."""

from __future__ import annotations

import socket

import pytest


def test_socket_connect_is_blocked_in_the_suite():
    with pytest.raises(RuntimeError, match="network blocked"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)
    s = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="network blocked"):
            s.connect(("127.0.0.1", 9))
    finally:
        s.close()
