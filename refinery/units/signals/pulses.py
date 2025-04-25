from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg


class pulses(Unit):
    """
    Computes the width of each continuous pulse in a demodulated signal.
    This can be used to further demodulate signals, which encode codewords as pulse width.
    """

    def __init__(self,
                 threshold: Arg.Number('-t', help="Threshold to distinguish HI from LO, guessed by default") = None,
                 keep: Arg.Choice('-k', choices=["hi", "lo", "both"]) = "both",
                 ):
        super().__init__(threshold=threshold, keep=keep)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    @Unit.Requires('matplotlib', 'default', 'extended')
    def _matplotlib():
        from matplotlib import pyplot
        return pyplot

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        np = self._numpy

        sig = np.frombuffer(data, dtype=np.float32)

        if not self.args.threshold:
            self.args.threshold = 0.5 * np.max(sig) - 1.5 * np.min(sig)

        sig = (sig > self.args.threshold).astype(np.int32)
        difference_between_consecutive_elements = np.diff(sig)
        indexes_of_edges = np.where(difference_between_consecutive_elements != 0)[0]+1
        runs = np.split(sig, indexes_of_edges)
        pulse_lengths = np.array([len(r) for r in runs], dtype=np.float32)

        if self.args.keep == "hi":
            start = 0 if sig[0] >= self.args.threshold else 1
        else:
            start = 0 if sig[0] < self.args.threshold else 1

        if self.args.keep != "both":
            pulse_lengths = pulse_lengths[start::2]

        return pulse_lengths.tobytes()
