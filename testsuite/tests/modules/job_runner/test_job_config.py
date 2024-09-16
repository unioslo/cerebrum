# encoding: utf-8
""" Unit tests for :mod:`Cerebrum.modules.job_runner.job_config` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import sys
import textwrap

import pytest

from Cerebrum.modules.job_runner import job_config


# Uses `config_file` fixture from `conftest`


CONFIG_TEXT = textwrap.dedent(
    """
    FOO = "foo"
    BAR = 3
    """
).lstrip()


def _write_config(filename, content):
    with io.open(filename, mode="w", encoding="utf-8") as f:
        f.write(content)


@pytest.fixture
def config_file(config_file):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    _write_config(config_file, CONFIG_TEXT)
    return config_file


def test_get_job_config_file(config_file):
    mod = job_config.get_job_config(config_file)
    assert mod.FOO == "foo"
    assert job_config.DEFAULT_MODULE_NAME in sys.modules
    assert sys.modules[job_config.DEFAULT_MODULE_NAME] is mod


def test_get_job_config_module(config_file):
    job_config.get_job_config(config_file)
    mod = job_config.get_job_config(job_config.DEFAULT_MODULE_NAME)
    assert mod.FOO == "foo"


def test_reload_config_module(config_file):
    mod_a = job_config.get_job_config(config_file)
    assert mod_a.__file__ == config_file
    config_text = CONFIG_TEXT + textwrap.dedent(
        """
        BAZ = "baz"
        """
    )
    _write_config(config_file, config_text)
    mod_b = job_config.reload_job_config(mod_a)
    assert mod_b is mod_a
    assert mod_b.BAZ == "baz"


#
# very basic tests
#


def test_get_parser():
    assert job_config.pretty_jobs_parser()
