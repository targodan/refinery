#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence, Optional

from refinery.units.crypto.cipher.tea import TEAUnit, TEABase, tea_block_operation, Arg
from refinery.lib.crypto import BlockCipherFactory, CipherInterface, BufferType, CipherMode


class XXTEA_ASR(TEABase):

    def __init__(
        self,
        key: BufferType,
        mode: Optional[CipherMode],
        big_endian: bool = False,
        block_size: int = TEABase.block_size
    ):
        self.block_size = block_size
        super().__init__(key, mode, big_endian)

    @tea_block_operation
    def block_encrypt(key: Sequence[int], v: Sequence[int]) -> Sequence[int]:
        n = len(v)
        s = 0
        r = 6 + 52 // n
        z = v[n - 1]
        for _ in range(r):
            s = s + 0x9E3779B9 & 0xFFFFFFFF
            e = (s >> 2) & 3
            for p in range(n):
                y = v[(p + 1) % n]
                k = (p & 3) ^ e
                x = (asr(z, 5) ^ (y << 2)) + (asr(y, 3) ^ (z << 4)) ^ (s ^ y) + (key[k] ^ z)
                z = v[p] = v[p] + x & 0xFFFFFFFF
        return v

    @tea_block_operation
    def block_decrypt(key: Sequence[int], v: Sequence[int]) -> Sequence[int]:
        n = len(v)
        r = 6 + 52 // n
        s = r * 0x9E3779B9 & 0xFFFFFFFF
        y = v[0]
        for _ in range(r):
            e = (s >> 2) & 3
            for p in range(n - 1, -1, -1):
                z = v[(p - 1) % n]
                k = (p & 3) ^ e
                x = (asr(z, 5) ^ (y << 2)) + (asr(y, 3) ^ (z << 4)) ^ (s ^ y) + (key[k] ^ z)
                y = v[p] = v[p] - x & 0xFFFFFFFF
            s = s - 0x9E3779B9 & 0xFFFFFFFF
        return v


class xxtea_asr(TEAUnit, cipher=BlockCipherFactory(XXTEA_ASR)):

    block_size: int = 8

    def __init__(
        self, key, iv=b'', padding=None, mode=None, raw=False, swap=False,
        block_size: Arg.Number('-b', help=(
            'Cipher block size in 32-bit words. The default value {default} implies that the input '
            'is treated as a single block, which is common behaviour of many implementations.')) = 1
    ):
        super().__init__(key, iv, padding, mode, raw, swap=swap, block_size=block_size)

    def _prepare_block(self, data: bytes):
        if self.args.block_size < 2:
            blocks, remainder = divmod(len(data), 4)
            if remainder:
                blocks += 1
            self.block_size = blocks * 4
        else:
            self.block_size = self.args.block_size * 4

    def encrypt(self, data: bytes) -> bytes:
        self._prepare_block(data)
        return super().encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        self._prepare_block(data)
        return super().decrypt(data)

    def _new_cipher(self, **optionals) -> CipherInterface:
        return super()._new_cipher(block_size=self.block_size, **optionals)


def asr(value, shift):
    """
    Source: https://blog.xlab.qianxin.com/long-live-the-vo1d_botnet/#34-mzmess-plugins
    Perform an arithmetic shift right (ASR) operation.
    :param value: The signed 32-bit integer (treated as 32-bit)
    :param shift: The number of positions to shift.
    :return: The result of the arithmetic shift right.
    """
    if value & 0x80000000:  # Check if MSB is set (negative number)
        return (value >> shift) | (0xFFFFFFFF << (32 - shift)) & 0xFFFFFFFF
    else:
        return value >> shift