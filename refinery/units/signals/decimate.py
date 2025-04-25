from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg
from refinery.lib.meta import metavars


class decimate(Unit):
    """
    Decimates a signal by the given factor.
    """

    def __init__(self, factor: Arg.Number(help="factor to decimate by")):
        super().__init__(factor=factor)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    @Unit.Requires('scipy', 'default', 'extended')
    def _scipy():
        import scipy
        return scipy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy
        scipy = self._scipy
        meta = metavars(data)

        new_sample_rate = meta.get("sample_rate", 0) // self.args.factor

        sig = np.frombuffer(data, dtype=np.complex64)
        sig = scipy.signal.decimate(sig, self.args.factor, ftype='fir')

        return self.labelled(sig.tobytes(), sample_rate=new_sample_rate)
