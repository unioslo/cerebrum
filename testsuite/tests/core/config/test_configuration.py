# encoding: utf-8
""" Unit tests for :mod:`Cerebrum.config.configuration`. """
from collections import OrderedDict

import pytest
import six

from Cerebrum.config.configuration import ConfigDescriptor
from Cerebrum.config.configuration import Configuration
from Cerebrum.config.configuration import Namespace
from Cerebrum.config.configuration import flatten_dict
from Cerebrum.config.errors import ConfigurationError
from Cerebrum.config.settings import NotSet
from Cerebrum.config.settings import Numeric
from Cerebrum.config.settings import String


def test_flatten():
    d = {
        'foo': 1,
        'bar': {
            'foo': 2,
            'bar': {
                'foo': 3,
                'baz': 4,
            },
            'baz': 5,
        },
        'baz': {
            'foo': 6,
        },
    }
    flat = OrderedDict(flatten_dict(d))
    assert len(flat) == 6
    assert flat['foo'] == 1
    assert flat['bar.bar.baz'] == 4
    assert flat['baz.foo'] == 6
    assert 'bar.foo' in flat
    assert 'baz.foo' in flat
    assert 'bar.bar.foo' in flat
    assert list(flat.keys()) == sorted(flat.keys())


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
        foo = ConfigDescriptor(Numeric, minval=0, doc="Some foo value")
        bar = ConfigDescriptor(String, minlen=1, doc="Some bar value")
        group = ConfigDescriptor(Namespace, config=group_cls, doc="group")
        not_a_setting = "not a setting"
    return Example


@pytest.fixture
def config_inst(config_cls):
    c = config_cls()
    c['foo'] = 1
    c['bar'] = 'example'
    c['group.item_a'] = 'a'
    c['group.item_b'] = 'b'
    return c


def test_list_settings(config_cls):
    attrs = config_cls.list_settings()
    assert len(attrs) == 3
    assert set(attrs) == set(("foo", "bar", "group"))


def test_list_ns_settings(config_cls):
    attrs = list(config_cls.list_ns_settings())
    assert len(attrs) == 4
    assert set(attrs) == set(("foo", "bar", "group.item_a", "group.item_b"))


def test_documentation(config_cls):
    doc = config_cls.documentation()
    # This is a bit lazy - we just ensure nothing fails, and that we got
    # *something* out of the call
    assert doc


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


def test_eq(config_cls):
    values = {'foo': 1, 'bar': "ex", 'group': {'item_a': "a", 'item_b': "b"}}
    a = config_cls(values)
    b = config_cls(values)
    assert a == b


def test_not_eq_cls(config_cls, group_cls):
    class _Custom(config_cls):
        pass

    a = config_cls()
    b = _Custom()
    assert a != b


def test_not_eq_values(group_cls):
    values_a = {'item_a': "a", 'item_b': "b"}
    values_b = {'item_a': "a", 'item_b': "c"}
    a = group_cls(values_a)
    b = group_cls(values_b)
    assert a != b


def test_not_eq_nested_values(config_cls):
    values_a = {'foo': 1, 'bar': "ex", 'group': {'item_a': "a", 'item_b': "b"}}
    values_b = {'foo': 1, 'bar': "ex", 'group': {'item_a': "a", 'item_b': "c"}}
    a = config_cls(values_a)
    b = config_cls(values_b)
    assert a != b


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


def test_set_namespace_attr(config_cls):
    example = config_cls({'foo': 2, 'bar': "bar"})
    example['group'] = {'item_a': "a", 'item_b': "b"}
    assert example['foo'] == 2
    assert example['bar'] == "bar"
    assert example['group.item_a'] == "a"
    assert example['group.item_b'] == "b"


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


def test_error_missing_nested_item(config_inst):
    """ getting a non-existing nested name should result in an error """
    with pytest.raises(KeyError):
        config_inst['group.item_c']


def test_error_missing_nested_group(config_inst):
    """ getting a name from a non-namespace should result in an error """
    with pytest.raises(KeyError):
        config_inst['foo.bar']


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


def test_validate_valid(config_inst):
    config_inst.validate()
    # validate raises an exception if something is invalid
    assert True


def test_load_invalid_setting(config_inst):
    # foo must be >= 0, load_dict should validate this
    with pytest.raises(ConfigurationError) as err:
        config_inst.load_dict({'foo': -1})

    assert len(err.value.errors) == 1
    assert "foo" in err.value.errors


def test_load_multiple_invalid_settings(config_inst):
    # foo must be >= 0, and len(bar) > 0
    with pytest.raises(ConfigurationError) as err:
        config_inst.load_dict({'foo': -1, 'bar': ""})

    assert len(err.value.errors) == 2
    assert "foo" in err.value.errors
    assert "bar" in err.value.errors


def test_validate_missing_settings(config_cls):
    # foo must be >= 0, load_dict should validate this
    config_inst = config_cls({'bar': "example", 'group.item_a': "something"})
    with pytest.raises(ConfigurationError) as err:
        config_inst.validate()

    assert len(err.value.errors) == 2
    assert "foo" in err.value.errors
    assert "group.item_b" in err.value.errors


def test_validate_load_invalid_setting(config_inst):
    # foo must be >= 0, load_dict should validate this
    with pytest.raises(ConfigurationError) as err:
        config_inst.load_dict({'missing_attr': "baz"})

    assert len(err.value.errors) == 1
    assert "missing_attr" in err.value.errors


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
    assert isinstance(six.text_type(config_inst), six.text_type)


def test_str(config_inst):
    assert isinstance(str(config_inst), str)


def test_repr(config_inst, config_cls):
    # The class name is 'Example' - it needs to exist in this scope for our
    # `eval` to work as expected.
    Example = config_cls  # noqa: N806
    reprstr = repr(config_inst)
    copy = eval(reprstr)
    assert copy == config_inst
    del Example  # 'use' Example to shut up linters


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
    assert list(d.keys()) == sorted(d.keys())
