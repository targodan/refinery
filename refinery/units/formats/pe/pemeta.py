#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import itertools
import json
import re

from contextlib import suppress
from importlib import resources
from datetime import timedelta
from dataclasses import dataclass
from enum import Enum

from pefile import (
    DEBUG_TYPE,
    DIRECTORY_ENTRY,
    image_characteristics,
    MACHINE_TYPE,
    SUBSYSTEM_TYPE,
    PE,
)

from refinery.lib.dotnet.header import DotNetHeader
from refinery.units import Arg, Unit
from refinery.units.sinks.ppjson import ppjson
from refinery.units.formats.pe import get_pe_size
from refinery.lib.tools import date_from_timestamp

from refinery import data


class VIT(str, Enum):
    ERR = 'unknown'
    OBJ = 'object file from C'
    CPP = 'object file from C++'
    ASM = 'object file from assembler'
    RES = 'object from CVTRES'
    LNK = 'linker version'
    IMP = 'dll import in library file'
    EXP = 'dll export in library file'

    @property
    def tag(self) -> str:
        if self in (VIT.OBJ, VIT.CPP, VIT.ASM, VIT.RES):
            return 'object'
        if self is VIT.IMP:
            return 'import'
        if self is VIT.EXP:
            return 'export'
        if self is VIT.LNK:
            return 'linker'
        else:
            return 'unknown'


@dataclass
class VersionInfo:
    pid: str
    ver: str
    err: bool

    def __str__(self):
        return F'{self.ver} [{self.pid.upper()}]'

    def __bool__(self):
        return not self.err


with resources.path(data, 'rich.json') as path:
    with path.open('r') as stream:
        RICH = json.load(stream)


class ShortPID(str, Enum):
    UTC = 'STDLIB' # STDLIBC
    RES = 'CVTRES' # Cvt/RES
    OMF = 'CVTOMF' # Cvt/OMF
    PGD = 'CVTPGD' # Cvt/PGD
    LNK = 'LINKER' # Linker
    EXP = 'EXPORT' # Exports
    IMP = 'IMPORT' # Imports
    OBJ = 'OBJECT' # Object
    PHX = 'PHOENX' # Phoenix
    ASM = 'MASM'   # MASM
    MIL = 'MSIL'   # MSIL
    VB6 = 'VB6OBJ' # VB6

    def __str__(self):
        width = max(len(item.value) for item in self.__class__)
        return F'{self.value:>{width}}'


def get_rich_short_pid(pid: str) -> ShortPID:
    pid = pid.upper()
    if pid.startswith('UTC'):
        return ShortPID.UTC
    if pid.startswith('CVTRES'):
        return ShortPID.RES
    if pid.startswith('CVTOMF'):
        return ShortPID.OMF
    if pid.startswith('CVTPGD'):
        return ShortPID.PGD
    if pid.startswith('LINKER'):
        return ShortPID.LNK
    if pid.startswith('EXPORT'):
        return ShortPID.EXP
    if pid.startswith('IMPORT'):
        return ShortPID.IMP
    if pid.startswith('IMPLIB'):
        return ShortPID.IMP
    if pid.startswith('ALIASOBJ'):
        return ShortPID.OBJ
    if pid.startswith('RESOURCE'):
        return ShortPID.RES
    if pid.startswith('PHX'):
        return ShortPID.PHX
    if pid.startswith('PHOENIX'):
        return ShortPID.PHX
    if pid.startswith('MASM'):
        return ShortPID.ASM
    if pid.startswith('ILASM'):
        return ShortPID.MIL
    if pid.startswith('VISUALBASIC'):
        return ShortPID.VB6
    raise LookupError(pid)


def get_rich_info(vid: int) -> VersionInfo:
    pid = vid >> 0x10
    ver = vid & 0xFFFF
    ver = RICH['ver'].get(F'{ver:04X}')
    pid = RICH['pid'].get(F'{pid:04X}')
    err = ver is None and pid is None
    if ver is not None:
        suffix = ver.get('ver')
        ver = ver['ide']
        if suffix:
            ver = F'{ver} {suffix}'
    else:
        ver = 'Unknown Version'
    pid = pid or 'Unknown Type'
    return VersionInfo(pid, ver, err)


class pemeta(Unit):
    """
    Extract metadata from PE files. By default, all information except for imports and exports are
    extracted.
    """
    def __init__(
        self, custom : Arg('-c', '--custom',
            help='Unless enabled, all default categories will be extracted.') = False,
        debug      : Arg.Switch('-D', help='Parse the PDB path from the debug directory.') = False,
        dotnet     : Arg.Switch('-N', help='Parse the .NET header.') = False,
        signatures : Arg.Switch('-S', help='Parse digital signatures.') = False,
        timestamps : Arg.Counts('-T', help='Extract time stamps. Specify twice for more detail.') = 0,
        version    : Arg.Switch('-V', help='Parse the VERSION resource.') = False,
        header     : Arg.Switch('-H', help='Parse base data from the PE header.') = False,
        exports    : Arg.Counts('-E', help='List all exported functions. Specify twice to include addresses.') = 0,
        imports    : Arg.Counts('-I', help='List all imported functions. Specify twice to include addresses.') = 0,
        tabular    : Arg.Switch('-t', help='Print information in a table rather than as JSON') = False,
        timeraw    : Arg.Switch('-r', help='Extract time stamps as numbers instead of human-readable format.') = False,
    ):
        if not custom and not any((debug, dotnet, signatures, timestamps, version, header)):
            debug = dotnet = signatures = timestamps = version = header = True
        super().__init__(
            debug=debug,
            dotnet=dotnet,
            signatures=signatures,
            timestamps=timestamps,
            version=version,
            header=header,
            imports=imports,
            exports=exports,
            timeraw=timeraw,
            tabular=tabular,
        )

    @classmethod
    def _ensure_string(cls, x):
        if not isinstance(x, str):
            x = repr(x) if not isinstance(x, bytes) else x.decode(cls.codec, 'backslashreplace')
        return x

    @classmethod
    def _parse_pedict(cls, bin):
        return dict((
            cls._ensure_string(key),
            cls._ensure_string(val)
        ) for key, val in bin.items() if val)

    @classmethod
    def parse_signature(cls, data: bytearray) -> dict:
        """
        Extracts a JSON-serializable and human-readable dictionary with information about
        time stamp and code signing certificates that are attached to the input PE file.
        """
        from refinery.units.formats.pkcs7 import pkcs7

        try:
            signature = data | pkcs7 | json.loads
        except Exception as E:
            raise ValueError(F'PKCS7 parser failed with error: {E!s}')

        info = {}

        def find_timestamps(entry):
            if isinstance(entry, dict):
                if set(entry.keys()) == {'type', 'value'}:
                    if entry['type'] == 'signing_time':
                        return {'Timestamp': entry['value']}
                for value in entry.values():
                    result = find_timestamps(value)
                    if result is None:
                        continue
                    with suppress(KeyError):
                        result.setdefault('TimestampIssuer', entry['sid']['issuer']['common_name'])
                    return result
            elif isinstance(entry, list):
                for value in entry:
                    result = find_timestamps(value)
                    if result is None:
                        continue
                    return result

        timestamp_info = find_timestamps(signature)
        if timestamp_info is not None:
            info.update(timestamp_info)

        try:
            certificates = signature['content']['certificates']
        except KeyError:
            return info

        if len(certificates) == 1:
            main_certificate = certificates[0]
        else:
            certificates_with_extended_use = []
            main_certificate = None
            for certificate in certificates:
                with suppress(Exception):
                    crt = certificate['tbs_certificate']
                    ext = [e for e in crt['extensions'] if e['extn_id'] == 'extended_key_usage' and e['extn_value'] != ['time_stamping']]
                    key = [e for e in crt['extensions'] if e['extn_id'] == 'key_usage']
                    if ext:
                        certificates_with_extended_use.append(certificate)
                    if any('key_cert_sign' in e['extn_value'] for e in key):
                        continue
                    if any('code_signing' in e['extn_value'] for e in ext):
                        main_certificate = certificate
                        break
            if main_certificate is None and len(certificates_with_extended_use) == 1:
                main_certificate = certificates_with_extended_use[0]
        if main_certificate:
            crt = main_certificate['tbs_certificate']
            serial = crt['serial_number']
            if isinstance(serial, int):
                serial = F'{serial:x}'
            if len(serial) % 2 != 0:
                serial = F'0{serial}'
            assert bytes.fromhex(serial) in data
            subject = crt['subject']
            location = [subject.get(t, '') for t in ('locality_name', 'state_or_province_name', 'country_name')]
            info.update(Subject=subject['common_name'])
            if any(location):
                info.update(SubjectLocation=', '.join(filter(None, location)))
            for signer_info in signature['content'].get('signer_infos', ()):
                try:
                    if signer_info['sid']['serial_number'] != crt['serial_number']:
                        continue
                    for attr in signer_info['signed_attrs']:
                        if attr['type'] == 'authenticode_info':
                            info.update(ProgramName=attr['value']['programName'])
                            info.update(MoreInfo=attr['value']['moreInfo'])
                except KeyError:
                    continue
            try:
                valid_from = crt['validity']['not_before']
                valid_until = crt['validity']['not_after']
            except KeyError:
                pass
            else:
                info.update(ValidFrom=valid_from, ValidUntil=valid_until)
            info.update(
                Issuer=crt['issuer']['common_name'], Fingerprint=main_certificate['fingerprint'], Serial=serial)
            return info
        return info

    def _pe_characteristics(self, pe: PE):
        return {name for name, mask in image_characteristics
            if pe.FILE_HEADER.Characteristics & mask}

    def _pe_address_width(self, pe: PE, default=16) -> int:
        if 'IMAGE_FILE_16BIT_MACHINE' in self._pe_characteristics(pe):
            return 4
        elif MACHINE_TYPE[pe.FILE_HEADER.Machine] in ['IMAGE_FILE_MACHINE_I386']:
            return 8
        elif MACHINE_TYPE[pe.FILE_HEADER.Machine] in [
            'IMAGE_FILE_MACHINE_AMD64',
            'IMAGE_FILE_MACHINE_IA64',
        ]:
            return 16
        else:
            return default

    def _vint(self, pe: PE, value: int):
        if not self.args.tabular:
            return value
        aw = self._pe_address_width(pe)
        return F'0x{value:0{aw}X}'

    def parse_version(self, pe: PE, data=None) -> dict:
        """
        Extracts a JSON-serializable and human-readable dictionary with information about
        the version resource of an input PE file, if available.
        """
        pe.parse_data_directories(directories=[DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        string_table_entries = []
        for FileInfo in pe.FileInfo:
            for FileInfoEntry in FileInfo:
                with suppress(AttributeError):
                    for StringTableEntry in FileInfoEntry.StringTable:
                        StringTableEntryParsed = self._parse_pedict(StringTableEntry.entries)
                        with suppress(AttributeError):
                            LangID = StringTableEntry.entries.get('LangID', None) or StringTableEntry.LangID
                            LangID = int(LangID, 0x10) if not isinstance(LangID, int) else LangID
                            LangHi = LangID >> 0x10
                            LangLo = LangID & 0xFFFF
                            Language = self._LCID.get(LangHi, 'Language Neutral')
                            Charset = self._CHARSET.get(LangLo, 'Unknown Charset')
                            StringTableEntryParsed.update(
                                LangID=F'{LangID:08X}',
                                Charset=Charset,
                                Language=Language
                            )
                        for key in StringTableEntryParsed:
                            if key.endswith('Version'):
                                value = StringTableEntryParsed[key]
                                separator = ', '
                                if re.match(F'\\d+({re.escape(separator)}\\d+){{3}}', value):
                                    StringTableEntryParsed[key] = '.'.join(value.split(separator))
                        string_table_entries.append(StringTableEntryParsed)
        if not string_table_entries:
            return None
        elif len(string_table_entries) == 1:
            return string_table_entries[0]
        else:
            return string_table_entries

    def parse_exports(self, pe: PE, data=None, include_addresses=False) -> list:
        pe.parse_data_directories(directories=[DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
        base = pe.OPTIONAL_HEADER.ImageBase
        info = []
        for k, exp in enumerate(pe.DIRECTORY_ENTRY_EXPORT.symbols):
            if not exp.name:
                name = F'@{k}'
            else:
                name = exp.name.decode('ascii')
            item = {'Name': name, 'Address': self._vint(pe, exp.address + base)} if include_addresses else name
            info.append(item)
        return info

    def parse_imports(self, pe: PE, data=None, include_addresses=False) -> list:
        info = {}
        dirs = []
        for name in [
            'DIRECTORY_ENTRY_IMPORT',
            'DIRECTORY_ENTRY_DELAY_IMPORT',
        ]:
            pe.parse_data_directories(directories=[DIRECTORY_ENTRY[F'IMAGE_{name}']])
            with suppress(AttributeError):
                dirs.append(getattr(pe, name))
        self.log_warn(dirs)
        for idd in itertools.chain(*dirs):
            dll: bytes = idd.dll
            dll = dll.decode('ascii')
            if dll.lower().endswith('.dll'):
                dll = dll[:~3]
            imports: list[str] = info.setdefault(dll, [])
            with suppress(AttributeError):
                symbols = idd.imports
            with suppress(AttributeError):
                symbols = idd.entries
            try:
                for imp in symbols:
                    name: bytes = imp.name
                    name = name and name.decode('ascii') or F'@{imp.ordinal}'
                    if not include_addresses:
                        imports.append(name)
                    else:
                        imports.append(dict(Name=name, Address=self._vint(pe, imp.address)))
            except Exception as e:
                self.log_warn(F'error parsing {name}: {e!s}')
        return info

    def parse_header(self, pe: PE, data=None) -> dict:
        def format_macro_name(name: str, prefix, convert=True):
            name = name.split('_')[prefix:]
            if convert:
                for k, part in enumerate(name):
                    name[k] = part.upper() if len(part) <= 3 else part.capitalize()
            return ' '.join(name)

        major = pe.OPTIONAL_HEADER.MajorOperatingSystemVersion
        minor = pe.OPTIONAL_HEADER.MinorOperatingSystemVersion
        version = self._WINVER.get(major, {0: 'Unknown'})

        try:
            MinimumOS = version[minor]
        except LookupError:
            MinimumOS = version[0]
        header_information = {
            'Machine': format_macro_name(MACHINE_TYPE[pe.FILE_HEADER.Machine], 3, False),
            'Subsystem': format_macro_name(SUBSYSTEM_TYPE[pe.OPTIONAL_HEADER.Subsystem], 2),
            'MinimumOS': MinimumOS,
        }

        pe.parse_data_directories(directories=[
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT'],
        ])

        try:
            export_name = pe.DIRECTORY_ENTRY_EXPORT.name
            if isinstance(export_name, bytes):
                export_name = export_name.decode('utf8')
            if not export_name.isprintable():
                export_name = None
        except Exception:
            export_name = None
        if export_name:
            header_information['ExportName'] = export_name

        rich_header = pe.parse_rich_header()
        rich = []

        if rich_header:
            it = rich_header.get('values', [])
            if self.args.tabular:
                cw = max(len(F'{c:d}') for c in it[1::2])
            for idv, count in zip(it[0::2], it[1::2]):
                info = get_rich_info(idv)
                if not info:
                    continue
                pid = info.pid.upper()
                if self.args.tabular:
                    short_pid = get_rich_short_pid(pid)
                    rich.append(F'[{idv:08x}] {count:>0{cw}d} {short_pid!s} {info.ver}')
                else:
                    rich.append({
                        'Counter': count,
                        'Encoded': F'{idv:08x}',
                        'Library': pid,
                        'Product': info.ver,
                    })
            header_information['RICH'] = rich

        characteristics = self._pe_characteristics(pe)
        for typespec, flag in {
            'EXE': 'IMAGE_FILE_EXECUTABLE_IMAGE',
            'DLL': 'IMAGE_FILE_DLL',
            'SYS': 'IMAGE_FILE_SYSTEM'
        }.items():
            if flag in characteristics:
                header_information['Type'] = typespec

        base = pe.OPTIONAL_HEADER.ImageBase
        header_information['ImageBase'] = self._vint(pe, base)
        header_information['ImageSize'] = get_pe_size(pe)
        header_information['Bits'] = 4 * self._pe_address_width(pe, 16)
        header_information['EntryPoint'] = self._vint(pe, pe.OPTIONAL_HEADER.AddressOfEntryPoint + base)
        return header_information

    def parse_time_stamps(self, pe: PE, raw_time_stamps: bool, more_detail: bool) -> dict:
        """
        Extracts time stamps from the PE header (link time), as well as from the imports,
        exports, debug, and resource directory. The resource time stamp is also parsed as
        a DOS time stamp and returned as the "Delphi" time stamp.
        """
        if raw_time_stamps:
            def dt(ts): return ts
        else:
            dt = date_from_timestamp

        pe.parse_data_directories(directories=[
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT'],
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT'],
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT'],
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DEBUG'],
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']
        ])

        info = {}

        with suppress(AttributeError):
            info.update(Linker=dt(pe.FILE_HEADER.TimeDateStamp))

        for dir_name, _dll, info_key in [
            ('DIRECTORY_ENTRY_IMPORT',       'dll',  'Import'), # noqa
            ('DIRECTORY_ENTRY_DELAY_IMPORT', 'dll',  'Symbol'), # noqa
            ('DIRECTORY_ENTRY_BOUND_IMPORT', 'name', 'Module'), # noqa
        ]:
            impts = {}
            for entry in getattr(pe, dir_name, []):
                ts = 0
                with suppress(AttributeError):
                    ts = entry.struct.dwTimeDateStamp
                with suppress(AttributeError):
                    ts = entry.struct.TimeDateStamp
                if ts == 0 or ts == 0xFFFFFFFF:
                    continue
                name = getattr(entry, _dll, B'').decode()
                if name.lower().endswith('.dll'):
                    name = name[:-4]
                impts[name] = dt(ts)
            if not impts:
                continue
            if not more_detail:
                dmin = min(impts.values())
                dmax = max(impts.values())
                small_delta = 2 * 60 * 60
                if not raw_time_stamps:
                    small_delta = timedelta(seconds=small_delta)
                if dmax - dmin < small_delta:
                    impts = dmin
            info[info_key] = impts

        with suppress(AttributeError):
            Export = pe.DIRECTORY_ENTRY_EXPORT.struct.TimeDateStamp
            if Export: info.update(Export=dt(Export))

        with suppress(AttributeError):
            res_timestamp = pe.DIRECTORY_ENTRY_RESOURCE.struct.TimeDateStamp
            if res_timestamp:
                with suppress(ValueError):
                    from refinery.units.misc.datefix import datefix
                    dos = datefix.dostime(res_timestamp)
                    info.update(Delphi=dos)
                    info.update(RsrcTS=dt(res_timestamp))

        def norm(value):
            if isinstance(value, list):
                return [norm(v) for v in value]
            if isinstance(value, dict):
                return {k: norm(v) for k, v in value.items()}
            if isinstance(value, int):
                return value
            return str(value)

        return {key: norm(value) for key, value in info.items()}

    def parse_dotnet(self, pe: PE, data):
        """
        Extracts a JSON-serializable and human-readable dictionary with information about
        the .NET metadata of an input PE file.
        """
        header = DotNetHeader(data, pe=pe)
        tables = header.meta.Streams.Tables
        info = dict(
            RuntimeVersion=F'{header.head.MajorRuntimeVersion}.{header.head.MinorRuntimeVersion}',
            Version=F'{header.meta.MajorVersion}.{header.meta.MinorVersion}',
            VersionString=header.meta.VersionString
        )

        info['Flags'] = [name for name, check in header.head.KnownFlags.items() if check]

        if len(tables.Assembly) == 1:
            assembly = tables.Assembly[0]
            info.update(
                AssemblyName=assembly.Name,
                Release='{}.{}.{}.{}'.format(
                    assembly.MajorVersion,
                    assembly.MinorVersion,
                    assembly.BuildNumber,
                    assembly.RevisionNumber
                )
            )

        try:
            entry = self._vint(pe, header.head.EntryPointToken + pe.OPTIONAL_HEADER.ImageBase)
            info.update(EntryPoint=entry)
        except AttributeError:
            pass

        if len(tables.Module) == 1:
            module = tables.Module[0]
            info.update(ModuleName=module.Name)

        return info

    def parse_debug(self, pe: PE, data=None):
        result = {}
        pe.parse_data_directories(directories=[
            DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DEBUG']])
        for dbg in pe.DIRECTORY_ENTRY_DEBUG:
            if DEBUG_TYPE.get(dbg.struct.Type, None) != 'IMAGE_DEBUG_TYPE_CODEVIEW':
                continue
            with suppress(Exception):
                pdb = dbg.entry.PdbFileName
                if 0 in pdb:
                    pdb = pdb[:pdb.index(0)]
                result.update(
                    PdbPath=pdb.decode(self.codec),
                    PdbAge=dbg.entry.Age
                )
        return result

    def process(self, data):
        result = {}
        pe = PE(data=data, fast_load=True)

        for switch, resolver, name in [
            (self.args.debug,   self.parse_debug,    'Debug'),    # noqa
            (self.args.dotnet,  self.parse_dotnet,   'DotNet'),   # noqa
            (self.args.header,  self.parse_header,   'Header'),   # noqa
            (self.args.version, self.parse_version,  'Version'),  # noqa
            (self.args.imports, self.parse_imports,  'Imports'),  # noqa
            (self.args.exports, self.parse_exports,  'Exports'),  # noqa
        ]:
            if not switch:
                continue
            self.log_debug(F'parsing: {name}')
            args = pe, data
            if switch > 1:
                args = *args, True
            try:
                info = resolver(*args)
            except Exception as E:
                self.log_info(F'failed to obtain {name}: {E!s}')
                continue
            if info:
                result[name] = info

        signature = {}

        if self.args.timestamps or self.args.signatures:
            with suppress(Exception):
                from refinery.units.formats.pe.pesig import pesig
                signature = self.parse_signature(next(data | pesig))

        if self.args.timestamps:
            ts = self.parse_time_stamps(pe, self.args.timeraw, self.args.timestamps > 1)
            with suppress(KeyError):
                ts.update(Signed=signature['Timestamp'])
            result.update(TimeStamp=ts)

        if signature and self.args.signatures:
            result['Signature'] = signature

        if result:
            yield from ppjson(tabular=self.args.tabular)._pretty_output(result, indent=4, ensure_ascii=False)

    _LCID = {
        0x0C00: 'Default Custom Locale Language',
        0x1400: 'Default Custom MUI Locale Language',
        0x007F: 'Invariant Locale Language',
        0x0000: 'Neutral Locale Language',
        0x0800: 'System Default Locale Language',
        0x1000: 'Unspecified Custom Locale Language',
        0x0400: 'User Default Locale Language',
        0x0436: 'Afrikaans-South Africa',
        0x041c: 'Albanian-Albania',
        0x045e: 'Amharic-Ethiopia',
        0x0401: 'Arabic (Saudi Arabia)',
        0x1401: 'Arabic (Algeria)',
        0x3c01: 'Arabic (Bahrain)',
        0x0c01: 'Arabic (Egypt)',
        0x0801: 'Arabic (Iraq)',
        0x2c01: 'Arabic (Jordan)',
        0x3401: 'Arabic (Kuwait)',
        0x3001: 'Arabic (Lebanon)',
        0x1001: 'Arabic (Libya)',
        0x1801: 'Arabic (Morocco)',
        0x2001: 'Arabic (Oman)',
        0x4001: 'Arabic (Qatar)',
        0x2801: 'Arabic (Syria)',
        0x1c01: 'Arabic (Tunisia)',
        0x3801: 'Arabic (U.A.E.)',
        0x2401: 'Arabic (Yemen)',
        0x042b: 'Armenian-Armenia',
        0x044d: 'Assamese',
        0x082c: 'Azeri (Cyrillic)',
        0x042c: 'Azeri (Latin)',
        0x042d: 'Basque',
        0x0423: 'Belarusian',
        0x0445: 'Bengali (India)',
        0x0845: 'Bengali (Bangladesh)',
        0x141A: 'Bosnian (Bosnia/Herzegovina)',
        0x0402: 'Bulgarian',
        0x0455: 'Burmese',
        0x0403: 'Catalan',
        0x045c: 'Cherokee-United States',
        0x0804: 'Chinese (People\'s Republic of China)',
        0x1004: 'Chinese (Singapore)',
        0x0404: 'Chinese (Taiwan)',
        0x0c04: 'Chinese (Hong Kong SAR)',
        0x1404: 'Chinese (Macao SAR)',
        0x041a: 'Croatian',
        0x101a: 'Croatian (Bosnia/Herzegovina)',
        0x0405: 'Czech',
        0x0406: 'Danish',
        0x0465: 'Divehi',
        0x0413: 'Dutch-Netherlands',
        0x0813: 'Dutch-Belgium',
        0x0466: 'Edo',
        0x0409: 'English (United States)',
        0x0809: 'English (United Kingdom)',
        0x0c09: 'English (Australia)',
        0x2809: 'English (Belize)',
        0x1009: 'English (Canada)',
        0x2409: 'English (Caribbean)',
        0x3c09: 'English (Hong Kong SAR)',
        0x4009: 'English (India)',
        0x3809: 'English (Indonesia)',
        0x1809: 'English (Ireland)',
        0x2009: 'English (Jamaica)',
        0x4409: 'English (Malaysia)',
        0x1409: 'English (New Zealand)',
        0x3409: 'English (Philippines)',
        0x4809: 'English (Singapore)',
        0x1c09: 'English (South Africa)',
        0x2c09: 'English (Trinidad)',
        0x3009: 'English (Zimbabwe)',
        0x0425: 'Estonian',
        0x0438: 'Faroese',
        0x0429: 'Farsi',
        0x0464: 'Filipino',
        0x040b: 'Finnish',
        0x040c: 'French (France)',
        0x080c: 'French (Belgium)',
        0x2c0c: 'French (Cameroon)',
        0x0c0c: 'French (Canada)',
        0x240c: 'French (Democratic Rep. of Congo)',
        0x300c: 'French (Cote d\'Ivoire)',
        0x3c0c: 'French (Haiti)',
        0x140c: 'French (Luxembourg)',
        0x340c: 'French (Mali)',
        0x180c: 'French (Monaco)',
        0x380c: 'French (Morocco)',
        0xe40c: 'French (North Africa)',
        0x200c: 'French (Reunion)',
        0x280c: 'French (Senegal)',
        0x100c: 'French (Switzerland)',
        0x1c0c: 'French (West Indies)',
        0x0462: 'Frisian-Netherlands',
        0x0467: 'Fulfulde-Nigeria',
        0x042f: 'FYRO Macedonian',
        0x083c: 'Gaelic (Ireland)',
        0x043c: 'Gaelic (Scotland)',
        0x0456: 'Galician',
        0x0437: 'Georgian',
        0x0407: 'German (Germany)',
        0x0c07: 'German (Austria)',
        0x1407: 'German (Liechtenstein)',
        0x1007: 'German (Luxembourg)',
        0x0807: 'German (Switzerland)',
        0x0408: 'Greek',
        0x0474: 'Guarani-Paraguay',
        0x0447: 'Gujarati',
        0x0468: 'Hausa-Nigeria',
        0x0475: 'Hawaiian (United States)',
        0x040d: 'Hebrew',
        0x0439: 'Hindi',
        0x040e: 'Hungarian',
        0x0469: 'Ibibio-Nigeria',
        0x040f: 'Icelandic',
        0x0470: 'Igbo-Nigeria',
        0x0421: 'Indonesian',
        0x045d: 'Inuktitut',
        0x0410: 'Italian (Italy)',
        0x0810: 'Italian (Switzerland)',
        0x0411: 'Japanese',
        0x044b: 'Kannada',
        0x0471: 'Kanuri-Nigeria',
        0x0860: 'Kashmiri',
        0x0460: 'Kashmiri (Arabic)',
        0x043f: 'Kazakh',
        0x0453: 'Khmer',
        0x0457: 'Konkani',
        0x0412: 'Korean',
        0x0440: 'Kyrgyz (Cyrillic)',
        0x0454: 'Lao',
        0x0476: 'Latin',
        0x0426: 'Latvian',
        0x0427: 'Lithuanian',
        0x043e: 'Malay-Malaysia',
        0x083e: 'Malay-Brunei Darussalam',
        0x044c: 'Malayalam',
        0x043a: 'Maltese',
        0x0458: 'Manipuri',
        0x0481: 'Maori-New Zealand',
        0x044e: 'Marathi',
        0x0450: 'Mongolian (Cyrillic)',
        0x0850: 'Mongolian (Mongolian)',
        0x0461: 'Nepali',
        0x0861: 'Nepali-India',
        0x0414: 'Norwegian (Bokmål)',
        0x0814: 'Norwegian (Nynorsk)',
        0x0448: 'Oriya',
        0x0472: 'Oromo',
        0x0479: 'Papiamentu',
        0x0463: 'Pashto',
        0x0415: 'Polish',
        0x0416: 'Portuguese-Brazil',
        0x0816: 'Portuguese-Portugal',
        0x0446: 'Punjabi',
        0x0846: 'Punjabi (Pakistan)',
        0x046B: 'Quecha (Bolivia)',
        0x086B: 'Quecha (Ecuador)',
        0x0C6B: 'Quecha (Peru)',
        0x0417: 'Rhaeto-Romanic',
        0x0418: 'Romanian',
        0x0818: 'Romanian (Moldava)',
        0x0419: 'Russian',
        0x0819: 'Russian (Moldava)',
        0x043b: 'Sami (Lappish)',
        0x044f: 'Sanskrit',
        0x046c: 'Sepedi',
        0x0c1a: 'Serbian (Cyrillic)',
        0x081a: 'Serbian (Latin)',
        0x0459: 'Sindhi (India)',
        0x0859: 'Sindhi (Pakistan)',
        0x045b: 'Sinhalese-Sri Lanka',
        0x041b: 'Slovak',
        0x0424: 'Slovenian',
        0x0477: 'Somali',
        0x042e: 'Sorbian',
        0x0c0a: 'Spanish (Modern Sort)',
        0x040a: 'Spanish (Traditional Sort)',
        0x2c0a: 'Spanish (Argentina)',
        0x400a: 'Spanish (Bolivia)',
        0x340a: 'Spanish (Chile)',
        0x240a: 'Spanish (Colombia)',
        0x140a: 'Spanish (Costa Rica)',
        0x1c0a: 'Spanish (Dominican Republic)',
        0x300a: 'Spanish (Ecuador)',
        0x440a: 'Spanish (El Salvador)',
        0x100a: 'Spanish (Guatemala)',
        0x480a: 'Spanish (Honduras)',
        0x580a: 'Spanish (Latin America)',
        0x080a: 'Spanish (Mexico)',
        0x4c0a: 'Spanish (Nicaragua)',
        0x180a: 'Spanish (Panama)',
        0x3c0a: 'Spanish (Paraguay)',
        0x280a: 'Spanish (Peru)',
        0x500a: 'Spanish (Puerto Rico)',
        0x540a: 'Spanish (United States)',
        0x380a: 'Spanish (Uruguay)',
        0x200a: 'Spanish (Venezuela)',
        0x0430: 'Sutu',
        0x0441: 'Swahili',
        0x041d: 'Swedish',
        0x081d: 'Swedish-Finland',
        0x045a: 'Syriac',
        0x0428: 'Tajik',
        0x045f: 'Tamazight (Arabic)',
        0x085f: 'Tamazight (Latin)',
        0x0449: 'Tamil',
        0x0444: 'Tatar',
        0x044a: 'Telugu',
        0x041e: 'Thai',
        0x0851: 'Tibetan (Bhutan)',
        0x0451: 'Tibetan (People\'s Republic of China)',
        0x0873: 'Tigrigna (Eritrea)',
        0x0473: 'Tigrigna (Ethiopia)',
        0x0431: 'Tsonga',
        0x0432: 'Tswana',
        0x041f: 'Turkish',
        0x0442: 'Turkmen',
        0x0480: 'Uighur-China',
        0x0422: 'Ukrainian',
        0x0420: 'Urdu',
        0x0820: 'Urdu-India',
        0x0843: 'Uzbek (Cyrillic)',
        0x0443: 'Uzbek (Latin)',
        0x0433: 'Venda',
        0x042a: 'Vietnamese',
        0x0452: 'Welsh',
        0x0434: 'Xhosa',
        0x0478: 'Yi',
        0x043d: 'Yiddish',
        0x046a: 'Yoruba',
        0x0435: 'Zulu',
        0x04ff: 'HID (Human Interface DeVITe)'
    }

    _CHARSET = {
        0x0000: '7-bit ASCII',
        0x03A4: 'Japan (Shift ? JIS X-0208)',
        0x03B5: 'Korea (Shift ? KSC 5601)',
        0x03B6: 'Taiwan (Big5)',
        0x04B0: 'Unicode',
        0x04E2: 'Latin-2 (Eastern European)',
        0x04E3: 'Cyrillic',
        0x04E4: 'Multilingual',
        0x04E5: 'Greek',
        0x04E6: 'Turkish',
        0x04E7: 'Hebrew',
        0x04E8: 'Arabic',
    }

    _WINVER = {
        3: {
            0x00: 'Windows NT 3',
            0x0A: 'Windows NT 3.1',
            0x32: 'Windows NT 3.5',
            0x33: 'Windows NT 3.51',
        },
        4: {
            0x00: 'Windows 95',
            0x0A: 'Windows 98',
        },
        5: {
            0x00: 'Windows 2000',
            0x5A: 'Windows Me',
            0x01: 'Windows XP',
            0x02: 'Windows Server 2003',
        },
        6: {
            0x00: 'Windows Vista',
            0x01: 'Windows 7',
            0x02: 'Windows 8',
            0x03: 'Windows 8.1',
        },
        10: {
            0x00: 'Windows 10',
        }
    }
