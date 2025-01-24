#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import Counter
from refinery import Unit, Arg


class xkey(Unit):
    """
    The unit expects encrypted input which was encrypted byte-wise with a polyalphabetic key, and
    where the plaintext also has one letter that occurs with overwhelming frequency. This is often
    the case for the zero byte in binary formats such as PE files, and the space character in text
    files. Based on this assumption, the unit computes the most likely key. This can be useful to
    decrypt PE and uncompressed text files that were encrypted byte-wise using a short key.
    """
    def __init__(
        self,
        range: Arg.Bounds(help='range of length values to try in Python slice syntax, the default is {default}.') = slice(1, 32),
    ):
        super().__init__(range=range)

    def process(self, data: bytearray):
        score = 0
        guess = None
        bounds: slice = self.args.range
        view = memoryview(data)

        n = len(view)

        if n <= 1:
            return view

        start = bounds.start or 1
        stop = min(bounds.stop or n, n)

        if bounds.step is not None:
            step = bounds.step
            if bounds.start is None:
                start *= step
        else:
            step = 1

        self.log_debug(F'received input range [{bounds.start}:{bounds.stop}:{bounds.step}], using [{start}:{stop}:{step}]')

        for _count in range(start, stop + 1, step):
            _guess = [Counter(view[j::_count]).most_common(1)[0] for j in range(_count)]
            _score = sum(letter_count for _, letter_count in _guess) / n

            # This scaling accounts for the smaller probability of larger keys. No proper statistical analysis has been
            # conducted to derive it; there might be plenty of room for improvement here.
            _score = _score * ((n - _count) / (n - 1)) ** _count

            logmsg = F'got score {_score * 100:5.2f}% for length {_count}'
            if _score > score:
                self.log_info(logmsg)
                score = _score
                guess = bytearray(value for value, _ in _guess)
            else:
                self.log_debug(logmsg)

        return guess
