#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Testing of Utils.py's functionality."""

import nose.tools
import Cerebrum.Utils
import Cerebrum.modules.bofhd.session as session


# TODO: Or use pythons built-in logging?
logger = Cerebrum.Utils.get_logger('console')


def test_ip_to_long():
    """ Cerebrum.modules.bofhd.session.ip_to_long """
    assert session.ip_to_long('127.0.0.1') == 2130706433
    assert session.ip_to_long('129.240.8.200') == 2179991752


def test_ip_subnet_to_slash_range():
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range. """
    test = session.ip_subnet_slash_to_range
    assert test('127.0.0.0/8') == (2130706432L, 2147483647L)
    assert test('127.0.0.0/31') == (2130706432L, 2130706433L)
    assert test('127.0.0.0/1') == (0L, 2147483647L)


@nose.tools.raises(ValueError)
def test_ip_subnet_to_slash_range_big():
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range error. """
    session.ip_subnet_slash_to_range('127.0.0.0/0')


@nose.tools.raises(ValueError)
def test_ip_subnet_to_slash_range_small():
    """ Cerebrum.modules.bofhd.session.ip_subnet_to_slash_range error. """
    session.ip_subnet_slash_to_range('127.0.0.0/32')


# TODO: Actual BofhdSession tests
