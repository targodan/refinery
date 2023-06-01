#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import struct

from refinery import Unit
from .. import TestUnitBase


class TestCarve(TestUnitBase):

    def test_simple_integer(self):
        unit = self.load("{<I}")

        i = 42
        data = struct.pack("<I", i)
        result = unit(data)
        self.assertEqual(result.decode(Unit.codec), str(i))

    def test_multiple_integer_with_separator(self):
        unit = self.load("{<I},{<I},")

        i1 = 42
        i2 = 43
        data = struct.pack("<II", i1, i2)
        result = unit(data)
        self.assertEqual(result.decode(Unit.codec), f"{i1},{i2},")

    def test_multiple_inputs(self):
        unit = self.load("{<I},{<I},")

        i1 = 42
        i2 = 43
        i3 = 44
        i4 = 45
        data = struct.pack("<IIII", i1, i2, i3, i4)
        result = unit(data)
        self.assertEqual(result.decode(Unit.codec), f"{i1},{i2},{i3},{i4},")

    def test_chunked(self):
        unit = self.load("{<I},{<I}", as_chunks=True)

        i1 = 42
        i2 = 43
        i3 = 44
        i4 = 45
        data = struct.pack("<IIII", i1, i2, i3, i4)
        result = unit(data)
        self.assertEqual(result.decode(Unit.codec), f"{i1},{i2}\n{i3},{i4}")
