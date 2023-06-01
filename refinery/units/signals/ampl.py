from typing import ByteString, Union, Optional, Generator

from refinery import Unit


class ampl(Unit):
    """
    Computes the amplitude of a signal of a complex signal.
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
        return self.labelled(a.tobytes(), signal_type="amplitude")
