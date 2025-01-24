#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from refinery.units.meta import Arg, ConditionalUnit


class iffs(ConditionalUnit, extend_docs=True):
    """
    Filter incoming chunks depending on whether they contain a given binary substring.
    """
    def __init__(
        self,
        needle: Arg(help='the string to search for'),
        retain=False,
    ):
        super().__init__(
            needle=needle,
            retain=retain,
        )

    def match(self, chunk):
        return self.args.needle in chunk
