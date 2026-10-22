"""
------------------------------------------------------------------------
File : upload.py
Description: Upload - a file chosen by the user, as the core hands it
             to an Importer (and to a "file" field). The same Upload goes
             through inspect(), preview() and import_(), so its content
             can be read any number of times.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
from typing import BinaryIO, Optional


class Upload:
    """
    `filename` is the name the user's file had (used to pick importers by
    extension), `content_type` the MIME type the client declared ("" if
    unknown). read() returns the whole content; `stream` is a fresh,
    rewound binary stream over it on every access.
    """

    def __init__(self, filename: str, source: BinaryIO, content_type: str = ""):
        self.filename = filename
        self.content_type = content_type or ""
        self._source: Optional[BinaryIO] = source
        self._data: Optional[bytes] = None

    @classmethod
    def from_bytes(cls, filename: str, data: bytes, content_type: str = "") -> "Upload":
        upload = cls(filename, io.BytesIO(b""), content_type)
        upload._data = bytes(data)
        upload._source = None
        return upload

    def read(self) -> bytes:
        if self._data is None:
            assert self._source is not None
            self._data = self._source.read()
            self._source = None
        return self._data

    @property
    def stream(self) -> BinaryIO:
        return io.BytesIO(self.read())

    def __repr__(self) -> str:
        return f"Upload(filename={self.filename!r}, content_type={self.content_type!r})"
