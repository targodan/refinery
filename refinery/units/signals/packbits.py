import struct
from typing import ByteString, Union, Optional, Generator

from refinery import Unit, Arg


class packbits(Unit):
    """
    Packs codewords with bit_width number of bits per codeword.
    Turns [0, 1, 0, 1] into [0b0101] (assuming bit_width=1, bit_order=msb).
    If specified, any codeword given as argument will be left untouched. This is useful for word-separating
    special codewords.
    """

    def __init__(self,
                 specials: Arg.Binary(nargs='*', help="special values which will not be packed but stay as bytes"),
                 bit_width: Arg.Number('-w', help="number of bits per codeword") = 1,
                 bit_order: Arg.Choice('-o', choices=["msb", "lsb"]) = "msb",
                 ):
        super().__init__(special_values=specials, bit_width=bit_width, bit_order=bit_order)
        if bit_width not in (1, 2, 4):
            raise ValueError("unsupported bit width, can't be asked to figure out the maths right now")
        if bit_width < 1 or bit_width > 7:
            raise ValueError("unsupported bit width")
        self.args.special_values = [struct.unpack("B", s)[0] for s in self.args.special_values]

    def _shifted_bits(self, i: int, b: int) -> int:
        if self.args.bit_order == "lsb":
            return b << i
        elif self.args.bit_order == "msb":
            return b << (8-self.args.bit_width-i)

    def process(self, data: ByteString) -> Union[Optional[ByteString], Generator[ByteString, None, None]]:
        num_inputs_per_output = 8 // self.args.bit_width

        out = bytearray()
        current = 0
        current_started = False

        i_in_byte = 0
        i = 0
        while i < len(data):
            for j in range(num_inputs_per_output):
                if i >= len(data):
                    break
                b = data[i]

                if b in self.args.special_values:
                    if current_started:
                        # TODO Warn
                        out += struct.pack("B", current)
                        current = 0
                        current_started = False
                        i_in_byte = 0
                    out += struct.pack("B", b)
                else:
                    current_started = True
                    current |= self._shifted_bits(i_in_byte, b)
                    old_i_in_byte = i_in_byte
                    i_in_byte = (i_in_byte + self.args.bit_width) % 8

                    if i_in_byte < old_i_in_byte:
                        out += struct.pack("B", current)
                        current = 0
                        current_started = False

                i += 1

        return out
