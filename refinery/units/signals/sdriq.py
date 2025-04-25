import struct
from typing import ByteString, Union, Optional, Iterable, Generator

import binascii

from refinery import Unit, Arg
from refinery.lib.meta import metavars


class sdriq(Unit):
    """
    Parses the SDRIQ-header of a datastream, populating the related meta vars and outputting
    the raw signal with the header removed.
    """

    is_reversible = True
    
    def __init__(self, ignore_checksum: Arg.Switch('-i', help="ignore checksum errors")):
        super().__init__(ignore_checksum=ignore_checksum)

    @Unit.Requires('numpy', 'default', 'extended')
    def _numpy():
        import numpy
        return numpy

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        header = memoryview(data)
        data = memoryview(data)

        sample_rate, = struct.unpack("<I", data[:4])
        data = data[4:]
        center_freq, = struct.unpack("<Q", data[:8])
        data = data[8:]
        timestamp, = struct.unpack("<Q", data[:8])
        data = data[8:]
        sample_size, = struct.unpack("<I", data[:4])  # 16 or 24
        data = data[4:]
        # skip padding
        data = data[4:]
        crc32_sum, = struct.unpack("<I", data[:4])
        data = data[4:]

        computed_crc32 = binascii.crc32(header[:4+8+8+4+4])

        if not self.args.ignore_checksum and computed_crc32 != crc32_sum:
            raise RuntimeError(f"header checksum is invalid: {computed_crc32}, but header had {crc32_sum}")

        np = self._numpy
        if sample_size == 24:
            dtype = np.dtype("i4, i4")
            tmp_dtype = np.int32
        elif sample_size == 16:
            dtype = np.dtype("i2, i2")
            tmp_dtype = np.int16
        else:
            raise RuntimeError(f"unsupported sample_size {sample_size}")

        sig = np.frombuffer(data, dtype=dtype)
        # Convert from complex int to complex float
        sig = sig.view(tmp_dtype).astype(np.float32).view(np.complex64)

        return self.labelled(
            sig.tobytes(),
            sample_rate=sample_rate,
            center_freq=center_freq,
            timestamp=timestamp,
            sample_size=sample_size,
        )

    def reverse(self, data: ByteString) -> Union[Optional[ByteString], Iterable[ByteString]]:
        meta = metavars(data)
        missing_meta = {"sample_rate", "center_freq", "timestamp", "sample_size"} - set(meta.keys())
        if missing_meta:
            raise RuntimeError("missing required meta variables "+", ".join(missing_meta))

        sdriq_data = bytearray()
        sdriq_data += struct.pack("<I", meta["sample_rate"])
        sdriq_data += struct.pack("<Q", meta["center_freq"])
        sdriq_data += struct.pack("<Q", meta["timestamp"])
        sdriq_data += struct.pack("<I", meta["sample_size"])
        sdriq_data += struct.pack("<I", 0)  # padding
        sdriq_data += struct.pack("<I", binascii.crc32(sdriq_data))

        np = self._numpy

        if meta["sample_size"] == 24:
            dtype = np.int32
        elif meta["sample_size"] == 16:
            dtype = np.int16

        sig = np.frombuffer(data, dtype=np.complex64)
        # Convert back to complex int
        sig = sig.view(np.float32).astype(dtype)
        sdriq_data += sig.tobytes()

        return sdriq_data
