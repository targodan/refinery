#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import TYPE_CHECKING, Container

from refinery.units import Arg, Unit
from refinery.lib.executable import Range, Executable, CompartmentNotFound
from refinery.lib.tools import NoLogging


if TYPE_CHECKING:
    from smda.common.SmdaFunction import SmdaFunction


class vmemref(Unit):
    """
    The unit expects an executable as input (PE/ELF/MachO) and scans a function at a given virtual
    address for memory references. For each memory reference, the unit looks up the corresponding
    section and file offset for the reference. It then returns all data from that section starting
    at the given offset.
    """

    @Unit.Requires('smda', 'all')
    def _smda():
        import smda
        import smda.Disassembler
        import smda.DisassemblyResult
        return smda

    def _memory_references(
        self,
        exe: Executable,
        function: SmdaFunction,
        codes: Container[Range],
        max_dereference: int = 1
    ):
        def is_valid_data_address(address):
            if not isinstance(address, int):
                return False
            if address not in exe:
                return False
            if address in instructions:
                return False
            for code in codes:
                if address in code:
                    return False
            return True

        def dereference(address):
            return int.from_bytes(exe[address:address + pointer_size], exe.byte_order().value)

        pointer_size = exe.pointer_size // 8
        instructions = {op.offset for op in function.getInstructions()}

        references = set()

        for op in function.getInstructions():
            try:
                refs = list(op.getDataRefs())
            except Exception:
                continue
            for address in refs:
                try:
                    address = int(address)
                except Exception:
                    continue
                times_dereferenced = 0
                while is_valid_data_address(address) and address not in references:
                    references.add(address)
                    times_dereferenced += 1
                    if max_dereference and max_dereference > 0 and times_dereferenced > max_dereference:
                        break
                    try:
                        address = dereference(address)
                    except Exception:
                        break

        return references

    def __init__(
        self,
        *address: Arg.Number(metavar='ADDR', help=(
            'Specify the address of a function to scan. If no argument is given, the unit will scan'
            ' all functions for memory references.')),
        take: Arg.Number('-t', metavar='SIZE', help=(
            'Optionally specify the number of bytes to read from each reference; by default, all '
            'data until the end of the section is returned.')) = None,
        base: Arg.Number('-b', metavar='ADDR',
            help='Optionally specify a custom base address B.') = None,
    ):
        super().__init__(address=address, take=take, base=base)

    def process(self, data):
        smda = self._smda
        take = self.args.take
        exe = Executable.Load(data, self.args.base)
        fmt = exe.pointer_size // 4
        addresses = self.args.address

        self.log_info(R'disassembling and exploring call graph using smda')
        with NoLogging():
            cfg = smda.Disassembler.SmdaConfig()
            cfg.CALCULATE_SCC = False
            cfg.CALCULATE_NESTING = False
            cfg.TIMEOUT = 600
            dsm = smda.Disassembler.Disassembler(cfg)
            _input = data
            if not isinstance(_input, bytes):
                _input = bytes(data)
            graph = dsm.disassembleUnmappedBuffer(_input)

        self.log_info('collecting code addresses for memory reference exclusion list')
        visits = set()
        avoid = set()

        for symbol in exe.symbols():
            if not symbol.code:
                continue
            avoid.add(exe.location_from_address(symbol.address).virtual.box)

        if addresses:
            reset = visits.clear
        else:
            def reset(): pass
            self.log_info('scanning executable for functions')
            with NoLogging():
                addresses = [pfn.offset for pfn in graph.getFunctions()]
                addresses.sort()

        for a in addresses:
            reset()
            address, function = min(graph.xcfg.items(), key=lambda t: (t[0] >= a, abs(t[0] - a)))
            self.log_debug(F'scanning function: 0x{address:0{fmt}X}')
            refs = list(self._memory_references(exe, function, avoid))
            refs.sort(reverse=True)
            last_start = None
            for ref in refs:
                if ref in visits:
                    continue
                visits.add(ref)
                try:
                    box = exe.location_from_address(ref)
                    end = box.physical.box.upper
                    if take is not None:
                        end = min(ref + take, end)
                    if last_start is not None:
                        end = min(last_start, end)
                    last_start = box.physical.position
                except CompartmentNotFound:
                    self.log_info(F'memory reference could not be resolved: 0x{ref:0{fmt}X}')
                else:
                    yield exe.data[last_start:end]
