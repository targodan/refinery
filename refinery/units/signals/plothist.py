from typing import ByteString, Union, Optional, Generator, Iterable

import math

from refinery import Unit, Arg
from refinery.lib.frame import Chunk


class plothist(Unit):
    """
    Plots the histogram of the given demodulated signal.
    Depending on the demodulation used, this can be used to show a histogram of the
    instantaneous frequency, the phase or the amplitude, etc.
    """

    def __init__(self, bins: Arg.Number(help="number of bins")):
        super().__init__(bins=bins)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    @Unit.Requires('matplotlib', 'default', 'extended')
    def _matplotlib():
        from matplotlib import pyplot
        return pyplot

    def filter(self, inputs: Iterable[Chunk]) -> Iterable[Chunk]:
        np = self._numpy
        plt = self._matplotlib

        inputs = list(inputs)
        num_inputs = len(inputs)
        n_cols = math.ceil(math.sqrt(num_inputs))
        n_rows = math.ceil(num_inputs/n_cols)

        ax = None

        for i, chunk in enumerate(inputs):
            sig = np.frombuffer(chunk, dtype=np.float32)

            ax = plt.subplot(n_rows, n_cols, i+1, sharex=ax)
            plt.hist(sig, bins=self.args.bins)

        plt.show()

        return []

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        return None

