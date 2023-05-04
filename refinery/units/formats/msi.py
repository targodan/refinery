#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List, Dict, NamedTuple, Union

import codecs
import collections
import enum
import json
import re
import struct

from refinery.lib.structures import StructReader
from refinery.units.formats.office.xtdoc import xtdoc, UnpackResult
from refinery.lib import chunks
from refinery.lib.types import ByteStr
from refinery.lib.mime import FileMagicInfo
from refinery.lib.tools import cached_property


class MsiType(enum.IntEnum):
    """
    Known data types for MSI table cell entries.
    """

    Long = 0x104
    Short = 0x502
    Binary = 0x900
    String = 0xD00
    StringLocalized = 0xF00
    Unknown = 0

    def __str__(self):
        return self.name


class MSITableColumnInfo(NamedTuple):
    """
    Represents information about an MSI table column. See also:
    https://doxygen.reactos.org/db/de4/msipriv_8h.html
    """
    number: int
    attributes: int

    @property
    def type(self) -> MsiType:
        try:
            if self.is_integer:
                return MsiType(self.attributes & 0xFFF)
            else:
                return MsiType(self.attributes & 0xF00)
        except Exception:
            return MsiType.Unknown

    @property
    def is_integer(self) -> bool:
        return self.attributes & 0x0F00 < 0x800

    @property
    def is_key(self) -> bool:
        return self.attributes & 0x2000 == 0x2000

    @property
    def is_nullable(self) -> bool:
        return self.attributes & 0x1000 == 0x1000

    @property
    def length(self) -> int:
        vt = self.type
        if vt is MsiType.Long:
            return 4
        if vt is MsiType.Short:
            return 2
        return self.attributes & 0xFF

    @property
    def struct_format(self) -> str:
        vt = self.type
        if vt is MsiType.Long:
            return 'I'
        elif vt is MsiType.Short:
            return 'H'
        else:
            return 'H'


class MSIStringData:
    def __init__(self, string_data: ByteStr, string_pool: ByteStr):
        data = StructReader(string_data)
        pool = StructReader(string_pool)
        self.strings: List[bytes] = []
        self.provided_ref_count: List[int] = []
        self.computed_ref_count: List[int] = []
        self.codepage = pool.u16()
        self._unknown = pool.u16()
        while not pool.eof:
            size, rc = pool.read_struct('<HH')
            string = data.read_bytes(size)
            self.strings.append(string)
            self.provided_ref_count.append(rc)
            self.computed_ref_count.append(0)

    @cached_property
    def codec(self):
        try:
            return codecs.lookup(F'cp{self.codepage}').name
        except Exception:
            xtmsi.log_info('failed looking up codec', self.codepage)
            return 'latin1'

    def __len__(self):
        return len(self.strings)

    def __iter__(self):
        yield from range(1, len(self) + 1)

    def __contains__(self, index):
        return 0 < index <= len(self)

    def ref(self, index: int, increment=True) -> Union[str, bytes]:
        assert index > 0
        index -= 1
        if increment:
            self.computed_ref_count[index] += 1
        data = self.strings[index]
        data = data.decode(self.codec)
        return data


class xtmsi(xtdoc):
    """
    Parse Microsoft Installer (MSI) files and returns the parsed information in JSON format.
    """

    # https://learn.microsoft.com/en-us/windows/win32/msi/summary-list-of-all-custom-action-types
    _CUSTOM_ACTION_TYPES = {
        0x01: 'DLL file stored in a Binary table stream.',
        0x02: 'EXE file stored in a Binary table stream.',
        0x05: 'JScript file stored in a Binary table stream.',
        0x06: 'VBScript file stored in a Binary table stream.',
        0x11: 'DLL file that is installed with a product.',
        0x12: 'EXE file that is installed with a product.',
        0x13: 'Displays a specified error message and returns failure, terminating the installation.',
        0x15: 'JScript file that is installed with a product.',
        0x16: 'VBScript file that is installed with a product.',
        0x22: 'EXE file having a path referencing a directory.',
        0x23: 'Directory set with formatted text.',
        0x25: 'JScript text stored in this sequence table.',
        0x26: 'VBScript text stored in this sequence table.',
        0x32: 'EXE file having a path specified by a property value.',
        0x33: 'Property set with formatted text.',
        0x35: 'JScript text specified by a property value.',
        0x36: 'VBScript text specified by a property value.',
    }

    def unpack(self, data):
        streams = {result.path: result for result in super().unpack(data)}

        def stream(name: str):
            return streams.pop(name).get_data()

        def column_formats(table: Dict[str, MSITableColumnInfo]) -> str:
            return ''.join(v.struct_format for v in table.values())

        def stream_to_rows(data: ByteStr, row_format: str):
            row_size = struct.calcsize(F'<{row_format}')
            row_count = int(len(data) / row_size)
            reader = StructReader(data)
            columns = [reader.read_struct(F'<{sc*row_count}') for sc in row_format]
            for i in range(row_count):
                yield [c[i] for c in columns]

        tables: Dict[str, Dict[str, MSITableColumnInfo]] = collections.defaultdict(collections.OrderedDict)
        strings = MSIStringData(stream('!_StringData'), stream('!_StringPool'))

        for tbl_name_id, col_number, col_name_id, col_attributes in stream_to_rows(stream('!_Columns'), 'HHHH'):
            tbl_name = strings.ref(tbl_name_id)
            col_name = strings.ref(col_name_id)
            tables[tbl_name][col_name] = MSITableColumnInfo(col_number, col_attributes)

        table_names_given = {strings.ref(k) for k in chunks.unpack(stream('!_Tables'), 2, False)}
        table_names_known = set(tables)

        for name in table_names_known - table_names_given:
            self.log_warn(F'table name known but not given: {name}')
        for name in table_names_given - table_names_known:
            self.log_warn(F'table name given but not known: {name}')

        processed_table_data = {}

        for table_name, table in tables.items():
            stream_name = F'!{table_name}'
            if stream_name not in streams:
                continue
            processed = []
            info = list(table.values())
            for row in stream_to_rows(stream(stream_name), column_formats(table)):
                values = []
                for index, value in enumerate(row):
                    vt = info[index].type
                    if vt is MsiType.Long:
                        if value != 0:
                            value -= 0x80000000
                    elif vt is MsiType.Short:
                        if value != 0:
                            value -= 0x8000
                    elif value in strings:
                        value = strings.ref(value)
                    elif not info[index].is_integer:
                        value = ''
                    values.append(value)

                entry = dict(zip(table, values))
                einfo = {t: i for t, i in zip(table, info)}

                if stream_name == '!MsiFileHash':
                    entry['Hash'] = struct.pack(
                        '<IIII',
                        row[2] ^ 0x80000000,
                        row[3] ^ 0x80000000,
                        row[4] ^ 0x80000000,
                        row[5] ^ 0x80000000,
                    ).hex()

                if stream_name == '!CustomAction':
                    code = row[1] & 0x3F
                    try:
                        entry['Comment'] = self._CUSTOM_ACTION_TYPES[code]
                    except LookupError:
                        pass

                processed.append(entry)

                if stream_name == '!CustomAction':
                    if code not in {0x25, 0x26, 0x33}:
                        continue
                    if einfo['Target'].is_integer:
                        continue
                    path = entry['Action']
                    data = entry['Target']
                    path = F'Action/{path}'
                    if code == 0x33:
                        meta_chars = re.finditer(r'[\x01-\x05]', data)
                        offset = max((m.end() for m in meta_chars), default=0)
                        if not offset:
                            continue
                        data = re.sub(r'\[\\(.)\]', r'\1', data[offset:])
                    else:
                        extension = {0x25: 'js', 0x26: 'vbs'}.get(code)
                        path = F'{path}.{extension}'
                    streams[path] = UnpackResult(path, data.encode(self.codec))

            processed_table_data[table_name] = processed

        for ignored_stream in [
            '[5]SummaryInformation',
            '[5]DocumentSummaryInformation',
            '[5]DigitalSignature',
            '[5]MsiDigitalSignatureEx'
        ]:
            streams.pop(ignored_stream, None)

        inconsistencies = 0
        for k in range(len(strings)):
            c = strings.computed_ref_count[k]
            p = strings.provided_ref_count[k]
            if c != p and not self.log_debug(F'string reference count computed={c} provided={p}:', strings.ref(k + 1, False)):
                inconsistencies += 1
        if inconsistencies:
            self.log_info(F'found {inconsistencies} incorrect string reference counts')

        def fix_msi_path(path: str):
            prefix, dot, name = path.partition('.')
            if dot == '.' and prefix.lower() == 'binary':
                path = F'{prefix}/{name}'
            return path

        streams = {fix_msi_path(path): item for path, item in streams.items()}
        ds = UnpackResult('MsiTables.json',
                json.dumps(processed_table_data, indent=4).encode(self.codec))
        streams[ds.path] = ds

        for path in sorted(streams):
            streams[path].path = path
            yield streams[path]

    @classmethod
    def handles(self, data: bytearray):
        if not data.startswith(B'\xD0\xCF\x11\xE0'):
            return False
        return FileMagicInfo(data).extension == 'msi'
