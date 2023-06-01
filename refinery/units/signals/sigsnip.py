#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math

from refinery.lib.meta import metavars
from refinery.units import Arg
from refinery.units.strings.snip import snip


class sigsnip(snip):
    """
    Snips the input data based on a Python slice expression. For example, the
    initialization `slice 0::1 1::1` would yield a unit that first extracts
    every byte at an even position and then, every byte at an odd position. In
    this case, multiple outputs are produced. The unit can be used in reverse
    mode, in which case the specified ranges are deleted sequentially from the
    input.
    """
    def __init__(
        self,
        slices: Arg(help='Specify start:stop:step in Python slice syntax.', nargs='+') = [slice(None, None)],
        remove: Arg.Switch('-r', help='Remove the slices from the input rather than selecting them.') = False,
        seconds: Arg.Switch('-s', help='Use seconds rather than samples as slice unit.') = False,
    ):
        super(snip, self).__init__(slices=slices, remove=remove, seconds=seconds)

    def process(self, data: bytearray):
        # Assuming np.complex64 as sample format
        bytes_per_sample = 8

        mult = 1
        if self.args.seconds:
            sample_rate = metavars(data).get("sample_rate")
            if not sample_rate:
                raise RuntimeError("cannot specify unit seconds when the sample rate is unknown")
            mult *= sample_rate

        new_slices = [slice(
            int(s.start * mult) * bytes_per_sample if s.start else None,
            math.ceil(s.stop * mult) * bytes_per_sample if s.stop else None,
            round(s.step * mult) * bytes_per_sample if s.step else None,
        ) for s in self.args.slices]
        self.args.slices = new_slices

        return super().process(data)
