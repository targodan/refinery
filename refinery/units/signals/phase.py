from typing import ByteString, Union, Optional, Generator

from refinery import Unit


class phase(Unit):
    """
    Computes instantaneous phase of a complex signal.
    """

    def __init__(self):
        super().__init__()

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy

        sig = np.frombuffer(data, dtype=np.complex64)
        p = np.angle(sig)
        return self.labelled(p.tobytes(), signal_type="phase")
