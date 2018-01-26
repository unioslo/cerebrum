#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""Testing of Utils.py's functionality."""

import re
import sys
import nose.tools
import Cerebrum.Utils as Utils
from Cerebrum.extlib.db_row import MetaRow

# Data
messages_en_word = 'ynzwdpzm'
messages_no_word = 'llduloxr'
messages_dict = {'both_langs': {'en': messages_en_word,
                                'no': messages_no_word, },
                 'only_en':    {'en': messages_en_word, },
                 'only_no':    {'no': messages_no_word, },
                 'only_nn':    {'nn': messages_no_word, },
                 'none':       {}, }

# Helper functions


def noop():
    """ A simple no-op function. """
    pass


def raise1():
    """ Function to raise ValueError. """
    raise ValueError("raise1")


# Utils.format_exception_context

def test_format_exception_context_wrong_args():
    """ Utils.format_exception_context with invalid arguments. """
    for count in range(3):
        nose.tools.assert_raises(TypeError,
                                 Utils.format_exception_context,
                                 *(None,)*count)


def test_format_exception_context_no_exc():
    """ Utils.format_exception_context with empty arguments. """
    retval = Utils.format_exception_context(None, None, None)
    assert retval == ''


def test_format_exception_context1():
    """ Utils.format_exception_context with valid arguments. """
    try:
        raise ValueError("ioshivfq")
    except ValueError:
        message = Utils.format_exception_context(*sys.exc_info())
        assert re.search("Exception <type 'exceptions.ValueError'> occured " +
                         "\(in context.*: ioshivfq", message)


# Utils.exception_wrapper

def test_exception_wrapper_returns_callable():
    """ Utils.exception_wrapper returns callable. """
    assert hasattr(Utils.exception_wrapper(noop), '__call__')
    Utils.exception_wrapper(noop)()


def test_exception_wrapper_arg_count():
    """ Utils.exception_wrapper with invalid arguments. """
    for count in 0, 5:
        nose.tools.assert_raises(TypeError,
                                 Utils.exception_wrapper,
                                 *(None,)*count)


def test_exception_wrapper_behaviour():
    """ Utils.exception_wrapper with valid arguments. """
    # Ignoring all exceptions with defaults always yields None
    assert Utils.exception_wrapper(noop, None)() is None
    # Ignoring the exception raised with defaults always yields None
    assert Utils.exception_wrapper(raise1, ValueError)() is None
    # Exceptions can be given as tuples ...
    assert Utils.exception_wrapper(raise1, (ValueError,))() is None
    # ... lists
    assert Utils.exception_wrapper(raise1, [ValueError, ])() is None
    # ... or sets without affecting the result
    assert Utils.exception_wrapper(raise1, set((ValueError,)))() is None

    # Exception not matching the spec are not caught
    nose.tools.assert_raises(ValueError,
                             Utils.exception_wrapper(raise1, AttributeError))

    # Return value with no exceptions is not altered
    assert Utils.exception_wrapper(noop, None, '')() is None
    # Return value with exceptions matches the arg
    assert Utils.exception_wrapper(raise1, ValueError, '')() == ''


# Utils.NotSet

def test_notset_single():
    """ Utils.NotSet comparison behaviour. """
    ns1 = Utils.NotSet
    ns2 = Utils.NotSet
    ns3 = Utils._NotSet()

    assert ns1 is ns2
    assert ns1 is ns3
    assert ns1 == ns2 == ns3
    assert not bool(ns1)


# Utils.dyn_import

def dyn_import_test():
    """ Utils.dyn_import puts modules in sys.modules. """

    for name in ("Cerebrum.Utils", "Cerebrum.modules", "Cerebrum.modules.no"):
        Utils.dyn_import(name)
        assert name in sys.modules

    x = "Cerebrum.modules.no"
    assert Utils.dyn_import(x) is sys.modules[x]


# Utils.this_module

def this_module_test():
    """ Utils.this_module reports correct module. """
    me = sys.modules[this_module_test.__module__]
    assert Utils.this_module() is me
    assert Utils.this_module() == me


def is_str_test():
    """ Utils.is_str accepts str, rejects unicode and others. """
    assert Utils.is_str('Hello world!')
    assert not Utils.is_str(u'Hello world!')
    assert not Utils.is_str(None)
    assert Utils.is_str(str(None))
    assert not Utils.is_str(unicode(None))


def is_unicode_test():
    """ Utils.is_unicode accepts unicode, rejects str and others. """
    assert not Utils.is_unicode('Hello world!')
    assert Utils.is_unicode(u'Hello world!')
    assert not Utils.is_unicode(None)
    assert not Utils.is_unicode(str(None))
    assert Utils.is_unicode(unicode(None))


def is_str_or_unicode_test():
    """ Utils.is_str_or_unicode accepts unicode, str, rejects others. """
    assert Utils.is_str_or_unicode('Hello world!')
    assert Utils.is_str_or_unicode(u'Hello world!')
    assert not Utils.is_str_or_unicode(None)
    assert Utils.is_str_or_unicode(str(None))
    assert Utils.is_str_or_unicode(unicode(None))


def test_messages_type():
    """ Utils.messages correct class. """
    m = Utils.Messages(text={})
    assert isinstance(m, Utils.Messages)
    assert isinstance(m, dict)


def test_messages_fetch_exists():
    """ Utils.Messages fetch exising word/fallback word. """
    # Word in primary and fallback
    assert Utils.Messages(text={'foo': {'no': 'bar_no', 'en': 'bar_en'}},
                          lang='no', fallback='en')['foo'] == 'bar_no'
    # Word only in primary
    assert Utils.Messages(text={'foo': {'no': 'bar_no', }},
                          lang='no', fallback='en')['foo'] == 'bar_no'
    # Word only in fallback
    assert Utils.Messages(text={'foo': {'en': 'bar_en', }},
                          lang='no', fallback='en')['foo'] == 'bar_en'


@nose.tools.raises(KeyError)
def test_messages_missing_key():
    """ Utils.Messages fetch non-exising key. """
    Utils.Messages(text={}, lang='no', fallback='en')['foo']


@nose.tools.raises(KeyError)
def test_messages_missing_lang():
    """ Utils.Messages fetch non-exising lang. """
    Utils.Messages(
        text={'foo': {'se': 'bar_se'}}, lang='en', fallback='no')['foo']


def test_messages_set_key():
    """ Utils.Messages set key. """
    m = Utils.Messages(text={}, lang='no', fallback='en')
    m['foo'] = {'no': 'bar_no'}
    assert m['foo'] == 'bar_no'


@nose.tools.raises(NotImplementedError)
def test_messages_set_invalid():
    """ Utils.Messages set key to invalid value. """
    m = Utils.Messages(text={}, lang='foo', fallback='bar')
    m['key'] = 'value'


def test_argument_to_sql_droptables():
    """ Utils.argument_to_sql with Bobby Tables. """
    binds = {}
    name = "Robert'; DROP TABLE Students;--"
    sql = Utils.argument_to_sql(name, 'name', binds)
    assert sql == '(name = :name)'
    assert binds == {'name': name}  # This function should not sanitize. That's
                                    # for the transform to do.


def test_argument_to_sql_transform():
    """ Utils.argument_to_sql with transform function. """
    binds = {}
    sql = Utils.argument_to_sql(None, 'foo', binds, type)
    assert sql == '(foo = :foo)'
    assert binds == {'foo': type(None)}


def test_argument_to_sql_sequence():
    """ Utils.argument_to_sql with sequence. """
    sequence = [1, 2, 3]
    for seq_type in (tuple, set, list):
        binds = {}
        sql = Utils.argument_to_sql(seq_type(sequence), 'foo', binds)
        assert sql == '(foo IN (:foo0, :foo1, :foo2))'
        assert binds == {'foo0': 1, 'foo1': 2, 'foo2': 3}


# TODO: How to test:
# - SMSsender?
# - sendmail?
# - mail_template?
# - read_password?
# - make_temp_file
# - make_temp_dir
#
