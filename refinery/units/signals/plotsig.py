from typing import ByteString, Union, Optional, Generator, Iterable

import math

from refinery import Unit
from refinery.lib.frame import Chunk
from refinery.lib.meta import metavars


class plotsig(Unit):
    """
    Plots a demodulated signal.
    Depending on the demodulation used, this can be used to plot the
    instantaneous frequency, the phase or the amplitude, etc.
    """

    is_reversible = False
    
    def __init__(self):
        super().__init__()

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
            meta = metavars(chunk)
            sample_rate = meta.get("sample_rate")

            sig = np.frombuffer(chunk, dtype=np.float32)

            ax = plt.subplot(n_rows, n_cols, i+1, sharex=ax)

            ylabel = ""
            plt.title(meta.get("signal_type"))
            if meta.get("signal_type") == "frequency":
                ylabel = "Frequency [Hz]"
                if center_freq := meta.get("center_freq"):
                    sig += center_freq
            elif meta.get("signal_type") == "phase":
                plt.title("Phase")
                ylabel = "Phase [rad]"
            elif meta.get("signal_type") == "amplitude":
                plt.title("Amplitude")

            if sample_rate:
                num_samples = len(sig)
                xs = np.linspace(0., num_samples/sample_rate, num=num_samples)
                plt.plot(xs, sig)
                plt.xlabel("Time [S]")
            else:
                plt.plot(sig)
                plt.xlabel("Samples")

            plt.ylabel(ylabel)

        plt.show()

        return []

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        return None

