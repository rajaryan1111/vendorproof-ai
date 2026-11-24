"""Private ClamAV INSTREAM protocol. Only controlled outcomes leave this module."""

import socket
import struct
import time
from datetime import UTC, datetime

from fastapi import HTTPException


def reply(sock):
    data = bytearray()
    while len(data) < 1024:
        part = sock.recv(1024)
        if not part:
            break
        data.extend(part)
        if b"\x00" in data:
            return bytes(data).partition(b"\x00")[0]
    raise OSError("incomplete scanner reply")


def scan(data, settings):
    if settings.scanner_socket is None:
        if settings.environment == "production":
            raise HTTPException(503)
        return False

    def connect():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(15)
            sock.connect(str(settings.scanner_socket))
        except OSError:
            sock.close()
            raise
        return sock

    try:
        if settings.environment == "production":
            with connect() as sock:
                sock.sendall(b"zVERSION\0")
                version = reply(sock).decode("ascii").split("/")
                if len(version) != 3 or not version[1].isdigit():
                    raise ValueError
                released = datetime.strptime(
                    version[2], "%a %b %d %H:%M:%S %Y"
                ).replace(tzinfo=UTC)
                if not -300 <= time.time() - released.timestamp() <= 3 * 86400:
                    raise ValueError
        with connect() as sock:
            sock.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), 65536):
                block = data[start : start + 65536]
                sock.sendall(struct.pack("!I", len(block)) + block)
            sock.sendall(bytes(4))
            result = reply(sock)
    except (OSError, ValueError) as exc:
        raise HTTPException(503) from exc
    if result.endswith(b" FOUND"):
        raise HTTPException(422)
    if result != b"stream: OK":
        raise HTTPException(503)
    return True
