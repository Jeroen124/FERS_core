"""Read a JSON document one value at a time.

``json.load`` builds the whole document before it returns, so a large solver
result exists as Python objects all at once. This walks the document instead:
the caller descends into the objects it wants to take apart and decodes the rest
value by value, so only the value in hand is ever held decoded.
"""

from __future__ import annotations

import json
import re
from typing import IO, Any, Iterator, Union

_DECODER = json.JSONDecoder()
_WHITESPACE = re.compile(r"[ \t\n\r]*")
_NUMBER_START = frozenset("-0123456789")
_AFTER_NUMBER = frozenset(" \t\n\r,]}")
_CHUNK = 1 << 18


class JsonStream:
    """A cursor over one JSON document, read from a text file or held in a string.

    ``iter_object`` yields the keys of the object at the cursor. The caller has to
    consume each key's value -- ``read_value``, ``skip_value`` or a nested
    ``iter_object`` -- before asking for the next key.
    """

    def __init__(self, source: Union[str, IO[str]], chunk_chars: int = _CHUNK):
        if isinstance(source, str):
            # Read in place: a str is never copied into a StringIO, which would store it
            # at four bytes per character.
            self._buf, self._file, self._eof = source, None, True
        else:
            self._buf, self._file, self._eof = "", source, False
        self._pos = 0
        self._chunk = chunk_chars
        # Where _buf[0] sits in the document, for error positions.
        self._dropped = 0
        self._dropped_lines = 0
        self._dropped_column = 0

    @property
    def offset(self) -> int:
        """Characters consumed so far."""
        return self._dropped + self._pos

    def peek(self) -> str:
        """The next character that is not whitespace, or '' at the end of the input."""
        return self._skip_whitespace()

    def read_value(self) -> Any:
        """Decode the value at the cursor whole and move past it."""
        first = self._skip_whitespace()
        if not first:
            raise self._error("Expecting value", self._pos)
        while True:
            try:
                value, end = _DECODER.raw_decode(self._buf, self._pos)
            except json.JSONDecodeError as exc:
                if self._read_more(len(self._buf) - self._pos):
                    continue
                raise self._error(exc.msg, exc.pos) from None
            # A number cut by the buffer edge decodes short: "1.5e" as 1.5, "-0." as 0.
            if first in _NUMBER_START and (end == len(self._buf) or self._buf[end] not in _AFTER_NUMBER):
                if self._read_more(len(self._buf) - self._pos):
                    continue
            self._pos = end
            return value

    def skip_value(self) -> None:
        self.read_value()

    def iter_object(self) -> Iterator[str]:
        """Yield the keys of the object at the cursor; see the class docstring."""
        if self._skip_whitespace() != "{":
            raise self._error("Expecting '{'", self._pos)
        self._pos += 1
        if self._skip_whitespace() == "}":
            self._pos += 1
            return
        while True:
            if self._skip_whitespace() != '"':
                raise self._error("Expecting property name enclosed in double quotes", self._pos)
            key = self.read_value()
            if self._skip_whitespace() != ":":
                raise self._error("Expecting ':' delimiter", self._pos)
            self._pos += 1
            before = self.offset
            yield key
            if self.offset == before:
                raise RuntimeError(f"JsonStream: the value of {key!r} was not consumed")
            separator = self._skip_whitespace()
            self._pos += 1
            if separator == "}":
                return
            if separator != ",":
                raise self._error("Expecting ',' delimiter", self._pos - 1)

    def expect_end(self) -> None:
        """Raise unless only whitespace is left."""
        if self._skip_whitespace():
            raise self._error("Extra data", self._pos)

    def _skip_whitespace(self) -> str:
        while True:
            self._pos = _WHITESPACE.match(self._buf, self._pos).end()
            if self._pos < len(self._buf):
                return self._buf[self._pos]
            if not self._read_more(self._chunk):
                return ""

    def _read_more(self, at_least: int) -> bool:
        """Append at least ``at_least`` characters to the buffer; False at end of input."""
        if self._eof:
            return False
        if self._pos:
            newlines = self._buf.count("\n", 0, self._pos)
            if newlines:
                self._dropped_lines += newlines
                self._dropped_column = self._pos - self._buf.rfind("\n", 0, self._pos) - 1
            else:
                self._dropped_column += self._pos
            self._dropped += self._pos
            self._buf = self._buf[self._pos :]
            self._pos = 0
        data = self._file.read(max(at_least, self._chunk))
        if not data:
            self._eof = True
            return False
        self._buf += data
        return True

    def _error(self, msg: str, pos: int) -> json.JSONDecodeError:
        """A JSONDecodeError placed in the whole document, not in the current buffer."""
        newlines = self._buf.count("\n", 0, pos)
        lineno = self._dropped_lines + newlines + 1
        if newlines:
            colno = pos - self._buf.rfind("\n", 0, pos)
        else:
            colno = self._dropped_column + pos + 1
        err = json.JSONDecodeError(msg, "", 0)
        err.pos = self._dropped + pos
        err.lineno, err.colno = lineno, colno
        err.args = (f"{msg}: line {lineno} column {colno} (char {err.pos})",)
        return err
