from typing import ByteString, Union, Optional, Generator

import math

from refinery import Unit, Arg


class gen(Unit):
    """
    Generates a cosine signal of the given frequency.
    """

    def __init__(self, frequency: Arg.Number(help="frequency to mix with"),
                 sample_rate: Arg.Number('-r'),
                 sample_count: Arg.Number('-s', group="TIME"),
                 time: Arg('-t',type=float, group="TIME") = 0,
                 ):
        super().__init__(frequency=frequency, sample_rate=sample_rate, sample_count=sample_count, time=time)
        if self.args.time:
            self.args.sample_count = math.ceil(self.args.time * self.args.sample_rate)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    @classmethod
    def generate_signal(self, f: float, sample_rate: float, sample_count: int):
        np = self._numpy

        ampl = 1.
        t = np.linspace(0, sample_count * (1/sample_rate), sample_count, dtype=np.complex64)
        return ampl*np.exp(2j * np.pi * f * t)

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        sig = self.generate_signal(self.args.frequency, self.args.sample_rate, self.args.sample_count)
        return self.labelled(sig.tobytes(), sample_rate=self.args.sample_rate)
