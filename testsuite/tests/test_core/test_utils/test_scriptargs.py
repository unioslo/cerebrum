#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for script argument utilities. """
from __future__ import print_function, unicode_literals

import pytest
import argparse

from Cerebrum.utils.scriptargs import build_callback_action


class CallbackCalled(Exception):
    pass


def test_build_callback_action():
    def callback(*args, **kwargs):
        raise CallbackCalled

    def noop(*args, **kwargs):
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument('--foo',
                        action=build_callback_action(callback, exit=False),
                        help="Foo")
    parser.add_argument('--bar',
                        action=build_callback_action(noop, exit=True),
                        help="Bar")

    with pytest.raises(CallbackCalled):
        parser.parse_args(['this', '--foo'])
    with pytest.raises(SystemExit):
        parser.parse_args(['this', '--bar'])
