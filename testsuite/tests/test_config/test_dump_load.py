#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for configuration. """
import pytest
import tempfile
import os
from contextlib import closing

from Cerebrum.config.configuration import Configuration
from Cerebrum.config.configuration import ConfigDescriptor
from Cerebrum.config.configuration import Namespace
from Cerebrum.config.settings import Numeric
from Cerebrum.config.settings import Iterable


@pytest.fixture
def coordinate_cls():
    """ An example (x, y) coordinate class. """

    class Coordinate(Configuration):

        x = ConfigDescriptor(
            Numeric,
            minval=-10,
            maxval=10)

        y = ConfigDescriptor(
            Numeric,
            minval=-10,
            maxval=10)

    return Coordinate


@pytest.fixture
def vectors_cls(coordinate_cls):
    """ An example class with vectors with a shared origin. """

    class Vectors(Configuration):

        origin = ConfigDescriptor(
            Namespace,
            config=coordinate_cls)

        vectors = ConfigDescriptor(
            Iterable,
            default=[],
            setting=Namespace(config=coordinate_cls))

    return Vectors


@pytest.fixture
def empty(vectors_cls):
    return vectors_cls()


@pytest.fixture
def config(vectors_cls):
    config = vectors_cls()
    config.origin.x = 0
    config.origin.y = 0
    config.vectors = [
        {'x': 1, 'y': 1},
        {'x': 1, 'y': -1},
        {'x': 2, 'y': -3}, ]
    return config


@pytest.yield_fixture
def touch_file():
    fd, name = tempfile.mkstemp()
    os.close(fd)
    yield name
    os.unlink(name)


# JSON tests

@pytest.fixture
def jsondata():
    return """{
    "origin": {
        "x": 1,
        "y": 2
    },
    "vectors": [
        {
            "x": 5,
            "y": 3
        },
        {
            "x": 0,
            "y": -8
        }
    ]
}"""


@pytest.yield_fixture
def jsonfile(jsondata):
    """ Create a temporary config file with a file reference. """
    with closing(tempfile.NamedTemporaryFile(mode='w', delete=True)) as f:
        f.write(jsondata)
        f.flush()
        yield f.name


def test_load_json_data(config, jsondata):
    config.load_json(jsondata)
    assert config['origin.x'] == 1
    assert config['origin.y'] == 2
    assert len(config['vectors']) == 2
    for item in config['vectors']:
        if item.x == 5:
            assert item.y == 3
        elif item.x == 0:
            assert item.y == -8
        else:
            assert False


def test_dump_json_data(config, empty):
    jsonstr = config.dump_json()
    assert '"origin":' in jsonstr
    assert '"x":' in jsonstr

    empty.load_json(jsonstr)
    assert config == empty


def test_dump_json_data_flat(config, empty):
    jsonstr = config.dump_json(flatten=True)
    assert '"origin.x":' in jsonstr

    empty.load_json(jsonstr)
    assert config == empty


def test_load_json_file(config, jsonfile):
    config.read_json(jsonfile)
    assert config['origin.x'] == 1
    assert config['origin.y'] == 2
    assert len(config['vectors']) == 2
    for item in config['vectors']:
        if item.x == 5:
            assert item.y == 3
        elif item.x == 0:
            assert item.y == -8
        else:
            assert False


def test_dump_json_file(config, empty, touch_file):
    config.write_json(touch_file)
    empty.read_json(touch_file)
    assert empty['origin.x'] == 0
    assert empty['origin.y'] == 0
    assert len(empty['vectors']) == 3


# YAML tests

@pytest.fixture
def yamldata():
    return """
origin:
    x: 1
    y: 2
vectors:
  - x: 5
    y: 3
  - x: 0
    y: -8
"""


@pytest.yield_fixture
def yamlfile(yamldata):
    """ Create a temporary config file with a file reference. """
    with closing(tempfile.NamedTemporaryFile(mode='w', delete=True)) as f:
        f.write(yamldata)
        f.flush()
        yield f.name


def test_load_yaml_data(config, yamldata):
    config.load_yaml(yamldata)
    assert config['origin.x'] == 1
    assert config['origin.y'] == 2
    assert len(config['vectors']) == 2
    for item in config['vectors']:
        if item.x == 5:
            assert item.y == 3
        elif item.x == 0:
            assert item.y == -8
        else:
            assert False


def test_dump_yaml_data(config, empty):
    yamlstr = config.dump_yaml()
    assert 'origin:' in yamlstr
    assert 'x:' in yamlstr

    empty.load_yaml(yamlstr)
    assert config == empty


def test_dump_yaml_data_flat(config, empty):
    yamlstr = config.dump_yaml(flatten=True)
    assert 'origin.x:' in yamlstr

    empty.load_yaml(yamlstr)
    assert config == empty


def test_load_yaml_file(config, yamlfile):
    config.read_yaml(yamlfile)
    assert config['origin.x'] == 1
    assert config['origin.y'] == 2
    assert len(config['vectors']) == 2
    for item in config['vectors']:
        if item.x == 5:
            assert item.y == 3
        elif item.x == 0:
            assert item.y == -8
        else:
            assert False


def test_dump_yaml_file(config, empty, touch_file):
    config.write_yaml(touch_file)
    empty.read_yaml(touch_file)
    assert empty['origin.x'] == 0
    assert empty['origin.y'] == 0
    assert len(empty['vectors']) == 3
