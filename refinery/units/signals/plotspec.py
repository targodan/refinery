from typing import ByteString, Union, Optional, Generator, Iterable

import math

from refinery import Unit, Arg
from refinery.lib.frame import Chunk
from refinery.lib.meta import metavars

windows = [
    "boxcar", "triang", "blackman", "hamming", "hann", "bartlett", "flattop", "parzen", "bohman", "blackmanharris",
    "nuttall", "barthann",
]


class plotspec(Unit):
    """
    Plots the spectrum of a complex singal.
    """

    def __init__(self,
                 mode: Arg.Choice('-m', choices=["periodogram", "welch"]) = "periodogram",
                 window: Arg.Choice('-w', choices=windows) = "blackmanharris"):
        super().__init__(mode=mode, window=window)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    @Unit.Requires('scipy', 'default', 'extended')
    def _scipy():
        import scipy
        return scipy

    @Unit.Requires('matplotlib', 'default', 'extended')
    def _matplotlib():
        from matplotlib import pyplot
        return pyplot

    def filter(self, inputs: Iterable[Chunk]) -> Iterable[Chunk]:
        np = self._numpy
        scipy = self._scipy
        plt = self._matplotlib

        inputs = list(inputs)
        num_inputs = len(inputs)
        n_cols = math.ceil(math.sqrt(num_inputs))
        n_rows = math.ceil(num_inputs/n_cols)

        ax = None

        for i, chunk in enumerate(inputs):
            meta = metavars(chunk)
            sig = np.frombuffer(chunk, dtype=np.complex64)

            if self.args.mode == "periodogram":
                f, power = scipy.signal.periodogram(sig,
                                                    meta["sample_rate"],
                                                    self.args.window,
                                                    return_onesided=False,
                                                    scaling='spectrum')

                ax = plt.subplot(n_rows, n_cols, i+1, sharex=ax)
            elif self.args.mode == "welch":
                f, power = scipy.signal.welch(sig,
                                              meta["sample_rate"],
                                              scaling='spectrum',
                                              return_onesided=False,
                                              window=self.args.window)

                ax = plt.subplot(n_rows, n_cols, i+1, sharex=ax)
            else:
                raise ValueError("invalid mode")  # should never happen

            if center_freq := meta.get("center_freq"):
                f += center_freq

            plt.semilogy(f, power)
            plt.xlabel('Frequency [Hz]')
            plt.ylabel('PSD [V**2]')

        plt.grid()
        plt.show()

        return []

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        return None

