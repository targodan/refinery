#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from .. import TestUnitBase
from refinery.lib.loader import load_pipeline as L


class TestPackbits(TestUnitBase):

    def test_simple_msb(self):
        unit = self.load("h:AA", bit_width=1, bit_order="msb")
        data = B'\x00' * 8 + B'\x01' * 8 + B'\xAA' + B'\x00' * 4 + B'\x01' * 4
        self.assertEqual(unit.process(data), B'\x00\xFF\xAA\x0F')

    def test_simple_lsb(self):
        unit = self.load("h:AA", bit_width=1, bit_order="lsb")
        data = B'\x00' * 8 + B'\x01' * 8 + B'\xAA' + B'\x00' * 4 + B'\x01' * 4
        self.assertEqual(unit.process(data), B'\x00\xFF\xAA\xF0')

    def test_2bit_msb(self):
        unit = self.load("h:AA", bit_width=2, bit_order="msb")
        data = B'\x00' * 4 + B'\x03' * 4 + B'\xAA' + B'\x00' * 2 + B'\x03' * 2
        self.assertEqual(unit.process(data), B'\x00\xFF\xAA\x0F')

    def test_2bit_lsb(self):
        unit = self.load("h:AA", bit_width=2, bit_order="lsb")
        data = B'\x00' * 4 + B'\x03' * 4 + B'\xAA' + B'\x00' * 2 + B'\x03' * 2
        self.assertEqual(unit.process(data), B'\x00\xFF\xAA\xF0')
