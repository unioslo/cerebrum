#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""These tests cover Cerebrum's own logging framework -- cerelog.

- process_config() is too complex to test right now
- initialize_logger -- ditto
- initialize_handler -- ditto
- initialize_formatter -- ditto
- cerelog_init -- ditto
- DelayedFileHandler


"""

import cStringIO
import logging
import os
import random
import string
import sys
import threading

import Cerebrum.modules.cerelog as cerelog





def guerilla_clean_cerelog():
    """Some of the setup steps are once-per-process only. This function cleans
    all the internal structures. This is NOT supposed to be run in regular
    code; but this is rather a necessity of testing cerelog in multiple
    configuratiosn from the same process.
    """

    cerelog._logger_instance = None
    cerelog._handlers = dict()
    cerelog._formatters = dict()
    cerelog.init_cerebrum_extensions()
# end guerilla_clean_cerelog


def clean_directory(dirname):
    """Remove dirname and everything inside it.

    NB! Use with care!!
    """

    if dirname is not None and os.path.exists(dirname):
        for root, dirs, files in os.walk(dirname, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
                # print "os.remove(%s)" % (os.path.join(root, name),)
            for name in dirs:
                os.rmdir(os.path.join(root, name))
                # print "os.rmdir(%s)" % (os.path.join(root, name),)
        os.rmdir(dirname)
# end clean_directory


def with_tmp_directory(func):
    def test_wrapper(*rest, **kw_args):
        original_wd = os.getcwd()
        tmpdir = None
        try:
            tmpdir = mkdtemp()
            # print "Creating tmp dir=%s" % tmpdir
            os.chdir(tmpdir)
            func(*rest, **kw_args)
        finally:
            if os.getcwd() != original_wd:
                os.chdir(original_wd)
            clean_directory(tmpdir)
    # end test_wrapper

    # This is to make func names look sane in the nose output
    test_wrapper.__name__ = func.__name__
    test_wrapper.func_name = func.func_name

    return test_wrapper
# end with_tmp_directory


def mkdtemp(run_mkdir=True,
            alphabet=list(string.ascii_letters + string.digits)):
    """Why does Python not have mkdtemp?"""

    # if we do not succeed in 20 attempts -- epic fail. 20 is just a magic
    # number; there is nothing special about it.
    for count in range(20):
        new_dir = os.path.join("/tmp", "".join(random.sample(alphabet, 20)))
        if not os.path.exists(new_dir):
            if run_mkdir:
                os.mkdir(new_dir)
            return new_dir

    raise RuntimeError("Failed to create a temporary directory")
# end mkdtemp


def slurp(filename):
    """Return the content of file filename

    @type filename: basestring
    @param filename: Filename to read.
    """

    return file(filename).read().strip()
# end slurp



def test_init_cerebrum_extensions():
    guerilla_clean_cerelog()

    additional_debug_names = ("DEBUG%d" % x for x in range(1, 6))

    # Check additional debug attributes are in cerelog
    assert all(hasattr(cerelog, name) for name in additional_debug_names)

    # Check the class is there
    assert logging.getLoggerClass() is cerelog.CerebrumLogger

    # Check the additional debug levels are there
    for name in additional_debug_names:
        debug_level = getattr(cerelog, name)
        assert logging.getLevelName(debug_level) == name
# end test_init_cerebrum_extensions



def test_fetch_logger_arguments():
    guerilla_clean_cerelog()

    oldsys = sys.argv
    cerelog_args = ("--logger-name", "--logger-level")
    
    try:
        # feed an empty list. expect an empty result
        sys.argv = list()
        assert cerelog.fetch_logger_arguments(()) == dict()
        assert sys.argv == list()

        # feed a list with mixed argument junk, but nothing for the logger
        l =  [__file__, "-a", "-b", "1", "-c=2",
              "--long1", "--long2", "2", "--long3=3"]
        sys.argv = l[:]
        assert cerelog.fetch_logger_arguments(cerelog_args) == dict()
        assert sys.argv == l

        # feed a list with cerelog-specific arguments
        l = ["--logger-name", "foo"]
        sys.argv = l[:]
        assert cerelog.fetch_logger_arguments(cerelog_args) == {l[0]: l[1]}
        assert sys.argv == list()

        # feed a list with cerelog-specific arguments
        l = ["--logger-name=foo", "--logger-level", "DEBUG"]
        sys.argv = l[:]
        x = cerelog.fetch_logger_arguments(cerelog_args)
        y = {"--logger-name": "foo", l[1]: l[2]}
        assert x == y
        assert sys.argv == list()

        # feed a mix of junk and cerelog-specific arguments
        l = ["--logger-name=foo", "--logger-level", "DEBUG"]
        extra = [__file__, "-a", "-b", "1", "-c=2",
                 "--long1", "--long2", "2", "--long3=3"]
        tmp = extra[:]
        # put cerelog-stuff here and there
        tmp.insert(2, l[0])
        tmp.insert(4, l[1])
        tmp.insert(5, l[2])
        sys.argv = tmp[:]
        x = cerelog.fetch_logger_arguments(cerelog_args)
        y = {"--logger-name": "foo", l[1]: l[2]}
        assert x == y
        assert sys.argv == extra
    finally:
        sys.argv = oldsys
# end test_fetch_logger_arguments
    


def test_get_level():
    # This is quite essential actually.
    guerilla_clean_cerelog()
    
    assert cerelog.get_level(logging.DEBUG) == logging.DEBUG
    assert cerelog.get_level("DEBUG") == logging.DEBUG

    assert cerelog.get_level(cerelog.DEBUG1) == cerelog.DEBUG1
    assert cerelog.get_level("DEBUG1") == cerelog.DEBUG1
# end test_get_level



def test_get_logger():
    import cerebrum_path, cereconf
    guerilla_clean_cerelog()

    # cerelog has a singleton logger.
    l1 = cerelog.get_logger(cereconf.LOGGING_CONFIGFILE, "console")
    l2 = cerelog.get_logger(cereconf.LOGGING_CONFIGFILE, "console")
    l3 = cerelog.get_logger(cereconf.LOGGING_CONFIGFILE, "root")

    # We have one instance only
    assert l1 is l2 is l3
# end test_get_logger



@with_tmp_directory
def test_root_logger():
    config_content = """
[logger_root]
level=WARN
qualname=root
handlers=hand_root

[handler_hand_root]
class=FileHandler
level=WARN
formatter=form_root
args=('root.log', 'a+')

[formatter_form_root]
format=%(message)s
"""

    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
    # this breaks all abstractions, but we don't really care here
    fname = l.handlers[0].baseFilename
    
    assert os.path.exists(fname)
    assert os.stat(fname).st_size == 0

    l.debug("this should not appear")
    assert os.stat(fname).st_size == 0

    l.info("this should not appear")
    assert os.stat(fname).st_size == 0

    msg = "this should appear"
    l.warn(msg)
    assert slurp(fname) == msg
# end test_root_logger



@with_tmp_directory
def test_simple_propagate():
    config_content = """

[logger_root]
level=WARN
qualname=root
handlers=hand_root

[handler_hand_root]
class=FileHandler
level=WARN
formatter=form_root
args=('root.log', 'a+')

[formatter_form_root]
format=%(message)s

[logger_case1]
level=INFO
qualname=case1
propagate=1
handlers=hand_case1

[handler_hand_case1]
class=FileHandler
level=INFO
formatter=form_root
args=('case1.log', 'a+')
"""

    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "case1")

    h_mine = l.handlers[0].baseFilename
    h_root = l.parent.handlers[0].baseFilename

    # the files should exist, and they should be empty
    assert os.stat(h_mine).st_size == 0
    assert os.stat(h_root).st_size == 0

    # this should not be anywhere
    l.debug("fjas")
    assert os.stat(h_mine).st_size == 0
    assert os.stat(h_root).st_size == 0

    # this should be in "mine" only
    message1 = "this appears in case"
    l.info("this appears in case")
    assert slurp(h_mine) == message1
    assert os.stat(h_root).st_size == 0

    # this should be in both only
    message2 = "this appears in both"
    l.warn(message2)
    assert slurp(h_mine) == message1 + '\n' + message2
    assert slurp(h_root) == message2
# end test_simple_propagate



@with_tmp_directory
def test_streamwriter_unicode_writing():
    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=DelayedFileHandler
level=DEBUG
formatter=form_root
args=('root.log', 'a+', 'utf-8')

[formatter_form_root]
format=%(message)s
    """

    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
    fname = l.handlers[0].baseFilename

    messages = ("foo", "blåbærsyltetøy", u"foobar", u"blåbærsyltetøy")
    for m in messages:
        l.debug(m)

    chunk = slurp(fname).decode('utf-8')
    original = "\n".join(isinstance(x, unicode) and x or x.decode('utf-8')
                         for x in messages)
    assert chunk == original
# end test_streamwriter_unicode_writing
    


@with_tmp_directory
def test_cerelog_findcaller():
    """Check that CerebrumLogger.findCaller makes sense"""

    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=StreamHandler
level=DEBUG
formatter=form_root
args=(sys.stderr,)

[formatter_form_root]
format=%(message)s
    """

    # findCaller return a triple in python>=2.4
    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
    source, lineno, codename = l.findCaller()

    name = __file__
    if __file__[-3:] == 'pyc':
        name = name[:-1]

    assert source == name
    assert codename == 'test_cerelog_findcaller'
# end test_cerelog_findcaller



@with_tmp_directory
def test_cerelog_indentation():
    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=FileHandler
level=DEBUG
formatter=form_root
args=('root.log', 'a+')

[formatter_form_root]
format=%(indent)s%(message)s
"""
    
    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
    fname = l.handlers[0].baseFilename

    l.debug("foo")
    l.set_indent(2)
    l.debug("bar")

    chunk = slurp(fname)
    assert chunk == "foo\n  bar"
# end test_indentation


@with_tmp_directory
def test_delayed_file_opening():
    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=DelayedFileHandler
level=INFO
formatter=form_root
args=('root.log', 'a+')

[formatter_form_root]
format=%(message)s
"""
    
    guerilla_clean_cerelog()
    l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
    fname = l.handlers[0].baseFilename

    assert not os.path.exists(fname)
    l.debug("this will not appear")

    assert not os.path.exists(fname)
    message = "this will appear"
    l.info(message)

    assert os.path.exists(fname)
    assert slurp(fname) == message
# end test_delayed_file_opening



def test_simple_rotation():
    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=CerebrumRotatingHandler
level=DEBUG
formatter=form_root
args=('%s', 'a', 10, %d, 'utf-8', '%s', '%s')
"""

    try:
        logdir = None
        logdir = mkdtemp()
        directory = 'rotate1'
        basename = 'foo'
        rotation = 2
        config_content = config_content % (logdir, rotation, directory, basename)
        config_content += "[formatter_form_root]\nformat=%(message)s"

        guerilla_clean_cerelog()
        l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
        fname = l.handlers[0].baseFilename

        message = ("0123456789", "-123456789", "+123456789", "#123456789")

        # Otherwise there is no point in testing. When there are more messages
        # than the available backlog of files, the oldest messages will
        # disappear (by design).
        assert rotation < len(message)

        for index in range(len(message)):
            # output the message (this will always force a rotation)
            l.debug(message[index])

            # How many rotated files exist when we've output message number index?
            file_count = min(index, rotation)

            # check that current file and the rotated ones thus far actually
            # exist...
            for count in range(file_count+1):
                tmp_name = fname + (count and ".%d"%count or "")
                assert os.path.exists(tmp_name)

            # some of the rotations files should not exist (yet... they will
            # be 'rotated to' later)
            for count in range(file_count+1, len(message)):
                assert not os.path.exists(fname + (".%d" % count))

            # and finally, check that the content of all of the files (current
            # and rotated) matches the messages that have been output thus
            # far.
            for count in range(file_count+1):
                content = slurp(fname + (count and ".%d" % count or ""))
                assert content == message[index-count]
    finally:
        clean_directory(logdir)
# end test_simple_rotattion



def test_substitution():
    config_content = """

[logger_root]
level=DEBUG
qualname=root
handlers=hand_root

[handler_hand_root]
class=CerebrumSubstituteHandler
level=DEBUG
formatter=form_root
args=('%s', 0, 0, 0644, %r, 'utf-8', '%s', '%s')
"""

    try:
        logdir = None
        logdir = mkdtemp()
        directory = 'rotate1'
        basename = 'foo'
        patterns = (("foo", "bar"), ("bar", "zot"))
        
        config_content = config_content % (logdir, patterns, directory, basename)
        config_content += "[formatter_form_root]\nformat=%(message)s"

        messages = (("test1", "test1"),
                    (patterns[1][0], patterns[1][1]),
                    # foo is transitively remapped to zot
                    (patterns[0][0], patterns[1][1]))
        previous = []

        for message, result in messages:
            guerilla_clean_cerelog()
            l = cerelog.get_logger(cStringIO.StringIO(config_content), "root")
            fname = l.handlers[0].baseFilename

            l.debug(message)
            chunk = slurp(fname)
            previous.append(result)
            assert chunk == "\n".join(previous)

    finally:
        clean_directory(logdir)
# end substitution
