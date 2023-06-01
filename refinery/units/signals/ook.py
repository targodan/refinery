import struct
from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg


class ook(Unit):
    """
    Performs n-OOK (on off keying) decoding of the *already demodulated* signal.
    """

    def __init__(self,
                 codewords: Arg.Binary(nargs="+", help="Codewords to use for the thresholds."),
                 thresholds: Arg.NumSeq('-t', help="Thresholds to distinguish states."),
                 slice: Arg('-s', help="slice the pulses before decoding") = slice(None),
                 ):
        super().__init__(thresholds=thresholds, codewords=codewords, slice=slice)

    @Unit.Requires('numpy', optional=False)
    def _numpy():
        import numpy
        return numpy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy

        sig = np.frombuffer(data, dtype=np.float32)

        if not self.args.codewords:
            self.args.codewords = [struct.pack("B", i) for i in range(len(self.args.thresholds)+1)]

        if self.args.slice:
            sig = sig[self.args.slice]

        data = np.zeros(len(sig), dtype=bytes)
        data[np.where(sig < self.args.thresholds[0])] = self.args.codewords[0]
        for i in range(len(self.args.thresholds)-1):
            lower, upper = self.args.thresholds[i], self.args.thresholds[i+1]
            data[np.where(np.logical_and(lower < sig, sig < upper))] = self.args.codewords[i+1]
        data[np.where(self.args.thresholds[-1] < sig)] = self.args.codewords[-1]

        return data.tobytes()
