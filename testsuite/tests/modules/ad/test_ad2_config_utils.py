# encoding: utf-8
""" Tests for :mod:`Cerebrum.modules.ad2.ConfigUtils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.ad2 import ConfigUtils as config_utils  # noqa: N813


@pytest.fixture(autouse=True)
def _patch_globals(database, const):
    """ catch badly formatted log records in dbal.logger. """
    config_utils.db = database
    config_utils.const = type(const)


@pytest.fixture
def spread_1(constant_module, constant_creator):
    return constant_creator(
        constant_module._SpreadCode,
        "s-1-60d9bf4cf132",
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def spread_2(constant_module, constant_creator):
    return constant_creator(
        constant_module._SpreadCode,
        "s-2-60d9bf4cf132",
        constant_module.CoreConstants.entity_person,
    )


class MockCallback(object):
    """ A simple mock callback function. """

    def __init__(self, value):
        self.value = value

    def __call__(self, *args, **kwargs):
        return self.value


#
# _prepare_constants tests
#


def test_prepare_constants_empty(constant_module):
    cls = constant_module._SpreadCode
    assert config_utils._prepare_constants(None, cls) is None


def test_prepare_constants_single(constant_module, spread_1):
    cls = constant_module._SpreadCode
    result = config_utils._prepare_constants(spread_1, cls)
    assert result == (spread_1,)


def test_prepare_constants_list(constant_module, spread_1, spread_2):
    cls = constant_module._SpreadCode
    spreads = (spread_1, spread_2)
    result = config_utils._prepare_constants(spreads, cls)
    assert result == spreads


def test_prepare_constants_invalid(constant_module, spread_1):
    cls = constant_module._EntityExternalIdCode
    with pytest.raises(config_utils.ConfigError):
        config_utils._prepare_constants(spread_1, cls)


#
# AttrCriterias tests
#


def test_attr_criterias_init_minimal():
    result = config_utils.AttrCriterias()
    assert not result.spreads
    assert not getattr(result, "callback", None)


def test_attr_criterias_init(spread_1):
    callback = MockCallback(True)
    result = config_utils.AttrCriterias(
        spreads=spread_1,
        callback=callback,
    )
    assert result.spreads == (spread_1,)
    assert result.callback is callback


def test_attr_criterias_init_invalid_callback():
    with pytest.raises(config_utils.ConfigError):
        config_utils.AttrCriterias(callback=True)


def test_attr_criterias_check_spreads(spread_1, spread_2):
    entity_a = type(str("example"), (object,), {"spreads": [spread_1]})()
    entity_b = type(str("example"), (object,), {"spreads": [spread_2]})()
    criteria = config_utils.AttrCriterias(spreads=(spread_1,))
    criteria.check(entity_a)
    with pytest.raises(config_utils.CriteriaError):
        criteria.check(entity_b)


def test_attr_criterias_check_callback():
    entity_a = type(str("example"), (object,), {})()
    entity_b = type(str("example"), (object,), {})()
    criteria = config_utils.AttrCriterias(
        callback=lambda e: e is entity_b,
    )
    with pytest.raises(config_utils.CriteriaError):
        criteria.check(entity_a)
    criteria.check(entity_b)


#
# AttrCriterias tests
#


def test_attr_config_init_minimal():
    result = config_utils.AttrConfig()
    assert not result.default
    assert not getattr(result, "transform", None)
    assert not result.source_systems
    assert not result.spread
    assert not result.criterias
    assert not result.ad_transform


def test_attr_config_init(spread_1):
    transform = MockCallback("foo-transform")
    ad_transform = MockCallback("foo-ad-transform")
    criterias = config_utils.AttrCriterias()
    result = config_utils.AttrConfig(
        default="foo",
        transform=transform,
        spread=(spread_1,),
        criterias=criterias,
        ad_transform=ad_transform,
    )
    assert result.default == "foo"
    assert result.transform(None) == "foo-transform"
    assert result.spread == (spread_1,)
    assert result.criterias is criterias
    assert result.ad_transform(None) == "foo-ad-transform"


def test_attr_config_init_invalid_criteria():
    with pytest.raises(config_utils.ConfigError):
        config_utils.AttrConfig(criterias=object())


def test_attr_config_init_invalid_ad_transform():
    with pytest.raises(config_utils.ConfigError):
        config_utils.AttrConfig(ad_transform=object())


def test_callback_attr():
    result = config_utils.CallbackAttr(MockCallback("foo"))
    assert result.callback(None) == "foo"


def test_callback_attr_invalid_callback():
    with pytest.raises(config_utils.ConfigError):
        config_utils.CallbackAttr(None)


#
# attribute config helper tests
#


class CustomAttr(config_utils.AttrConfig):

    def __init__(self, value, *args, **kwargs):
        super(CustomAttr, self).__init__(*args, **kwargs)
        self.value = value


@pytest.fixture
def example_config():
    return {
        'foo': config_utils.CallbackAttr(MockCallback("foo-value")),
        'bar': (
            config_utils.CallbackAttr(MockCallback("bar-value-0")),
            config_utils.CallbackAttr(MockCallback("bar-value-1")),
        ),
        'baz': CustomAttr("baz"),
    }


def test_has_config(example_config):
    assert config_utils.has_config(example_config, config_utils.CallbackAttr)
    assert config_utils.has_config(example_config, CustomAttr)
    assert not config_utils.has_config(example_config, config_utils.NameAttr)


def test_get_config_by_type(example_config):
    result = config_utils.get_config_by_type(example_config,
                                             config_utils.CallbackAttr)
    assert len(result) == 3
    assert example_config['foo'] in result
    assert example_config['bar'][0] in result
    assert example_config['bar'][1] in result
