#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for Cerebrum.config.parsers. """

import pytest
import tempfile
from contextlib import closing

from Cerebrum.config import parsers


@pytest.fixture
def source_data():
    return {"origin": {"x": 1,
                       "y": 2, },
            "vectors": [{"x": 5,
                         "y": 3, },
                        {"x": 0,
                         "y": -8, }], }


# parsers module tests


@pytest.yield_fixture
def invalid_parser():
    p = type('NonParser', (object, ), {'loads': None,
                                       'dumps': lambda: None,
                                       'read': lambda: None,
                                       'write': lambda: None, })
    yield p
    for k in parsers._parsers.keys():
        if parsers._parsers[k] is p:
            del parsers._parsers[k]


@pytest.yield_fixture
def valid_parser():
    p = type('Parser', (object, ), {'loads': lambda: None,
                                    'dumps': lambda: None,
                                    'read': lambda: None,
                                    'write': lambda: None, })
    name = 'asd-asd-asd'
    assert name not in parsers._parsers
    parsers._parsers[name] = p
    yield name, p
    for k in parsers._parsers.keys():
        if parsers._parsers[k] is p:
            del parsers._parsers[k]


def test_set_parser(valid_parser):
    ext, parser = valid_parser
    new_ext = ext + '_no_2'
    assert new_ext not in parsers._parsers
    parsers.set_parser(new_ext, parser)
    assert new_ext in parsers._parsers


def test_set_invalid_parser(invalid_parser):
    ext = ')(OSA=)_'
    assert ext not in parsers._parsers
    with pytest.raises(ValueError):
        parsers.set_parser(ext, invalid_parser)
    assert ext not in parsers._parsers


def test_get_parser(valid_parser):
    ext, parser = valid_parser
    fetched = parsers.get_parser('filename.' + ext)
    assert parser == fetched


def test_not_implemented_parser():
    filename = 'filename.dsa-dsa-dsaasd'
    with pytest.raises(NotImplementedError):
        parsers.get_parser(filename)


def test_abstract_parser_errors(tmpfile):
    parser = parsers._AbstractConfigParser
    for method, args in [('loads', ["string", ]),
                         ('dumps', ["string", ]),
                         ('read', [tmpfile]),
                         ('write', ["string", tmpfile])]:
        with pytest.raises(NotImplementedError):
            getattr(parser, method)(*args)


# JSON tests


@pytest.fixture
def jsondata(source_data):
    json = pytest.importorskip("json")
    return json.dumps(source_data)


def json2data(jsonstr):
    json = pytest.importorskip("json")
    return json.loads(jsonstr)


@pytest.yield_fixture
def jsonfile(jsondata):
    """ Create a temporary config file with a file reference. """
    with closing(tempfile.NamedTemporaryFile(mode='w', delete=True)) as f:
        f.write(jsondata)
        f.flush()
        yield f.name


@pytest.fixture
def jsonparser():
    try:
        return parsers.JsonParser
    except AttributeError:
        pytest.skip('No JsonParser implementation, missing json?')


def test_json_loads(jsonparser, source_data, jsondata):
    parsed = jsonparser.loads(jsondata)
    assert source_data == parsed


def test_json_dumps(jsonparser, source_data):
    dumped = jsonparser.dumps(source_data)
    assert json2data(dumped) == source_data


def test_json_read(jsonparser, source_data, jsonfile):
    parsed = jsonparser.read(jsonfile)
    assert parsed == source_data


def test_json_write(jsonparser, source_data, tmpfile):
    jsonparser.write(source_data, tmpfile)

    contents = ""
    with open(tmpfile, 'r') as f:
        contents = f.read()

    assert json2data(contents) == source_data


# YAML tests


@pytest.fixture
def yamldata(source_data):
    yaml = pytest.importorskip("yaml")
    return yaml.dump(source_data)


def yaml2data(yamlstr):
    yaml = pytest.importorskip("yaml")
    return yaml.load(yamlstr, Loader=yaml.FullLoader)


@pytest.yield_fixture
def yamlfile(yamldata):
    """ Create a temporary config file with a file reference. """
    with closing(tempfile.NamedTemporaryFile(mode='w', delete=True)) as f:
        f.write(yamldata)
        f.flush()
        yield f.name


@pytest.fixture
def yamlparser():
    try:
        return parsers.YamlParser
    except AttributeError:
        pytest.skip('No YamlParser implementation, missing PyYaml?')


def test_yaml_loads(yamlparser, source_data, yamldata):
    parsed = yamlparser.loads(yamldata)
    assert source_data == parsed


def test_yaml_dumps(yamlparser, source_data):
    dumped = yamlparser.dumps(source_data)
    assert yaml2data(dumped) == source_data


def test_yaml_read(yamlparser, source_data, yamlfile):
    parsed = yamlparser.read(yamlfile)
    assert parsed == source_data


def test_yaml_write(yamlparser, source_data, tmpfile):
    yamlparser.write(source_data, tmpfile)

    contents = ""
    with open(tmpfile, 'r') as f:
        contents = f.read()

    assert yaml2data(contents) == source_data
