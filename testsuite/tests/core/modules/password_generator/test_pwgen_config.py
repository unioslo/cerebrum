# encoding: utf-8
"""
Tests for :mod:`Cerebrum.modules.password_generator.config`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import json

import pytest

from Cerebrum.modules.password_generator import config as pwgen_config
from Cerebrum.utils import file_stream


#
# Test the default config
#


@pytest.fixture
def default_config():
    return pwgen_config.PasswordGeneratorConfig()


def test_validate_default_config(default_config):
    default_config.validate()
    assert True  # reached


#
# Test that our settings actually validates values
#


def test_setting_words_valid(default_config):
    """ amount_words should be a positive integer. """
    default_config.amount_words = 3
    assert default_config.amount_words == 3


def test_setting_words_invalid(default_config):
    """ amount_words should be a positive integer. """
    with pytest.raises(ValueError):
        default_config.amount_words = 0


def test_setting_length_valid(default_config):
    """ password_length should be a positive integer. """
    default_config.password_length = 8
    assert default_config.password_length == 8


def test_setting_length_invalid(default_config):
    """ password_length should be a positive integer. """
    with pytest.raises(ValueError):
        default_config.password_length = 0


def test_setting_charset_valid(default_config):
    """ legal_characters should be a string. """
    default_config.legal_characters = "ABCabc123"
    assert default_config.legal_characters == "ABCabc123"


def test_setting_charset_invalid(default_config):
    """ legal_characters should be a string. """
    with pytest.raises(TypeError):
        default_config.legal_characters = 0


def test_setting_dictionary_valid(default_config, empty_file):
    """ passphrase_dictionary must be readable. """
    default_config.passphrase_dictionary = empty_file
    assert default_config.passphrase_dictionary == empty_file


def test_setting_dictionary_invalid(default_config, new_file):
    """ passphrase_dictionary must be readable, and new_file doesn't exist. """
    with pytest.raises(ValueError):
        default_config.passphrase_dictionary = new_file


#
# Test using a custom config
#


@pytest.fixture
def config_data(empty_file):
    return {
        'amount_words': 3,
        'password_length': 8,
        'legal_characters': "Tr0ub4dor&3",
        'passphrase_dictionary': empty_file,
    }


@pytest.fixture
def config(config_data):
    return pwgen_config.PasswordGeneratorConfig(config_data)


@pytest.fixture
def config_file(empty_json_file, config_data):
    encoding = None if str is bytes else "utf-8"
    with file_stream.get_output_context(empty_json_file,
                                        encoding=encoding) as f:
        json.dump(config_data, f, indent=2, sort_keys=True)
    return empty_json_file


def test_validate_config(config):
    config.validate()
    assert True  # reached


def test_config_content(config, config_data):
    assert config.dump_dict() == config_data


def test_load_config(config_file, config):
    loaded = pwgen_config.load_config(filename=config_file)
    assert loaded == config
