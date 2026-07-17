# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.password_notifier.config` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.config.errors import ConfigurationError
from Cerebrum.modules.password_notifier import config as pn_config


#
# PasswordNotifierConfig tests
#


def test_pn_config_validate():
    config = pn_config.PasswordNotifierConfig()
    config.validate()
    assert True  # reached


def test_pn_config_from_dict():
    config_dict = {
        'change_log_program': "test-prog",
        'change_log_account': "",
        'templates': [],
        'max_password_age': 720,
        'max_new_notifications': 2,
        'grace_period': 14,
        'reminder_delay_values': [3, 7],
        'class_notifier_values': [
            'Cerebrum.modules.password_notifier.notifier/PasswordNotifier',
        ],
        'trait': "pw_notifications",
        'follow_trait': "pw_notifications",
        'except_trait': "autopass_except",
        'summary_from': "noreply@uio.no",
        'summary_to': ["example@example.org"],
        'summary_cc': ["cc@example.org"],
        'summary_bcc': ["bcc@example.org"],
        'affiliation_mappings': [
            {
                'affiliation': "ANSATT/tekadm",
                'max_password_age': 360,
                'warn_before_expiration_days': 7,
            },
        ],
    }
    config = pn_config.PasswordNotifierConfig(config_dict)
    config.validate()

    for k in config_dict:
        assert config[k] == config_dict[k]


@pytest.mark.parametrize(
    "key, value",
    [
        pytest.param("max_password_age", 0, id="no password age"),
        pytest.param("grace_period", -1, id="negative grace period"),
    ],
)
def test_pn_config_invalid_setting(key, value):
    with pytest.raises(ConfigurationError):
        pn_config.PasswordNotifierConfig({key: value})
