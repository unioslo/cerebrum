# -*- coding: utf-8 -*-

# Copyright 2002-2018 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
This module contains a number of core utilities used everywhere in the tree.
"""
from __future__ import unicode_literals

import cereconf
import inspect
import os
import re
import mx.DateTime
import six
import ssl
import imaplib
import sys
import time
import traceback
import socket
import random
import collections
import unicodedata
import io

from string import ascii_lowercase, digits
from subprocess import Popen, PIPE


class _NotSet(object):
    """This class shouldn't be referred to directly, import the
    singleton, 'NotSet', instead.  It should be used as the default
    value of keyword arguments which need to distinguish between the
    caller specifying None and not specifying it at all."""

    def __new__(cls):
        if '_the_instance' not in cls.__dict__:
            cls._the_instance = object.__new__(cls)
        return cls._the_instance

    def __nonzero__(self):
        return False

    __slots__ = ()


NotSet = _NotSet()


def dyn_import(name):
    """Dynamically import python module ``name``."""
    try:
        mod = __import__(name)
    except ImportError as e:
        raise ImportError("{0} (module={1})".format(e, name))
    components = name.split(".")
    try:
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    except AttributeError as e:
        raise ImportError("{0} (module={1})".format(e, name))


def this_module():
    """Return module object of the caller."""
    caller_frame = inspect.currentframe().f_back
    global_vars = caller_frame.f_globals
    #
    # If anyone knows a better way (e.g. one that isn't based on
    # iteration over sys.modules) to get at the module object
    # corresponding to a frame/code object, please do tell!
    correct_mod = None
    for mod in filter(None, sys.modules.values()):
        if global_vars is mod.__dict__:
            assert correct_mod is None
            correct_mod = mod
    assert correct_mod is not None
    return correct_mod


# TODO: Deprecate when switching over to Python 3.x
def is_str(x):
    """Checks if a given variable is a string, but not a unicode string."""
    return isinstance(x, str)


# TODO: Deprecate when switching over to Python 3.x
def is_str_or_unicode(x):
    """Checks if a given variable is a string (str or unicode)."""
    return isinstance(x, basestring)


# TODO: Deprecate when switching over to Python 3.x
def is_unicode(x):
    """Checks if a given variable is a unicode string."""
    return isinstance(x, unicode)


def remove_control_characters(s):
    """Remove unicode control characters."""
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


# TODO: Deprecate: needlessly complex in terms of readability and end result
def _mangle_name(classname, attr):
    """Do 'name mangling' for attribute ``attr`` in class ``classname``."""
    if not (classname and is_str(classname)):
        raise ValueError("Invalid class name string: '%s'" % classname)
    # Attribute name starts with at least two underscores, and
    # ends with at most one underscore and is not all underscores
    if (attr.startswith("__") and not attr.endswith("__")) and (classname.count("_") != len(classname)):
        # Strip leading underscores from classname.
        return "_" + classname.lstrip("_") + attr
    return attr


def read_password(user, system, host=None, encoding=None):
    """Read the password 'user' needs to authenticate with 'system'.
    It is stored as plain text in DB_AUTH_DIR.

    """
    fmt = ['passwd-%s@%s']
    var = [user.lower(), system.lower()]
    # "hosts" starting with a '/' are local sockets, and should use
    # this host's password files, i.e. don't qualify password filename
    # with hostname.
    # TODO: lowercasing user names may not be a good
    # idea, e.g. FS operates with usernames starting with capital
    # 'i'...
    if host is not None and not host.startswith("/"):
        fmt.append('@%s')
        var.append(host.lower())
    format_str = ''.join(fmt)
    format_var = tuple(var)
    filename = os.path.join(cereconf.DB_AUTH_DIR,
                            format_str % format_var)
    mode = 'rb' if encoding is None else 'r'
    with io.open(filename, mode, encoding=encoding) as f:
        # .rstrip() removes any trailing newline, if present.
        dbuser, dbpass = f.readline().rstrip('\n').split('\t', 1)
        assert dbuser == user
        return dbpass


def spawn_and_log_output(cmd, log_exit_status=True, connect_to=[], shell=False):
    """Run command and copy stdout to logger.debug and stderr to
    logger.error.  cmd may be a sequence.  connect_to is a list of
    servers which will be contacted.  If debug_hostlist is set and
    does not contain these servers, the command will not be run and
    success is always reported.

    Return the exit code if the process exits normally, or the
    negative signal value if the process was killed by a signal.

    :type cmd: basestr or sequence of basestr
    :param cmd: Command, see subprocess.Popen argument args

    :type log_exit_status: bool
    :param log_exit_status: emit log message with exit status?

    :type connect_to: list of str
    :param connect_to: Spawned command will connect to resource (hostlist),
                       only runs command if cereconf.DEBUG_HOSTLIST is None,
                       or contains the given resource

    :type shell: bool
    :param shell: run command in shell, or directly with os.exec*()

    :rtype: int
    :return: spawned programme's exit status
    """
    # select on pipes and Popen3 only works in Unix.
    from select import select
    EXIT_SUCCESS = 0
    logger = Factory.get_logger()
    if cereconf.DEBUG_HOSTLIST is not None:
        for srv in connect_to:
            if srv not in cereconf.DEBUG_HOSTLIST:
                logger.debug("Won't connect to %s, won't spawn %r",
                             srv, cmd)
                return EXIT_SUCCESS

    proc = Popen(cmd, bufsize=10240, close_fds=True,
                 stdin=PIPE, stdout=PIPE, stderr=PIPE)
    pid = proc.pid
    if log_exit_status:
        logger.debug('Spawned %r, pid %d', cmd, pid)
    proc.stdin.close()
    descriptor = {proc.stdout: logger.debug,
                  proc.stderr: logger.error}
    while descriptor:
        # select() is called for _every_ line, since we can't inspect
        # the buffering in Python's file object.  This works OK since
        # select() will return "readable" for an unread EOF, and
        # Python won't read the EOF until the buffers are exhausted.
        ready, _, _ = select(descriptor.keys(), [], [])
        for fd in ready:
            line = fd.readline()
            if line == '':
                fd.close()
                del descriptor[fd]
            else:
                descriptor[fd]("[%d] %s", pid, line.rstrip())
    status = proc.wait()
    if status == EXIT_SUCCESS and log_exit_status:
        logger.debug("[%d] Completed successfully", pid)
    elif os.WIFSIGNALED(status):
        # The process was killed by a signal.
        status = os.WTERMSIG(status)
        if log_exit_status:
            logger.error('[%d] Command "%r" was killed by signal %d',
                         pid, cmd, status)
    else:
        # The process exited with an exit status
        status = os.WSTOPSIG(status)
        if log_exit_status:
            logger.error("[%d] Return value was %d from command %r",
                         pid, status, cmd)
    return status


def filtercmd(cmd, input_data):
    """Send input on stdin to a command and collect the output from stdout.

    Keyword arguments:
    cmd -- arg list, where the first element is the full path to the command
    input_data -- data to be sent on stdin to the executable

    Returns the stdout that is returned from the command. May throw an IOError.

    Example use:

    >>> filtercmd(["sed", "s/kak/ost/"], "kakekake")
    'ostekake'

    """

    p = Popen(cmd, stdin=PIPE, stdout=PIPE, close_fds=False)
    if isinstance(input_data, six.text_type):
        input_data = input_data.encode('utf-8')
    p.stdin.write(input_data)
    p.stdin.close()

    output = p.stdout.read()
    exit_code = p.wait()
    p.stdout.close()

    if exit_code:
        raise IOError("%r exited with %i" % (cmd, exit_code))

    return output


def pgp_encrypt(message, keyid):
    """Encrypts a message using PGP.

    Keyword arguments:
    message -- the message that is to be encrypted
    keyid -- the private key

    Returns the encrypted message. May throw an IOError.
    """
    cmd = [cereconf.PGPPROG] + cereconf.PGP_ENC_OPTS + \
          ['--recipient', keyid, '--default-key', keyid]

    return filtercmd(cmd, message)


def pgp_decrypt(message, keyid, passphrase):
    """Decrypts a message using PGP.

    Keyword arguments:
    message -- the message that is to be decrypted
    keyid -- the private key
    passphrase - the password

    Returns the decrypted message. May throw an IOError.
    """
    cmd = [cereconf.PGPPROG] + cereconf.PGP_DEC_OPTS + ['--default-key', keyid]

    if passphrase != "":
        cmd += cereconf.PGP_DEC_OPTS_PASSPHRASE
        message = passphrase + "\n" + message

    return filtercmd(cmd, message)


# TODO: Deprecate when switching over to Python 3.x
def to_unicode(obj, encoding='utf-8'):
    """Decode obj to unicode if it is a str (basestring is either str or unicode)."""
    if is_str(obj):
        return unicode(obj, encoding)
    return obj


# TODO: Deprecate when switching over to Python 3.x
def unicode2str(obj, encoding='utf-8'):
    """Encode unicode object to a str with the given encoding."""
    if is_unicode(obj):
        return obj.encode(encoding)
    return obj


class auto_super(type):

    """Metaclass adding a private class variable __super, set to super(cls).

    Any class C of this metaclass can use the shortcut
      self.__super.method(args)
    instead of
      super(C, self).method(args)

    Besides being slightly shorter to type, this should also be less
    error prone -- there's no longer a need to remember that the first
    argument to super() must be changed whenever one copies its
    invocation into a new class.

    NOTE: As the __super trick relies on Pythons name-mangling
          mechanism for class private identifiers, it won't work if a
          subclass has the same name as one of its base classes.  This
          is a situation that hopefully won't be very common; however,
          if such a situation does arise, the subclass's definition
          will fail, raising a ValueError.

    """
    def __init__(cls, name, bases, dict):
        super(auto_super, cls).__init__(name, bases, dict)
        attr = _mangle_name(name, '__super')
        if hasattr(cls, attr):
            # The class-private attribute slot is already taken; the
            # most likely cause for this is a base class with the same
            # name as the subclass we're trying to create.
            raise ValueError("Found '%s' in class '%s'; name clash with base class?" %
                            (attr, name))
        setattr(cls, attr, super(cls))


class mark_update(auto_super):

    """Metaclass marking objects as 'updated' per superclass.

    This metaclass looks in the class attributes ``__read_attr__`` and
    ``__write_attr__`` (which should be tuples of strings) to
    determine valid attributes for that particular class.  The
    attributes stay valid in subclasses, but assignment to them are
    handled by code objects that live in the class where they were
    defined.

    The following class members are automatically defined for classes
    with this metaclass:

    ``__updated`` (class private variable):
      Set to the empty list initially; see description of ``__setattr__``.

    ``__setattr__`` (Python magic for customizing attribute assignment):
      * When a 'write' attribute has its value changed, the attribute
        name is appended to the list in the appropriate class's
        ``__updated`` attribute.

      * 'Read' attributes can only be assigned to if there hasn't
        already been defined any attribute by that name on the
        instance.
        This means that initial assignment will work, but plain
        reassignment will fail.  To perform a reassignment one must
        delete the attribute from the instance (e.g. by using ``del``
        or ``delattr``).
      NOTE: If a class has an explicit definition of ``__setattr__``,
            that class will retain that definition.

    ``__new__``:
      Make sure that instances get ``__updated`` attributes for the
      instance's class and for all of its base classes.
      NOTE: If a class has an explicit definition of ``__new__``,
            that class will retain that definition.

    ``clear'':
      Reset all the ``mark_update''-relevant attributes of an object
      to their default values.
      NOTE: If a class has an explicit definition of ``clear'', that
            class will retain that definition.

    ``__read_attr__`` and ``__write_attr__``:
      Gets overwritten with tuples holding the name-mangled versions
      of the names they initially held.  If there was no initial
      definition, the attribute is set to the empty tuple.

    ``__xerox__``:
      Copy all attributes that are valid for this instance from object
      given as first arg.

    ``__slots__``:
      If a class has an explicit definition of ``__slots__``, this
      metaclass will add names from ``__write_attr__`` and
      ``__read_attr__`` to the class's slots.  Classes without any
      explicit ``__slots__`` are not affected by this.

    Additionally, mark_update is a subclass of the auto_super
    metaclass; hence, all classes with metaclass mark_update will also
    be subject to the functionality provided by the auto_super
    metaclass.

    A quick (and rather nonsensical) example of usage:

    >>> class A(object):
    ...     __metaclass__ = mark_update
    ...     __write_attr__ = ('breakfast',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print('A')
    ...
    >>> class B(A):
    ...     __write_attr__ = ('egg', 'sausage', 'bacon')
    ...     __read_attr__ = ('spam',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print('B')
    ...         self.__super.print_updated()
    ...
    >>> b = B()
    >>> b.breakfast = 'vroom'
    >>> b.spam = False
    >>> b.print_updated()
    A
    >>> b.egg = 7
    >>> b.print_updated()
    B
    A
    >>> b.spam = True
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
      File "Cerebrum/Utils.py", line 237, in __setattr__
        raise AttributeError, \
    AttributeError: Attribute 'spam' is read-only.
    >>> del b.spam
    >>> b.spam = True
    >>> b.spam
    True
    >>> b.egg
    7
    >>> b.sausage
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    AttributeError: sausage
    >>>

    """
    def __new__(cls, name, bases, dict):
        read = [_mangle_name(name, x) for x in
                dict.get('__read_attr__', ())]
        dict['__read_attr__'] = read
        write = [_mangle_name(name, x) for x in
                 dict.get('__write_attr__', ())]
        dict['__write_attr__'] = write
        mupdated = _mangle_name(name, '__updated')
        msuper = _mangle_name(name, '__super')

        # Define the __setattr__ method that should be used in the
        # class we're creating.
        def __setattr__(self, attr, val):
# print "%s.__setattr__:" % name, self, attr, val
            if attr in read:
            # Only allow setting if attr has no previous
            # value.
                if hasattr(self, attr):
                    raise AttributeError("Attribute '%s' is read-only." % attr)
            elif attr in write:
                if hasattr(self, attr) and val == getattr(self, attr):
                    # No change, don't set __updated.
                    return
            elif attr != mupdated:
                # This attribute doesn't belong in this class; try the
                # base classes.
                return getattr(self, msuper).__setattr__(attr, val)
            # We're in the correct class, and we've established that
            # it's OK to set the attribute.  Short circuit directly to
            # object's __setattr__, as that's where the attribute
            # actually gets its new value set.
# print "%s.__setattr__: setting %s = %s" % (self, attr, val)
            object.__setattr__(self, attr, val)
            if attr in write:
                getattr(self, mupdated).append(attr)
        dict.setdefault('__setattr__', __setattr__)

        def __new__(cls, *args, **kws):
            # Get a bound super object.
            sup = getattr(cls, msuper).__get__(cls)
            # Call base class's __new__() to perform initialization
            # and get an instance of this class.
            obj = sup.__new__(cls)
            # Add a default for this class's __updated attribute.
            setattr(obj, mupdated, [])
            return obj
        dict.setdefault('__new__', __new__)

        dont_clear = dict.get('dontclear', ())

        def clear(self):
            getattr(self, msuper).clear()
            for attr in read:
                if hasattr(self, attr) and attr not in dont_clear:
                    delattr(self, attr)
            for attr in write:
                if attr not in dont_clear:
                    setattr(self, attr, None)
            setattr(self, mupdated, [])
        dict.setdefault('clear', clear)

        def __xerox__(self, from_obj, reached_common=False):
            """Copy attributes of ``from_obj`` to self (shallowly).

            If self's class is the same as or a subclass of
            ``from_obj``s class, all attributes are copied.  If self's
            class is a base class of ``from_obj``s class, only the
            attributes appropriate for self's class (and its base
            classes) are copied.

            """
            if not reached_common and \
               name in [c.__name__ for c in from_obj.__class__.__mro__]:
                reached_common = True
            try:
                super_xerox = getattr(self, msuper).__xerox__
            except AttributeError:
                # We've reached a base class that doesn't have this
                # metaclass; stop recursion.
                super_xerox = None
            if super_xerox is not None:
                super_xerox(from_obj, reached_common)
            if reached_common:
                for attr in read + write:
                    if hasattr(from_obj, attr):
                        setattr(self, attr, getattr(from_obj, attr))
                setattr(self, mupdated, getattr(from_obj, mupdated))
        dict.setdefault('__xerox__', __xerox__)

        if hasattr(dict, '__slots__'):
            slots = list(dict['__slots__'])
            for slot in read + write + [mupdated]:
                slots.append(slot)
            dict['__slots__'] = tuple(slots)

        return super(mark_update, cls).__new__(cls, name, bases, dict)


class XMLHelper(object):

    def __init__(self, encoding='utf-8'):
        self.xml_hdr = '<?xml version="1.0" encoding="{}"?>\n'.format(encoding)

    def conv_colnames(self, cols):
        """Strip tablename prefix from column name."""
        prefix = re.compile(r"[^.]*\.")
        for i in range(len(cols)):
            cols[i] = re.sub(prefix, "", cols[i]).lower()
        return cols

    def xmlify_dbrow(self, row, cols, tag, close_tag=1, extra_attr=None):
        if close_tag:
            close_tag = "/"
        else:
            close_tag = ""
        assert(len(row) == len(cols))
        if extra_attr is not None:
            extra_attr = " " + " ".join(
                ["%s=%s" % (k, self.escape_xml_attr(extra_attr[k]))
                 for k in extra_attr.keys()])
        else:
            extra_attr = ''
        return "<%s " % tag + (
            " ".join(["%s=%s" % (x, self.escape_xml_attr(row[x]))
                      for x in cols if row[x] is not None]) +
            "%s%s>" % (extra_attr, close_tag))

    def escape_xml_attr(self, a):
        """Escapes XML attributes."""
        if isinstance(a, int):
            a = six.text_type(a)
        elif isinstance(a, mx.DateTime.DateTimeType):
            a = six.text_type(str(a))
        a = a.replace('&', "&amp;")
        a = a.replace('"', "&quot;")
        a = a.replace('<', "&lt;")
        a = a.replace('>', "&gt;")
        return '"{}"'.format(a)


class Factory(object):

    class_cache = {}
    module_cache = {}

    # mapping between entity type codes and Factory.get() components
    # used by Entity.get_subclassed_object
    type_component_map = {
        'ou': 'OU',
        'person': 'Person',
        'account': 'Account',
        'group': 'Group',
        'host': 'Host',
        'disk': 'Disk',
        'email_target': 'EmailTarget',
    }

    @staticmethod
    def get(comp):
        components = {'Entity': 'CLASS_ENTITY',
                      'OU': 'CLASS_OU',
                      'Person': 'CLASS_PERSON',
                      'Account': 'CLASS_ACCOUNT',
                      'Group': 'CLASS_GROUP',
                      'Host': 'CLASS_HOST',
                      'Disk': 'CLASS_DISK',
                      'Database': 'CLASS_DATABASE',
                      'Constants': 'CLASS_CONSTANTS',
                      'CLConstants': 'CLASS_CL_CONSTANTS',
                      'ChangeLog': 'CLASS_CHANGELOG',
                      'DBDriver': 'CLASS_DBDRIVER',
                      'EmailLDAP': 'CLASS_EMAILLDAP',
                      'EmailTarget': 'CLASS_EMAILTARGET',
                      'OrgLDIF': 'CLASS_ORGLDIF',
                      'PosixExport': 'CLASS_POSIXEXPORT',
                      'PosixLDIF': 'CLASS_POSIXLDIF',
                      'PosixUser': 'CLASS_POSIX_USER',
                      'PosixGroup': 'CLASS_POSIX_GROUP',
                      'DistributionGroup': 'CLASS_DISTRIBUTION_GROUP',
                      'Project': 'CLASS_PROJECT',
                      'Allocation': 'CLASS_ALLOCATION',
                      'AllocationPeriod': 'CLASS_ALLOCATION_PERIOD',
                      'LMSImport': 'CLASS_LMS_IMPORT',
                      'LMSExport': 'CLASS_LMS_EXPORT', }

        if comp in Factory.class_cache:
            return Factory.class_cache[comp]

        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError("Unknown component %r" % comp)

        import_spec = getattr(cereconf, conf_var)
        return Factory.make_class(comp, import_spec, conf_var)

    @staticmethod
    def make_class(name, import_spec, conf_var=None):
        """Assemble the class according to spec.

        :param name: Name of class thing.
        :type name: str, unicode

        :param sequence import_spec: Name of classes to assemble into the
            returned class. Each element of the form ``module/classname``.

        :param string conf_var: Variable in cereconf

        :return: Class
        """
        if name in Factory.class_cache:
            return Factory.class_cache[name]

        if isinstance(import_spec, (tuple, list)):
            bases = []
            for c in import_spec:
                (mod_name, class_name) = c.split("/", 1)
                mod = dyn_import(mod_name)
                try:
                    cls = getattr(mod, class_name)
                except AttributeError:
                    raise ImportError("Module '{}' has no class '{}'"
                                      .format(mod_name, class_name))
                # The cereconf.CLASS_* tuples control which classes
                # are used to construct a Factory product class.
                # Order inside such a tuple is significant for the
                # product class's method resolution order.
                #
                # A likely misconfiguration is to list a class A as
                # class_tuple[N], and a subclass of A as
                # class_tuple[N+x], as that would mean the subclass
                # won't override any of A's methods.
                #
                # The following code should ensure that this form of
                # misconfiguration won't be used.
                for override in bases:
                    if issubclass(cls, override):
                        if conf_var:
                            raise RuntimeError("Class %r should appear earlier"
                                               " in cereconf.%s, as it's a"
                                               " subclass of class %r." %
                                               (cls, conf_var, override))
                        else:
                            raise RuntimeError("Class %r should appear earlier"
                                               " than %r as it is a subclass" %
                                               (cls, override))
                bases.append(cls)
            if len(bases) == 1:
                comp_class = bases[0]
            else:
                # Dynamically construct a new class that inherits from
                # all the specified classes.  The name of the created
                # class is the same as the component name with a
                # prefix of "_dynamic_"; the prefix is there to reduce
                # the probability of `auto_super` name collision
                # problems.
                comp_class = type(str('_dynamic_' + name),
                                  tuple(bases), {})
            Factory.class_cache[name] = comp_class
            return comp_class
        else:
            raise ValueError("Invalid import spec for component %s: %r" %
                             (name, import_spec))

    @staticmethod
    def get_logger(name=None):
        """Return THE cerebrum logger.

        Although this method does very little now, we should keep our
        options open for the future.
        """

        from Cerebrum.modules import cerelog
        cerelog.setup_warnings(getattr(cereconf, 'PYTHONWARNINGS', None) or [])
        return cerelog.get_logger(cereconf.LOGGING_CONFIGFILE, name)


# TODO: Temporary, test logutils by setting a CEREBRUM_LOGUTILS environment
# variable to a non-empty value.
if os.getenv('CEREBRUM_LOGUTILS'):
    from Cerebrum.logutils import getLogger
    Factory.get_logger = staticmethod(getLogger)


def random_string(length, characters=ascii_lowercase + digits):
    """
    Generate a random string of a given length using the given characters.

    :param int length: the desired string length
    :param str characters: a set of characters to use

    :return str: returns a string of random characters
    """
    # Create a local random object for increased randomness
    # "Use os.urandom() or SystemRandom if you require a
    # cryptographically secure pseudo-random number generator."
    # docs.python.org/2.7/library/random.html#random.SystemRandom
    lrandom = random.SystemRandom()
    # pick "length" number of letters, then combine them to a string
    return ''.join([lrandom.choice(characters) for _ in range(length)])


def exception_wrapper(functor, exc_list=None, return_on_exc=None, logger=None):
    """Helper function for discarding exceptions easier.

    Occasionally we do not care about about the specific exception being
    raised in a function call, since we are interested in the return value
    from that function. There are cases where a sensible dummy value can be
    either substituted or used, instead of having to deal with exceptions and
    what not. This is especially handy for small functions that may still
    (under realistic situations) raise exceptions. An reasonable example is
    Person.get_name, where '' can very often be used instead of exceptions.

    We can wrap around a call, so that a certain exception (or a sequence
    thereof) would result in in returning a specific (dummy) value. A typical
    use case would be:

        >>> def foo(...):
        ...     # do something that may raise
        ... # end foo
        ... foo = Utils.exception_wrapper(foo, (AttributeError, ValueError),
        ...                               (None, None), logger)

    ... which would result in a warn message in the logs, if foo() raises
    AttributeError or ValueError. No restrictions are placed on the arguments
    of foo, obviously.

    @param functor:
      A callable object which we want to wrap around.
    @type functor:
      A function, a method (bound or unbound) or an object implementing
      the __call__ special method.

    @param exc_list
      A sequence of exception classes to intercept. None means that all
      exceptions are intercepted (this is the default).
    @type exc_list: a tuple, a list, a set or another class implementing
      the __iter__ special method.

    @param return_on_exc:
      Value that is returned in case we intercept an exception. This is what
      play the role of a dummy value for the caller.
    @type return_on_exc: any object.

    @return:
      A function invoking functor when called. rest and keyword arguments are
      supported.
    @rtype: function.
    """

    # if it's a single exception type, convert it to a tuple now
    if not isinstance(exc_list, (list, tuple, set)) and exc_list is not None:
        exc_list = (exc_list,)

    # IVR 2008-03-11 FIXME: We cannot use this assert until all of Cerebrum
    # exceptions actually *are* derived from BaseException. But it is a good
    # sanity check.
    # assert all(issubclass(x, BaseException) for x in exc_list)

    def wrapper(*rest, **kw_args):
        "Small wrapper that calls L{functor} while ignoring exceptions."

        # None means trap all exceptions. Use with care!
        if exc_list is None:
            try:
                return functor(*rest, **kw_args)
            except:
                if logger:
                    logger.warn(format_exception_context(*sys.exc_info()))
        else:
            try:
                return functor(*rest, **kw_args)
            except tuple(exc_list):
                if logger:
                    logger.warn(format_exception_context(*sys.exc_info()))
        return return_on_exc

    return wrapper


def format_exception_context(etype, evalue, etraceback):
    """Small helper function for printing exception context.

    This exception method helps format an exception traceback.

    The arguments are the same as the return value of sys.exc_info() call.

    @rtype: basestring
    @return:
      A string holding the context description for the specified exception. If
      no exception is specified (i.e. (None, None, None) is given), return an
      empty string.
    """

    tmp = traceback.extract_tb(etraceback)
    if not tmp:
        return ""

    filename, line, funcname, _ = tmp[-1]
    filename = os.path.basename(filename)

    return ("Exception %s occured (in context %s): %s" %
            (etype, "%s/%s() @line %s" % (filename, funcname, line),
             evalue))


def argument_to_sql(argument,
                    sql_attr_name,
                    binds,
                    transformation=lambda x: x,
                    negate=False):
    """Help deal with sequences of values for SQL generation.

    On many occasions we want to allow a scalar, many scalars as a sequence,
    or different types for the same scalar as an argument that has to be
    passed to the database backend. This function helps us accomplish that.

    For the purpose of this method a tuple, a list or a set are considered to
    be a 'sequence'. Everything else is considered 'scalar'.

    :type argument: a scalar (of any type) or a sequence thereof.
    :param argument:
        This is the value we want to pass to the database backend and the basis
        for SQL code generation. A single scalar will be turned into SQL
        expression 'x = :x', where x is derived from L{sql_attr_name}. A
        sequence of scalars will be turned into SQL expression 'x IN (:x1, :x2,
        ..., :xN)' where :x_i refers to the i'th element of L{argument} and the
        name x itself is based on L{sql_attr_name}.

        E.g. if argument=(1, 2, 3) and sql_attr_name='foo', the resulting SQL
        code will look like::

            (foo in (:foo0, :foo1, :foo2))

        and L{binds} will contain this dictionary::

            {'foo0': transformation(argument[0]),
             'foo1': transformation(argument[1]),
             'foo2': transformation(argument[2])}

        This way we avoid the possibility of SQL-injection for sequences of
        strings that we want to embed into the generated SQL.

    :type sql_attr_name: basestring
    :param sql_attr_name: Name of the column to match L{argument} to.

    :type binds: dict
    :param binds:
        Contains named parameter bindings to be passed to the SQL backend. This
        function generates new parameter bindings and it will update L{binds}.

    :type transformation: a callable
    :param transformation:
        Since this function generates SQL, we want to avoid SQL-injection by
        converting L{argument} to proper type. Additionally, since Constant
        objects are passed around freely, we want them converted to suitable
        numerical codes before embedding them into SQL. transformation is a
        function (any callable) that converts whatever L{argument} is/consists
        of into something that we can embed into SQL.

    :type negate: bool
    :param negate: Negate the expression (f.i NOT IN)

    :rtype: basestring
    :return:
        SQL expression that can be safely embedded into SQL code to be passed
        to the backend. The corresponding bindings are registered in L{binds}.
    """

    # replace . with _, to not confuse the printf-like syntax when joining
    # the safe SQL string from this function with the values from L{binds}.
    binds_name = sql_attr_name.replace('.', '_')
    compare_set = 'NOT IN' if negate else 'IN'
    compare_scalar = '!=' if negate else '='
    if (isinstance(argument, (collections.Sized, collections.Iterable)) and
            not isinstance(argument, basestring)):
        assert len(argument) > 0, "List can not be empty."
        if len(argument) == 1 and isinstance(argument, collections.Sequence):
            # Sequence with only one scalar, let's unpack and treat as scalar.
            # Has no real effect, but the SQL looks prettier.
            argument = argument[0]
        # The binds approach is very slow when argument contains lots of
        # entries, so then skip it. Also the odds for hitting the sql-query
        # cache diminishes rapidly, which is what binds is trying to aid.
        elif len(argument) > 8:
            return '(%s %s (%s))' % (
                sql_attr_name,
                compare_set,
                ', '.join(map(str, map(transformation, argument))))
        else:
            tmp = dict()
            for index, item in enumerate(argument):
                name = binds_name + str(index)
                assert name not in binds
                tmp[name] = transformation(item)

            binds.update(tmp)
            return '(%s %s (%s))' % (
                sql_attr_name,
                compare_set,
                ', '.join([':' + x for x in tmp.iterkeys()]))

    assert binds_name not in binds
    binds[binds_name] = transformation(argument)
    return "(%s %s :%s)" % (sql_attr_name, compare_scalar, binds_name)


def prepare_string(value, transform=six.text_type.lower):
    """Prepare a string for being used in SQL.

    @type value: basestring
    @param value:
      The value we want to transform from regular glob search syntax to
      the special SQL92 glob syntax.

    @type transform: a callable or None
    @param transform
      By default we lowercase the search string so we can compare with
      LOWER(column) to get case insensitive comparison.

      Send in None or some other callable to override this behaviour.
    """

    value = value.replace("*", "%")
    value = value.replace("?", "_")

    if transform:
        return transform(value)

    return value


def make_timer(logger, msg=None):
    # t = make_timer(message) logs the message and starts a stop watch.
    # t(message) logs that message and #seconds since last message.
    def timer(msg):
        prev = timer.start
        timer.start = time.time()
        timer.logger.debug("%s (%d seconds)", msg, timer.start - prev)
    if msg:
        logger.debug(msg)
    timer.start = time.time()
    timer.logger = logger
    return timer


class Messages(dict):

    """Class for handling text in different languages.

    Should be filled with messages in different languages, and the message in
    either the set language or the fallback language is returned.

        msgs = Messages(lang='no', fallback='en')

    The preferred way of adding text to Messages is through template files, e.g.
    a python file with a large python dict on the format:

        {'key1':    {'en': 'This is a test',
                     'no': 'Dette er en test',
                     'nn': 'Dette er ein test'},
         'key2':    {...},}

    Messages could be given on the form:

        msgs['key1'] = {'en': 'This is a test', 'no': 'Dette er en test'}

    and the correct string is returned by:

        >>> msgs['key1']
        'This is a test'

    """

    def __init__(self, text=None, lang='en', fallback='en', logger=None):
        self.logger = logger or Factory.get_logger()
        self.lang = lang
        self.fallback = fallback
        dict.__init__(self)
        if text:
            self.update(text)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            dict.__setitem__(self, key, value)
        else:
            raise NotImplementedError("Supports only dicts for now")

    def __getitem__(self, key):
        """
        Returns a text string by given key in either the set language, or the
        fallback language if it didn't exist.

        Throws out a KeyError if the text doesn't exist for the fallback
        language either. TODO: or should it return something else instead, e.g.
        the key, and log it?
        """
        try:
            return dict.__getitem__(self, key)[self.lang]
        except KeyError:
            self.logger.warn(
                "Message for key '%s' doesn't exist for lang '%s'",
                key, self.lang)
        return dict.__getitem__(self, key)[self.fallback]


class CerebrumIMAP4_SSL(imaplib.IMAP4_SSL):
    """
    A changed version of imaplib.IMAP4_SSL that lets the caller specify
    ssl_version in order to please older versions of OpenSSL. CRB-1246
    """
    def __init__(self,
                 host='',
                 port=imaplib.IMAP4_SSL_PORT,
                 keyfile=None,
                 certfile=None,
                 ssl_version=ssl.PROTOCOL_TLSv1):
        """
        """
        self.keyfile = keyfile
        self.certfile = certfile
        self.ssl_version = ssl_version
        imaplib.IMAP4.__init__(self, host, port)

    def open(self, host='', port=imaplib.IMAP4_SSL_PORT):
        """
        """
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port))
        # "If not specified, the default is PROTOCOL_SSLv23;...
        # Which connections succeed will vary depending on the version
        # of OpenSSL. For example, before OpenSSL 1.0.0, an SSLv23
        # client would always attempt SSLv2 connections."
        self.sslobj = ssl.wrap_socket(self.sock,
                                      self.keyfile,
                                      self.certfile,
                                      ssl_version=self.ssl_version)
        self.file = self.sslobj.makefile('rb')
