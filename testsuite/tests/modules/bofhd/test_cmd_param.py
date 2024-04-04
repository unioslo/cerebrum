# -*- coding: utf-8 -*-
"""
Tests for Cerebrum.modules.bofhd.cmd_param.

This test module is not all that helpful, as most of the cmd-param
functionality is built into the interactive command line clients.

The module mostly constsists of simple wrappers that just return object
attributes as a dict.  At least we'll know the module is importable...

This module also kind of serves a purpose in documenting some examples on how
these data structures for the client are formatted.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.help import Help

logger = logging.getLogger(__name__)


class MockHelp(Help):
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
        self.logger = logger.getChild("MockHelp")

    def update_from_extension(self, *args, **kwargs):
        # prevent this from being called by mistake
        raise NotImplementedError()


@pytest.fixture()
def help_ref():
    # note - `help_ref` is both used as the argument name/reference to a `Help`
    # object, as well as the `arg_help` key too look up within a `Help` object.
    return MockHelp()


#
# Parameter tests
#


def test_parameter_init():
    # TODO: We're testing for protected attrs, which is generally frowned upon.
    # I would argue that these attrs should be public, though.
    param = cmd_param.Parameter(
        optional=True,
        default="foo",
        repeat=False,
        help_ref="strval",
    )
    assert param._optional
    assert param._default == "foo"
    assert not param._repeat
    assert param._help_ref == "strval"


class ExampleParam(cmd_param.Parameter):
    _tab_func = "tab_example"
    _type = "example"
    _help_ref = "strval"


def test_parameter_struct_defaults(help_ref):
    param = ExampleParam()
    struct = param.get_struct(help_ref)
    assert struct == {
        'help_ref': ExampleParam._help_ref,
        'prompt': help_ref.arg_help[ExampleParam._help_ref][1],
        'type': ExampleParam._type,
    }


def test_parameter_struct(help_ref):
    param = ExampleParam(
        optional=True,
        default="foo",
        repeat=True,
        help_ref="intval",
    )
    struct = param.get_struct(help_ref)
    assert struct == {
        'default': "foo",
        'help_ref': "intval",
        'optional': True,
        'prompt': help_ref.arg_help['intval'][1],
        'repeat': True,
        'type': "example",
    }


def test_parameter_struct_missing(help_ref):
    param = ExampleParam(
        optional=True,
        default="foo",
        repeat=False,
        help_ref="non-existing",
    )
    struct = param.get_struct(help_ref)
    assert struct == {
        'default': "foo",
        'help_ref': "non-existing",
        'optional': True,
        'prompt': "",
        'type': ExampleParam._type,
    }


#
# FormatSuggestion tests
#


def test_format_suggestion():
    # a basic, hard-coded format
    format_ = "this is not a format string"
    fs = cmd_param.FormatSuggestion(format_)
    assert fs.get_format() == {
        'str_vars': format_,
    }


def test_format_suggestion_header():
    # a basic, hard-coded format with header
    format_ = "this is not a format string"
    header = "this is a header"
    fs = cmd_param.FormatSuggestion(format_, hdr=header)
    assert fs.get_format() == {
        'str_vars': format_,
        'hdr': header,
    }


def test_format_suggestion_format():
    # a basic format string with two variables
    format_ = "this is a format string, a=%s, b=%d"
    vars_ = ("example_strval", "example_intval")
    fs = cmd_param.FormatSuggestion(format_, vars_)
    assert fs.get_format() == {
        'str_vars': [(format_, vars_)],
    }


#
# Command tests
#


def test_command_defaults(help_ref):
    cmd_group = ("example", "foo")
    cmd = cmd_param.Command(cmd_group)
    assert cmd.get_fs() is None
    assert cmd.get_struct(help_ref) == (cmd_group,)


def test_command_params(help_ref):
    cmd_group = ("example", "foo")
    fs = cmd_param.FormatSuggestion("this is not a format string")
    param_a = ExampleParam(help_ref="intval")
    param_b = ExampleParam(help_ref="strval", optional=True, default="bar")
    cmd = cmd_param.Command(
        cmd_group,
        param_a,
        param_b,
        fs=fs,
        perm_filter="can_run_example_foo",
    )
    assert cmd.perm_filter == "can_run_example_foo"
    assert cmd.get_fs() == fs.get_format()
    assert cmd.get_struct(help_ref) == (
        cmd_group,
        [
            param_a.get_struct(help_ref),
            param_b.get_struct(help_ref),
        ],
    )


def test_command_prompt(help_ref):
    cmd_group = ("example", "foo")
    fs = cmd_param.FormatSuggestion("this is not a format string")
    cmd = cmd_param.Command(
        cmd_group,
        fs=fs,
        prompt_func="example_foo_prompt",
        perm_filter="can_run_example_foo",
    )
    assert cmd.get_fs() == fs.get_format()
    assert cmd.get_struct(help_ref) == (cmd_group, "prompt_func")
