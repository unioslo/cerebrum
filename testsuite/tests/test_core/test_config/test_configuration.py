#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for configuration. """
import pytest
from collections import OrderedDict

from Cerebrum.config.errors import ConfigurationError
from Cerebrum.config.configuration import flatten_dict
from Cerebrum.config.configuration import Configuration
from Cerebrum.config.configuration import ConfigDescriptor
from Cerebrum.config.configuration import Namespace
from Cerebrum.config.settings import String
from Cerebrum.config.settings import Numeric
from Cerebrum.config.settings import NotSet


def test_flatten():
    d = {'foo': 1,
         'bar': {'foo': 2,
                 'bar': {'foo': 3,
                         'baz': 4, },
                 'baz': 5, },
         'baz': {'foo': 6}, }
    flat = OrderedDict(flatten_dict(d))
    assert len(flat) == 6
    assert flat['foo'] == 1
    assert flat['bar.bar.baz'] == 4
    assert flat['baz.foo'] == 6
    assert 'bar.foo' in flat
    assert 'baz.foo' in flat
    assert 'bar.bar.foo' in flat
    assert flat.keys() == sorted(flat.keys())


@pytest.fixture
def empty_config():
    return Configuration()


@pytest.fixture
def group_cls():
    class ExampleGroup(Configuration):
        item_a = ConfigDescriptor(String, doc="First item")
        item_b = ConfigDescriptor(String, doc="Second item")
    return ExampleGroup


@pytest.fixture
def config_cls(group_cls):
    class Example(Configuration):
        foo = ConfigDescriptor(Numeric, doc="Some foo value")
        bar = ConfigDescriptor(String, doc="Some bar value")
        group = ConfigDescriptor(Namespace, config=group_cls, doc="group")
    return Example


@pytest.fixture
def config_inst(config_cls):
    c = config_cls()
    c['foo'] = 1
    c['bar'] = 'example'
    c['group.item_a'] = 'a'
    c['group.item_b'] = 'b'
    return c


def test_len(empty_config, group_cls, config_inst):
    group = group_cls()
    assert len(empty_config) == 0
    assert len(group) == 2
    assert len(config_inst) == 3


def test_empty(empty_config):
    assert not empty_config


def test_nonempty(group_cls, config_inst):
    assert group_cls()
    assert config_inst


def test_in(config_cls, config_inst):
    example = config_cls()
    assert 'foo' in example
    assert 'foo' in config_inst
    assert 'group.item_a' in example
    assert 'group.item_a' in config_inst


def test_not_in(empty_config):
    assert 'foo' not in empty_config
    assert 'foo.bar' not in empty_config
    assert '' not in empty_config
    assert '.' not in empty_config
    assert '_' not in empty_config
    assert '_.foo' not in empty_config


def test_get_item(config_inst):
    assert config_inst['foo'] == 1
    assert config_inst['bar'] == 'example'
    assert config_inst['group.item_a'] == 'a'
    assert config_inst['group']['item_a'] == 'a'


def test_get_attr(config_inst):
    assert config_inst.foo == 1
    assert config_inst.group.item_b == 'b'


def test_set_item(config_cls):
    example = config_cls()
    example['foo'] = 2
    example['bar'] = 'bar'
    example['group']['item_a'] = 'c'
    assert example['foo'] == 2
    assert example['bar'] == 'bar'
    assert example['group.item_a'] == 'c'


def test_set_attr(config_cls):
    example = config_cls()
    example.foo = 2
    example.bar = 'bar'
    example.group.item_a = 'c'
    assert example['foo'] == 2
    assert example['bar'] == 'bar'
    assert example['group.item_a'] == 'c'


def test_del_item(config_inst):
    del config_inst['foo']
    assert config_inst['foo'] is NotSet


def test_del_attr(config_inst):
    del config_inst.foo
    assert config_inst['foo'] is NotSet


def test_get_group_item(config_inst, group_cls):
    group = config_inst['group']
    assert isinstance(group, group_cls)
    assert group['item_a'] == 'a'


def test_get_group_attr(config_inst, group_cls):
    group = config_inst.group
    assert isinstance(group, group_cls)
    assert group.item_a == 'a'


@pytest.fixture
def group_inst(group_cls):
    g = group_cls()
    g.item_a = 'Foo'
    g.item_b = 'Bar'
    return g


def test_set_group_item(config_inst, group_inst):
    config_inst['group'] = group_inst
    assert config_inst.foo == 1
    assert config_inst.group.item_a == 'Foo'
    assert config_inst.group.item_b == 'Bar'


def test_set_group_attr(config_inst, group_inst):
    config_inst.group = group_inst
    assert config_inst.foo == 1
    assert config_inst.group.item_a == 'Foo'
    assert config_inst.group.item_b == 'Bar'


def test_del_group_item(config_inst):
    del config_inst['group']
    assert config_inst.foo == 1
    assert config_inst.group.item_a == NotSet
    assert config_inst.group.item_b == NotSet


def test_del_group_attr(config_inst):
    del config_inst.group
    assert config_inst.foo == 1
    assert config_inst.group.item_a == NotSet
    assert config_inst.group.item_b == NotSet


def test_del_item_from_group(config_inst):
    del config_inst['group.item_a']
    assert config_inst.foo == 1
    assert config_inst.group.item_a == NotSet
    assert config_inst.group.item_b == 'b'


def test_del_attr_from_group(config_inst):
    del config_inst.group.item_a
    assert config_inst.foo == 1
    assert config_inst.group.item_a == NotSet
    assert config_inst.group.item_b == 'b'


def test_error_missing_item(empty_config):
    with pytest.raises(KeyError):
        empty_config['foo']


def test_error_missing_attr(empty_config):
    with pytest.raises(AttributeError):
        empty_config.foo


def test_error_missing_group_item(empty_config):
    with pytest.raises(KeyError):
        empty_config['foo.bar']


def test_error_missing_group_attr(empty_config):
    with pytest.raises(AttributeError):
        empty_config.foo.bar


def test_error_get_missing_item_from_group(config_inst):
    with pytest.raises(KeyError):
        config_inst['group.non_existing_item']


def test_error_get_missing_attr_from_group(config_inst):
    with pytest.raises(AttributeError):
        config_inst.group.non_existing_item


def test_error_set_nonstr_item_name(empty_config):
    with pytest.raises(TypeError):
        empty_config[1] = 'foo'


def test_error_use_group_as_item(config_inst):
    with pytest.raises(TypeError):
        config_inst['group'] = 1


def test_error_use_item_as_group(config_inst, group_cls):
    group = group_cls()
    with pytest.raises(TypeError):
        config_inst['foo'] = group


def test_error_use_attr_as_group(empty_config):
    empty_config.non_group = 2
    with pytest.raises(AttributeError):
        empty_config.non_group.item = 1


def test_error_del_missing_item(empty_config):
    with pytest.raises(KeyError):
        del empty_config['missing-key']


def test_error_del_missing_item_in_group(config_inst):
    with pytest.raises(KeyError):
        del config_inst['group.missing-item']


def test_error_del_item_in_missing_group(config_inst):
    with pytest.raises(KeyError):
        del config_inst['missing-item.foo']


@pytest.fixture
def class_mixes():

    class Base(Configuration):
        foo = ConfigDescriptor(
            String,
            default="foo",
            doc="Some common value")

    class Sub(Base):
        bar = ConfigDescriptor(
            String,
            default="bar",
            doc="Some specialized value")

    class IndependentMixin(Configuration):
        bar = ConfigDescriptor(
            String,
            default="bar",
            doc="Some specialized value")

    class Mixed(Base, IndependentMixin):
        some_other_attribute = None

    return [Sub, Mixed]


def test_inheritance(class_mixes):
    for cls in class_mixes:
        config = cls()
        assert len(config) == 2
        assert 'foo' in config
        assert 'bar' in config
        assert config.foo == 'foo'
        assert config.bar == 'bar'


def test_unicode(config_inst):
    assert isinstance(unicode(config_inst), unicode)


def test_str(config_inst):
    assert isinstance(str(config_inst), str)


def test_repr(config_inst, config_cls):
    Example = config_cls  # Namespace
    reprstr = repr(config_inst)
    copy = eval(reprstr)
    assert copy == config_inst
    del Example  # Shut up, linter


def test_load_dict(config_inst):
    cfg = {'group': {'item_a': 'c'}, 'foo': 4, }
    config_inst.load_dict(cfg)
    assert config_inst['foo'] == 4
    assert config_inst['bar'] == 'example'
    assert config_inst['group.item_a'] == 'c'
    assert config_inst['group.item_b'] == 'b'


def test_load_dict_duplicate(config_inst, group_cls):
    cfg = {'group': {'item_a': 'c'}, 'foo': 4, 'group.item_a': 'a', }
    try:
        config_inst.load_dict(cfg)
    except ConfigurationError as e:
        assert 'group.item_a' in e.errors


def test_dump_dict(config_inst):
    d = config_inst.dump_dict()
    assert 'foo' in d
    assert 'group' in d
    assert 'item_a' in d['group']
    assert d['bar'] == 'example'
    assert d['group']['item_b'] == 'b'


def test_dump_dict_flat(config_inst):
    d = config_inst.dump_dict(flatten=True)
    assert 'bar' in d
    assert 'group.item_b' in d
    assert d['foo'] == 1
    assert d['group.item_a'] == 'a'
    assert d.keys() == sorted(d.keys())
