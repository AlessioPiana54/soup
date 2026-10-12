"""
------------------------------------------------------------------------
File : input.py
Description: Generic input contracts. Deliberately not log-specific: a
             future plugin must be able to read other kinds of input
             (e.g. process models), not only event logs - EventLogReader
             (event_log.py) is a specialization of InputReader for the
             one `kind` the core currently ships, EVENT_LOG.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Generic, Mapping, Sequence, TypeVar

# The only input kind the core knows about today. Future plugins may
# introduce further kinds (e.g. "process_model"); the core must not be
# modified to support them - only InputReader/InputHandler are reused.
EVENT_LOG = "event_log"

T = TypeVar("T")


class InputReader(ABC, Generic[T]):
    """
    Reads one input format into an in-memory representation of type T
    (e.g. EventLogData for kind=EVENT_LOG). A plugin contributes one
    InputReader per format it supports.
    """

    format_id: str
    label: str
    extensions: Sequence[str] = ()
    kind: str

    def accepts(self, filename: str) -> bool:
        """Default: match by file extension. Override for content sniffing."""

        lowered = filename.lower()
        return any(lowered.endswith(extension.lower()) for extension in self.extensions)

    @abstractmethod
    def read(self, stream: BinaryIO) -> T:
        """Parse `stream` into the reader's output type T."""
        raise NotImplementedError


class InputHandler(ABC, Generic[T]):
    """
    Turns the data produced by an InputReader of the same `kind` into a
    Result the API layer can return. One handler per kind (e.g. the core
    ships the event-log import handler for kind=EVENT_LOG).
    """

    kind: str

    @abstractmethod
    def handle(self, data: T, options: Mapping[str, Any]) -> "Result":  # noqa: F821 - see soup/core/results.py
        """
        Process `data` (as produced by a matching InputReader) given
        `options`, and return a Result. `Result` itself is defined
        elsewhere in the host (soup/core/results.py) and out of scope for
        this module; using it only as a forward reference here keeps
        soup/core/contracts free of any dependency on that module.
        """
        raise NotImplementedError
