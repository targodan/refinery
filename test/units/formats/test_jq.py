#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import textwrap
from json import JSONDecodeError

from refinery.lib.frame import Chunk
from refinery.units.formats.jq import jq
from .. import TestUnitBase


class TestJQ(TestUnitBase):

    def test_prettify_default(self):
        document = B'{"foo":{"bar":[0, 1, 2, 3],"baz": true,"b0": "Binary","b1": "Refinery"},"bar": {"bar": {"ef": 0,"eg": 1,"ep": 2}}}'

        pretty_document = textwrap.dedent('''\
        {
            "foo": {
                "bar": [
                    0,
                    1,
                    2,
                    3
                ],
                "baz": true,
                "b0": "Binary",
                "b1": "Refinery"
            },
            "bar": {
                "bar": {
                    "ef": 0,
                    "eg": 1,
                    "ep": 2
                }
            }
        }''')
        unit = self.ldu('jq')
        self.assertEqual(bytes(document | unit).decode("utf-8"), pretty_document)

    def test_sort_keys(self):
        document = B'{"key2": "value2", "bar": [1, 2], "key1": "value1"}'
        compact_document = B'{"bar": [1, 2], "key1": "value1", "key2": "value2"}'

        unit = self.ldu('jq', compact=True, sort_keys=True)
        self.assertEqual(bytes(document | unit), compact_document)

    def test_compact(self):
        document = B'{"foo":{"bar":[0, 1, 2, 3],"baz": true,"b0": "Binary","b1": "Refinery"},"bar": {"bar": {"ef": 0,"eg": 1,"ep": 2}}}'
        compact_document = B'{"foo": {"bar": [0, 1, 2, 3], "baz": true, "b0": "Binary", "b1": "Refinery"}, "bar": {"bar": {"ef": 0, "eg": 1, "ep": 2}}}'

        unit = self.ldu('jq', compact=True)
        self.assertEqual(bytes(document | unit), compact_document)

    def test_basic_filter(self):
        document = B'''
        {"foo":{"bar":["foobar", "barfoo"]}}
        '''

        unit = self.ldu('jq', filter=".foo.bar[1]")
        self.assertEqual(bytes(document | unit), B'"barfoo"')

    def test_basic_filter_raw(self):
        document = B'''
        {"foo":{"bar":["foobar", "barfoo"]}}
        '''

        unit = self.ldu('jq', filter=".foo.bar[1]", raw=True)
        self.assertEqual(bytes(document | unit), B'barfoo')

    def test_raw_on_dict(self):
        document = B'''
        {"foo": {"bar": ["foobar", "barfoo"]}}
        '''

        unit = self.ldu('jq', compact=True, raw=True)
        self.assertEqual(bytes(document | unit), B'{"foo": {"bar": ["foobar", "barfoo"]}}')

    def test_explode_list(self):
        document = B'''
        [{"doc1": 1}, {"doc2": 2}, {"doc3": 3}]
        '''

        unit = self.ldu('jq', explode=True, compact=True)
        chunks = [bytes(chunk) for chunk in document | unit]
        self.assertEqual(chunks, [B'{"doc1": 1}', B'{"doc2": 2}', B'{"doc3": 3}'])

    def test_explode_dict(self):
        document = B'''
        {"key1": "value1", "key2": "value2", "key3": "value3"}
        '''

        unit = self.ldu('jq', explode=True)
        chunks_data = [bytes(chunk) for chunk in document | unit]
        chunks_meta = [dict(chunk.meta.items()) for chunk in document | unit]
        self.assertEqual(chunks_data, [B'"value1"', B'"value2"', B'"value3"'])
        self.assertEqual(chunks_meta, [{jq.meta_key_json_key: B'key1'},
                                       {jq.meta_key_json_key: B'key2'},
                                       {jq.meta_key_json_key: B'key3'}])

    def test_explode_dict_raw(self):
        document = B'''
        {"key1": "value1", "key2": "value2", "key3": "value3"}
        '''

        unit = self.ldu('jq', explode=True, raw=True)
        chunks_data = [bytes(chunk) for chunk in document | unit]
        chunks_meta = [dict(chunk.meta.items()) for chunk in document | unit]
        self.assertEqual(chunks_data, [B'value1', B'value2', B'value3'])
        self.assertEqual(chunks_meta, [{jq.meta_key_json_key: B'key1'},
                                       {jq.meta_key_json_key: B'key2'},
                                       {jq.meta_key_json_key: B'key3'}])

    def test_empty_input(self):
        document = B''

        unit = self.ldu('jq')
        self.assertEqual(bytes(document | unit), B"")

    def test_non_json_input(self):
        document = B'some other bogus data'

        unit = self.ldu('jq')
        with self.assertRaises(JSONDecodeError):
            _ = bytes(document | unit)


class TestJSONLevel0Extractor(TestUnitBase):

    def test_basic(self):
        data = br'''
        {
            "data": "Binary Refinery!",
            "date": "2021-09-04 12:00",
            "test": true,
            "keys": [7, 1, 12, 9, 1, 4],
            "n1": "I have\nline breaks and should not be in meta",
            "n2": {
                "nope": "I am a dictionary and should not be in meta"
            },
            "n3": ["No lists", "of strings", "even when they contain numbers:", 7, 8],
            "n4": "something way too long %s"
        }''' % (B'OOM' * 200)
        unit = self.ldu('xj0', 'data')
        result: Chunk = next(data | unit)

        for k in range(4):
            self.assertNotIn(F'n{k+1}', result.meta)

        self.assertEqual(result['date'], b'2021-09-04 12:00')
        self.assertEqual(result['test'], True)
        self.assertEqual(result['keys'], [7, 1, 12, 9, 1, 4])
        self.assertEqual(result, B'Binary Refinery!')

        unit = self.ldu('xj0', 'data', raw=True)
        result: Chunk = next(data | unit)
        self.assertEqual(0, len(result.meta))

        unit = self.ldu('xj0', 'data', all=True)
        result: Chunk = next(data | unit)
        self.assertEqual(result['date'], b'2021-09-04 12:00')
        self.assertEqual(result['test'], True)
        self.assertEqual(result['keys'], [7, 1, 12, 9, 1, 4])
        self.assertEqual(result, B'Binary Refinery!')
        self.assertNotIn('n2', result.meta)
        self.assertNotIn('n3', result.meta)
        self.assertEqual(result['n1'], b'I have\nline breaks and should not be in meta')
        self.assertIn('n4', result.meta)
