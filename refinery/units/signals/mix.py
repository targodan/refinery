from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg
from refinery.lib.meta import metavars
from refinery.units.signals.gen import gen


class mix(Unit):
    """
    Mixes the input signal with a cosine signal of the given frequency.
    This effectively shifts the input signal by the given frequency.
    """

    def __init__(self, frequency: Arg.Number(help="frequency to mix with")):
        super().__init__(frequency=frequency)

    @Unit.Requires('numpy', optional=False)
    def _numpy():
        import numpy
        return numpy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy

        sig = np.frombuffer(data, dtype=np.complex64)

        meta = metavars(data)
        generated = gen.generate_signal(self.args.frequency, meta["sample_rate"], len(sig))

        return self.labelled((sig * generated).tobytes(), center_freq=meta.get("center_freq", 0)-self.args.frequency)
