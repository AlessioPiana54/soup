"""
------------------------------------------------------------------------
File : import_service.py
Description: ImportCommand (replaces the 10 positional parameters of the
             legacy GraphService.create_new_dataset_s) and ImportService,
             which dispatches an import to the right InputReader (by
             filename/kind) and then to the InputHandler registered for
             that reader's kind.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, BinaryIO, Mapping, Optional

from soup.core.contracts import InputHandler, InputReader
from soup.core.errors import ValidationError
from soup.core.registry import Registry
from soup.core.results import Result


@dataclass
class ImportCommand:
    filename: str
    stream: BinaryIO
    kind: Optional[str] = None
    options: Mapping[str, Any] = field(default_factory=dict)


class ImportService:
    def __init__(self, readers: Registry[InputReader], handlers: Registry[InputHandler]):
        self._readers = readers
        self._handlers = handlers

    def reader_for(self, filename: str, kind: Optional[str] = None) -> InputReader:
        candidates = [
            reader for reader in self._readers
            if (kind is None or reader.kind == kind) and reader.accepts(filename)
        ]

        if not candidates:
            supported = sorted({
                extension
                for reader in self._readers
                if kind is None or reader.kind == kind
                for extension in reader.extensions
            })
            raise ValidationError(f"No reader can read '{filename}'. Supported extensions: {supported}")

        if len(candidates) > 1:
            names = [reader.format_id for reader in candidates]
            if kind is None:
                raise ValidationError(
                    f"Multiple readers can read '{filename}' ({names}); specify `kind` to disambiguate."
                )
            raise ValidationError(
                f"Multiple readers of kind '{kind}' can read '{filename}' ({names})."
            )

        return candidates[0]

    def import_(self, cmd: ImportCommand) -> Result:
        reader = self.reader_for(cmd.filename, cmd.kind)
        data = reader.read(cmd.stream)

        handler = self._handlers.get(reader.kind)
        if handler is None:
            raise ValidationError(f"No handler registered for kind '{reader.kind}'")

        options = dict(cmd.options)
        options.setdefault("source_format", reader.format_id)
        return handler.handle(data, options)
