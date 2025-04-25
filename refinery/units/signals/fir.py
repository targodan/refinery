from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg
from refinery.lib.meta import metavars
from refinery.units.signals.gen import gen


class fir(Unit):
    """
    Applies a FIR-filter to a signal.
    """

    def __init__(self,
                 bands: Arg(type=str, nargs='+', help="cutoff frequency bands ('-2.5/2.5' means lower frequency is -2.5, upper frequency is 2.5)"),
                 taps: Arg.Number("-t", help="number of taps") = 500,
                 ):
        super().__init__(bands=bands, taps=taps)
        new_bands = []
        for band in bands:
            lower, upper = band.split("/")
            new_bands.append((float(lower), float(upper)))
        self.args.bands = new_bands

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

        sig = np.frombuffer(data, dtype=np.complex64)

        for lower, upper in self.args.bands:
            if center_freq := meta.get("center_freq"):
                lower -= center_freq
                upper -= center_freq

            half_width = (upper - lower) / 2
            shift_freq = lower + half_width

            # Based on https://dsp.stackexchange.com/questions/41361/how-to-implement-bandpass-filter-on-complex-valued-signal
            kernel = scipy.signal.firwin(self.args.taps,
                                         half_width,
                                         scale=True,
                                         pass_zero='lowpass',
                                         fs=meta["sample_rate"]).astype(np.complex64)

            shifted = sig * gen.generate_signal(-shift_freq, meta["sample_rate"], len(sig))

            yield self.labelled(np.convolve(shifted, kernel, mode='valid'), center_freq=meta.get("center_freq", 0)+shift_freq)
