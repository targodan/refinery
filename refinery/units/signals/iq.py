from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg

DTYPES = ["c64", "c128", "ci32", "ci48", "ci64"]


class iq(Unit):
    """
    Converts various complex input signals to the binref-standard 64-bit-complex-float signal.
    Supported formats are 64-bit-complex-float ("c64"), 128-bit-complex-float ("c128"), 32-bit-complex-signed-int ("ci32"),
    48-bit-complex-signed-int ("ci48") or 64-bit-complex-signed-int ("ci64").
    """

    def __init__(self, dtype: Arg.Choice(choices=DTYPES)):
        super().__init__(dtype=dtype)

    @Unit.Requires('numpy', optional=False)
    def _numpy():
        import numpy
        return numpy

    def _read_data(self, data: ByteString):
        np = self._numpy
        dtype = {
            "c64": np.complex64,
            "c128": np.complex128,
            "ci32": np.dtype("i2, i2"),
            "ci48": np.dtype("i4, i4"),
            "ci64": np.dtype("i4, i4"),
        }[self.args.dtype]

        return np.frombuffer(data, dtype=dtype)

    def _to_complex64(self, sig):
        np = self._numpy
        if self.args.dtype == "c64":
            return sig
        elif self.args.dtype == "c128":
            return sig.astype(np.complex64)
        elif self.args.dtype == "ci32":
            return sig.view(np.int16).astype(np.float32).view(np.complex64)
        elif self.args.dtype == "ci48":
            return sig.view(np.int32).astype(np.float32).view(np.complex64)
        elif self.args.dtype == "ci64":
            return sig.view(np.int32).astype(np.float32).view(np.complex64)
        raise IndexError("invalid dtype")  # this should never happen

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        sig = self._read_data(data)
        sig = self._to_complex64(sig)

        return sig.tobytes()
