from typing import ByteString, Union, Optional, Generator

from refinery import Unit


class freq(Unit):
    """
    Computes instantaneous frequency of a complex signal.
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
        f = np.diff(np.unwrap(np.angle(sig)))
        return self.labelled(f.tobytes(), signal_type="frequency")
