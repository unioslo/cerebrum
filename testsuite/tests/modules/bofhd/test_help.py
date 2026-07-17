# -*- coding: utf-8 -*-
"""
Tests for Cerebrum.modules.bofhd.help.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.modules.bofhd import help as bofhd_help
from Cerebrum.modules.bofhd import errors as bofhd_errors

logger = logging.getLogger(__name__)


def test_merge_help_empty():
    """ test that no input produces empty outputs. """
    result = bofhd_help.merge_help_strings()
    assert result == ({}, {}, {})


def test_merge_help_copy():
    """ ensure that merge_help_strings makes *copies* of objects. """
    src_grps = {"foo": "foo"}
    src_cmds = {"foo": {"foo_bar": "foo_bar"}}
    src_args = {"name": ("name", "prompt", "help text")}

    dest_grps, dest_cmds, dest_args = bofhd_help.merge_help_strings(
        (src_grps, src_cmds, src_args,),
    )

    assert dest_grps is not src_grps
    assert dest_cmds is not src_cmds
    assert dest_args is not src_args
    assert dest_cmds['foo'] is not src_cmds['foo']


def test_merge_help_groups():
    """ test that a given group merges as expected. """
    a = {"foo": "foo help"}
    b = {"bar": "bar help"}
    c = {"baz": "baz help"}

    # groups missing from commands are ignored
    cmds = {"foo": {}, "bar": {}}

    merged_groups, _, _ = bofhd_help.merge_help_strings(
        (a, {}, {}),
        (b, {}, {}),
        (c, cmds, {}),
    )

    assert merged_groups == {
        "foo": "foo help",
        "bar": "bar help",
    }


def test_merge_help_cmd_replace():
    """ test that later commands help texts replaces previous help texts. """
    a = {'foo': {'foo_bar': "foo_bar"}, 'bar': {'bar_baz': "bar_baz"}}
    b = {'foo': {'foo_bar': "new foo_bar"}}

    _, merged_cmds, _ = bofhd_help.merge_help_strings(
        ({}, a, {}),
        ({}, b, {}),
    )

    assert merged_cmds == {
        'foo': {'foo_bar': "new foo_bar"},
        'bar': {'bar_baz': "bar_baz"},
    }


def test_merge_help_arg_replace():
    """ test that later argument help texts replaces previous help texts. """
    a = {'foo': ("a", "b", "c"), 'bar': ("d", "e", "f")}
    b = {'foo': ("g", "h", "i")}

    _, _, merged_args = bofhd_help.merge_help_strings(
        ({}, {}, a),
        ({}, {}, b),
    )

    assert merged_args == {
        'foo': ("g", "h", "i"),
        'bar': ("d", "e", "f"),
    }


class ReadOnlyHelp(bofhd_help.Help):
    """ A bofhd help object with known help texts. """

    group_help = {
        'general': "General bofhd help",
        'example': "Example bofhd command group",
    }

    command_help = {
        'example': {
            'foo': "Example bofhd command 'example foo'",
        },
    }

    arg_help = {
        'intval': (
            "intval",
            "Enter integer",
            "This is the long helpt for 'intval'",
        ),
        'strval': (
            "strval",
            "Enter string",
            "This is the long helpt for 'strval'",
        )
    }

    def __init__(self, *args, **kwargs):
        # (ab)use merge_help_strings to make copies of the class help strings
        (
            self.group_help,
            self.command_help,
            self.arg_help,
        ) = bofhd_help.merge_help_strings((
            type(self).group_help,
            type(self).command_help,
            type(self).arg_help,
        ))
        # the 'general' section getsfiltered out,
        # as it doesn't have any commands:
        self.group_help.update(type(self).group_help)
        self.logger = logger.getChild("MockHelp")

    def update_from_extension(self, *args, **kwargs):
        # prevent this from being called by mistake
        raise NotImplementedError()


@pytest.fixture
def help_obj():
    return ReadOnlyHelp()


def test_get_general_help(help_obj):
    """ Check that get_general_help returns *something*. """
    all_commands = {}
    gen = help_obj.get_general_help(all_commands)
    assert len(gen) > 1


def test_get_group_help(help_obj):
    """ Check that get_group_help returns *something*. """
    all_commands = {}
    gen = help_obj.get_group_help(all_commands, "example")
    assert len(gen) > 1


def test_get_arg_help(help_obj):
    """ Check that get_group_help returns *something*. """
    gen = help_obj.get_arg_help("intval")
    assert gen == ReadOnlyHelp.arg_help['intval'][2]


def test_get_arg_help_missing(help_obj):
    """ Check that get_arg_help raises a CerebrumError on missing ref. """
    with pytest.raises(bofhd_errors.CerebrumError):
        help_obj.get_arg_help("unknown-argument")
