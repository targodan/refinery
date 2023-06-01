import re
import re
import struct
from abc import ABC
from typing import ByteString, Union, Optional, Generator, Tuple

from refinery import Unit, Arg


class interp(Unit):
    """
    Interprets the input data according to the given extended struct-format.
    The interpreted data is then formatted as a string.
    """

    class formatPart(ABC):
        def __init__(self, s: str):
            self._s = s

        def eat(self, data: memoryview) -> Tuple[bytes, memoryview]:
            pass

        def __repr__(self) -> str:
            return f"{self.__class__.__name__}({repr(self._s)})"

    class formatPartSeparator(formatPart):
        def eat(self, data: memoryview) -> Tuple[bytes, memoryview]:
            return self._s.encode(Unit.codec), data

    class formatPartStruct(formatPart):
        def eat(self, data: memoryview) -> Tuple[bytes, memoryview]:
            size = struct.calcsize(self._s)
            value, = struct.unpack(self._s, data[:size])
            return str(value).encode(Unit.codec), data[size:]

    def __init__(self,
                 format: Arg(type=str, help="format string for interpretation"),
                 as_chunks: Arg.Switch('-c') = False):
        super().__init__(format=format, as_chunks=as_chunks)
        rex = re.compile(r"(?P<pre>[^{]*)\{(?P<format>[^{]+)}(?P<post>[^{]*)")
        self.format_parts = []
        for match in rex.finditer(self.args.format):
            if g := match.group('pre'):
                self.format_parts.append(self.formatPartSeparator(g))
            if g := match.group('format'):
                self.format_parts.append(self.formatPartStruct(g))
            if g := match.group('post'):
                self.format_parts.append(self.formatPartSeparator(g))

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        data = memoryview(data)
        out = bytearray()
        while data:
            for part in self.format_parts:
                tmp, data = part.eat(data)
                out += tmp

            if self.args.as_chunks:
                yield out
                out = bytearray()

        if not self.args.as_chunks:
            yield out
