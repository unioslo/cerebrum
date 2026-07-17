# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.tasks.config` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.config.errors import ConfigurationError
from Cerebrum.modules.tasks import config as task_config


def get_tasks():
    """ Example callable """


GET_TASKS_VALUE = "{}:{}".format(get_tasks.__module__, get_tasks.__name__)


#
# Callable setting tests
#


def test_callable_validate():
    callable_setting = task_config.Callable()
    callable_setting.validate(get_tasks)
    assert True  # reached


def test_callable_validate_optional():
    callable_setting = task_config.Callable(default=None)
    callable_setting.validate(None)
    assert True


@pytest.mark.parametrize("value", [None, ""])
def test_callable_validate_invalid(value):
    callable_setting = task_config.Callable()
    with pytest.raises(ValueError):
        callable_setting.validate(value)


def test_callable_set():
    callable_setting = task_config.Callable()
    callable_setting.set_value(get_tasks)
    assert callable_setting.get_value() == get_tasks


def test_callable_serialize():
    callable_setting = task_config.Callable()
    assert callable_setting.serialize(get_tasks) == GET_TASKS_VALUE
    assert callable_setting.serialize(None) is None


def test_callable_unserialize():
    callable_setting = task_config.Callable()
    assert callable_setting.unserialize(GET_TASKS_VALUE) == get_tasks
    assert callable_setting.unserialize(None) is None


#
# TaskGeneratorConfig tests
#


def test_task_config_validate():
    config = task_config.TaskGeneratorConfig()
    config['source'] = "example"
    config['get_tasks'] = get_tasks
    config.validate()
    assert True  # reached


@pytest.mark.parametrize(
    "value",
    [{'source': "foo"}, {'get_tasks': GET_TASKS_VALUE}],
    ids=["no callable", "no source"],
)
def test_task_config_validate_empty(value):
    config = task_config.TaskGeneratorConfig(value)
    with pytest.raises(ConfigurationError):
        config.validate()


def test_task_config_from_dict():
    config = task_config.TaskGeneratorConfig({
        'source': "example",
        'get_tasks': GET_TASKS_VALUE,
    })
    config.validate()
    assert config['source'] == "example"
    assert config['get_tasks'] == get_tasks


#
# TaskListMixin tests
#


def test_task_list_validate():
    config = task_config.TaskListMixin({
        'tasks': [
            {
                'source': "foo",
                'get_tasks': GET_TASKS_VALUE,
            },
            {
                'source': "bar",
                'get_tasks': GET_TASKS_VALUE,
            },
        ],
    })
    config.validate()
    assert len(config['tasks']) == 2
    assert config['tasks'][0]['source'] == "foo"
    assert config['tasks'][0]['get_tasks'] == get_tasks
    assert config['tasks'][1]['source'] == "bar"
    assert config['tasks'][1]['get_tasks'] == get_tasks


def test_task_list_validate_empty():
    config = task_config.TaskListMixin({'tasks': []})
    config.validate()
    assert True  # reached
