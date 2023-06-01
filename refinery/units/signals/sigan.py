from typing import ByteString, Union, Optional, Generator

from refinery import Unit


class sigan(Unit):
    """
    Computes instantaneous frequency, phase and amplitude in separate chunks.
    This is particularly useful in combination with the `plotsig` or `plothist` units
    for a quick look at the signal.
    """

    def __init__(self):
        super().__init__()

    @Unit.Requires('numpy', optional=False)
    def _numpy():
        import numpy
        return numpy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy

        sig = np.frombuffer(data, dtype=np.complex64)
        a = np.abs(sig)
        yield self.labelled(a.tobytes(), signal_type="amplitude")
        p = np.angle(sig)
        yield self.labelled(p.tobytes(), signal_type="phase")
        f = np.diff(np.unwrap(p))
        yield self.labelled(f.tobytes(), signal_type="frequency")
