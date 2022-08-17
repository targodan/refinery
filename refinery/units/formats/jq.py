import json

import jq as _jq

from refinery import Unit, Arg


class jq(Unit):
    """
    This unit is a thin wrapper around the tool `jq`, with some adjustments to fit the binref-principles.
    Each input chunk is processed individually, but completely. Meaning, each chunk is processed as
    if you used the --slurp flag of the standard jq-command.
    """

    def __init__(self,
                 raw: Arg.Switch("-r", help="output raw data rather than json-encoded data"),
                 sort_keys: Arg.Switch("-s", help="sort keys"),
                 compact: Arg.Switch("-c", help="output compact json, rather than pretty printing"),
                 explode: Arg.Switch("-e", help="output one chunk per array-item or per object-key"),
                 filter: Arg(help="jq compatible filter") = b"."):
        super().__init__(raw=raw, sort_keys=sort_keys, compact=compact, explode=explode, filter=filter)

    def process(self, data: bytearray):
        if not data:
            return data

        parsed = json.loads(data)
        for obj in _jq.compile(self.args.filter.decode(self.codec)).input(parsed):
            yield from self._chunk_and_format_data(obj)

    def _chunk_and_format_data(self, data):
        if self.args.explode:
            if isinstance(data, list):
                yield from (self.format_json(chunk) for chunk in data)
            elif isinstance(data, dict):
                yield from self._chunk_and_format_dict(data)
        else:
            yield self.format_json(data)

    def _chunk_and_format_dict(self, data: dict):
        for key, value in data.items():
            yield self.labelled(self.format_json(value), json_key=key)

    def format_json(self, data) -> bytes:
        if self.args.raw:
            return self._format_json_raw(data)
        else:
            return self._format_json_dumps(data)

    def _format_json_raw(self, data) -> bytes:
        if isinstance(data, (list, dict)):
            # This mimics the behaviour of the upstream jq-cli
            return self._format_json_dumps(data)
        return str(data).encode(self.codec)

    def _format_json_dumps(self, data) -> bytes:
        kwargs = {}
        if self.args.sort_keys:
            kwargs["sort_keys"] = True
        if not self.args.compact:
            kwargs["indent"] = 4
        return json.dumps(data, **kwargs).encode(self.codec)
