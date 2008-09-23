# -*- coding: iso-8859-1 -*-
# Copyright 2002-2008 University of Oslo, Norway
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

"""This module contains a number of core utilities used everywhere in the
tree.
"""

import cereconf
import filecmp
import inspect
import new
import os
import popen2
import re
import smtplib
import string
import sys
import time
import traceback


class _NotSet(object):
    """This class shouldn't be referred to directly, import the
    singleton, 'NotSet', instead.  It should be used as the default
    value of keyword arguments which need to distinguish between the
    caller specifying None and not specifying it at all."""

    def __new__(cls):
        if not '_the_instance' in cls.__dict__:
            cls._the_instance = object.__new__(cls)
        return cls._the_instance

    def __nonzero__(self):
        return False

    __slots__ = ()

NotSet = _NotSet()


def dyn_import(name):
    """Dynamically import python module ``name``."""
    mod = __import__(name)
    components = name.split(".")
    try:
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    except AttributeError, mesg:
        raise ImportError, mesg

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

def sendmail(toaddr, fromaddr, subject, body, cc=None,
             charset='iso-8859-1', debug=False):
    """Sends e-mail, mime-encoding the subject.  If debug is set,
    message won't be send, and the encoded message will be
    returned."""

    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate

    msg = MIMEText(body, _charset=charset)
    msg['Subject'] = Header(subject.strip(), charset)
    msg['From'] = fromaddr.strip()
    msg['To'] = toaddr.strip()
    msg['Date'] = formatdate(localtime=True)
    if cc:
        msg['Cc'] = cc
    if debug:
        return msg.as_string()
    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    smtp.sendmail(fromaddr, toaddr, msg.as_string())
    smtp.quit()


def mail_template(recipient, template_file, sender=None, cc=None,
                  substitute={}, charset='iso-8859-1', debug=False):
    """Read template from file, perform substitutions based on the
    dict, and send e-mail to recipient.  The recipient and sender
    e-mail address will be used as the defaults for the To and From
    headers, and vice versa for sender.  These values are also made
    available in the substitution dict as the keys 'RECIPIENT' and
    'SENDER'.

    When looking for replacements in the template text, it has to be
    enclosed in ${}, ie. '${SENDER}', not just 'SENDER'.  The template
    should contain at least a Subject header.  Make each header in the
    template a single line, it will be folded when sent.  Note that
    due to braindamage in Python's email module, only Subject and the
    body will be automatically MIME encoded.  The lines in the
    template should be terminated by LF, not CRLF.

    """
    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate, getaddresses

    if not template_file.startswith('/'):
        template_file = cereconf.TEMPLATE_DIR + "/" + template_file
    f = open(template_file)
    message = "".join(f.readlines())
    f.close()
    substitute['RECIPIENT'] = recipient
    if sender: substitute['SENDER'] = sender
    for key in substitute:
        message = message.replace("${%s}" % key, substitute[key])

    headers, body = message.split('\n\n', 1)
    msg = MIMEText(body, _charset=charset)
    # Date is always set, and shouldn't be in the template
    msg['Date'] = formatdate(localtime=True)
    preset_fields = {'from': sender,
                     'to': recipient,
                     'subject': '<none>'}
    for header in headers.split('\n'):
        field, value = header.split(':', 1)
        field = field.strip().lower()
        value = value.strip()
        if field in preset_fields:
            preset_fields[field] = value
        else:
            msg[field] = Header(value)
    msg['From'] = Header(preset_fields['from'])
    msg['To'] = Header(preset_fields['to'])
    msg['Subject'] = Header(preset_fields['subject'], charset)
    # recipients in smtp.sendmail should be a list of RFC 822
    # to-address strings
    to_addrs = [recipient]
    if cc:
        to_addrs.extend(cc)
        msg['Cc'] = ', '.join(cc)

    if debug:
        return msg.as_string()

    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    smtp.sendmail(sender or getaddresses([preset_fields['from']])[0][1],
                  to_addrs, msg.as_string())
    smtp.quit()


def separate_entries(rows, *predicates):
    """Separate ``rows`` into (keep, reject) tuple based on ``predicates``.

    The ``rows`` argument should be a sequence of db_row.py-generated
    objects.  Each element in ``predicates`` should be a (key, value)
    tuple, and is a formulation of a test expression.  The key must be
    a valid attribute name of each row object.

    The rows are separated according to these rules:
    1. By default rows go to the keep list.
    2. If a predicate's `value` is None, that predicate is ignored.
    3. Compare each predicate's `value` with the attribute whose name
       is `key` in each row.  Rows matching all predicates go to the
       keep list, while the rest end up in the reject list.

    """
    keep = []
    reject = []
    for row in rows:
        ok = 1
        for key, value in predicates:
            if value is None:
                continue
            ok = (row[key] == value)
            if not ok:
                break
        if ok:
            keep.append(row)
        else:
            reject.append(row)
    return (keep, reject)

def keep_entries(rows, *predicates):
    """Return the 'keep' part of separate_entries() return value."""
    return separate_entries(rows, *predicates)[0]

def reject_entries(rows, *predicates):
    """Return the 'reject' part of separate_entries() return value."""
    return separate_entries(rows, *predicates)[1]

def mangle_name(classname, attr):
    """Do 'name mangling' for attribute ``attr`` in class ``classname``."""
    if not classname or not isinstance(classname, str):
        raise ValueError, "Not a valid class name: '%s'" % classname
    if attr.startswith("__") and not attr.endswith("__"):
        # Attribute name starts with at least two underscores, and
        # ends with at most one underscore.
        #
        # Strip leading underscores from classname.
        for i in range(len(classname)):
            if classname[i] != "_":
                classname = classname[i:]
                break
        if classname and classname[0] == "_":
            # classname is all underscores.  No mangling.
            return attr
        return '_' + classname + attr
    return attr

def make_temp_file(dir="/tmp", only_name=0, ext="", prefix="cerebrum_tmp"):
    # TODO: Assert unique filename, and avoid potential security risks
    name = "%s/%s.%s%s" % (dir, prefix, time.time(), ext)
    if only_name:
        return name
    f = open(name, "w")
    return f, name

def make_temp_dir(dir="/tmp", prefix="cerebrum_tmp"):
    # TODO: Assert unique filename, and avoid potential security risks
    name = make_temp_file(dir=dir, only_name=1, ext="", prefix=prefix)
    os.mkdir(name)
    return name

# U-umlaut is treated specially and is therefore defined in
# latin1_specials to be transcribed to 'ue' instead of the single
# character 'u'. The reason for this is a wish for email addresses to
# reflect the common transcribation choice for this
# character. O-umlaut and a-umlaut are not getting such special
# treatment.
_latin1_specials = {'�': 'Dh',  '�': 'dh',
                    '�': 'Th',  '�': 'th',
                    '�': 'ss',  '�': 'Ue',
                    '�': 'ue'}
_latin1_wash_cache = {}

def latin1_wash(data, target_charset, expand_chars=False, substitute=''):
    # TBD: The code in this function is rather messy, as it tries to
    # deal with multiple combinations of target charsets etc.  It
    # *might* be worth it to reimplement this stuff as a few proper
    # Python codecs, i.e. registered via codecs.register() and hence
    # usable via the Python builtin str.encode().  On the other hand,
    # that might be seen as involving excess amounts of magic for such
    # an apparently simple task.
    key = (target_charset, bool(expand_chars), substitute)
    try:
        (tr, xlate_subst, xlate_match) = _latin1_wash_cache[key]
    except KeyError:
        tr_from = ('������[\\]{|}��'
                   '�������������������������������������������������'
                   '����')
        xlate = _latin1_specials.copy()
        if target_charset == 'iso646-60':
            tr_to = ('[\\]{|}[\\]{|}||'
                     'AAAAACEEEEIIIINOOOOOUUUYaaaaaceeeeiiiinooooouuuyy'
                     '"--\'')
            xlate_re = '[^\x1f-\x7e\xff]'  # Should be [^\x20-\x7e].
        elif target_charset == 'POSIXname':
            tr_to = ('AOAaoaAOAaoaoo'
                     'AAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuyy'
                     '"--\'')
            if expand_chars:
                xlate.update({'�': 'Ae', '�': 'ae',  '�': 'Aa', '�': 'aa',
                              '�': 'Ue', '�': 'ue'})
            xlate_re = r'[^a-zA-Z0-9 -]'
        else:
            raise ValueError, "Unknown target charset: %r" % (target_charset,)

        tr = dict(zip(tr_from, tr_to))
        for ch in filter(xlate.has_key, tr_from):
            del tr[ch]
        tr = string.maketrans("".join(tr.keys()), "".join(tr.values()))

        xlate_re = re.compile(xlate_re)
        for ch in filter(xlate_re.match, tr):
            xlate.setdefault(ch, substitute)

        (tr, xlate_subst, xlate_match) = _latin1_wash_cache[key] = (
            tr, xlate_re.sub, lambda match: xlate[match.group()])

    return xlate_subst(xlate_match, str(data).translate(tr))

_lat1_646_tr = string.maketrans(
    '�������������������������������������������������������������',
    '[\\]{|||}AAAAACEEEEIIIINOOOOOUUUYaaaaaceeeeiiiinooooouuuyy"--\'')
_lat1_646_subst = re.compile('[^\x1f-\x7e\xff]').sub  # Should be [^\x20-\x7e].
_lat1_646_cache = {}

def latin1_to_iso646_60(s, substitute=''):
    #
    # Wash known accented letters and some common charset confusions.
    try:
        xlate_match = _lat1_646_cache[substitute]
    except KeyError:
        xlate = _latin1_specials.copy()
        for ch in filter(_lat1_646_subst.__self__.match, _lat1_646_tr):
            xlate.setdefault(ch, substitute)
        xlate_match = _lat1_646_cache[substitute] = lambda m: xlate[m.group()]

    return _lat1_646_subst(xlate_match, str(s).translate(_lat1_646_tr))

def read_password(user, system, host=None):
    """Read the password 'user' needs to authenticate with 'system'.
    It is stored as plain text in DB_AUTH_DIR.

    """
    fmt = ['passwd-%s@%s']
    var = [user.lower(), system.lower()]
    # "hosts" starting with a '/' are local sockets, and should use
    # this host's password files, i.e. don't qualify password filename
    # with hostname.
    if host is not None and not host.startswith("/"):
        fmt.append('@%s')
        var.append(host.lower())
    format_str = ''.join(fmt)
    format_var = tuple(var)
    filename = os.path.join(cereconf.DB_AUTH_DIR,
                            format_str % format_var)
    f = file(filename)
    try:
        # .rstrip() removes any trailing newline, if present.
        dbuser, dbpass = f.readline().rstrip('\n').split('\t', 1)
        assert dbuser == user
        return dbpass
    finally:
        f.close()


def spawn_and_log_output(cmd, log_exit_status=True, connect_to=[]):
    """Run command and copy stdout to logger.debug and stderr to
    logger.error.  cmd may be a sequence.  connect_to is a list of
    servers which will be contacted.  If debug_hostlist is set and
    does not contain these servers, the command will not be run and
    success is always reported.

    Return the exit code if the process exits normally, or the
    negative signal value if the process was killed by a signal.

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

    proc = popen2.Popen3(cmd, capturestderr=True, bufsize=10240)
    pid = proc.pid
    if log_exit_status:
        logger.debug('Spawned %r, pid %d', cmd, pid)
    proc.tochild.close()
    descriptor = {proc.fromchild: logger.debug,
                  proc.childerr: logger.error}
    while descriptor:
        # select() is called for _every_ line, since we can't inspect
        # the buffering in Python's file object.  This works OK since
        # select() will return "readable" for an unread EOF, and
        # Python won't read the EOF until the buffers are exhausted.
        ready, x, x = select(descriptor.keys(), [], [])
        for fd in ready:
            line = fd.readline()
            if line == '':
                fd.close()
                del descriptor[fd]
            else:
                descriptor[fd]("[%d] %s" % (pid, line.rstrip()))
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


def pgp_encrypt(message, keyid):
    cmd = [cereconf.PGPPROG]
    cmd.extend(cereconf.PGP_ENC_OPTS)
    cmd.extend(('--recipient', keyid, '--default-key', keyid))

    child = popen2.Popen3(cmd)
    child.tochild.write(message)
    child.tochild.close()
    msg = child.fromchild.read()
    exit_code = child.wait()
    if exit_code:
        raise IOError, "%r exited with %i" % (cmd, exit_code)
    return msg

def pgp_decrypt(message, keyid, passphrase):
    """Decrypt message using the private key with ID keyid.  """
    
    cmd = [cereconf.PGPPROG]
    cmd.extend(cereconf.PGP_DEC_OPTS)
    cmd.extend(('--default-key', keyid))
    if passphrase != "":
        cmd.extend(cereconf.PGP_DEC_OPTS_PASSPHRASE)

    child = popen2.Popen3(cmd)

    if passphrase != "":
        child.tochild.write(passphrase + "\n")
    child.tochild.write(message)
    child.tochild.close()
    msg = child.fromchild.read()
    exit_code = child.wait()
    if exit_code:
        raise IOError, "%r exited with %i" % (cmd, exit_code)
    return msg


def format_as_int(i):
    """Get rid of PgNumeric while preserving NULL and unset values."""
    if i is None or i is NotSet:
        return i
    return int(i)


def to_unicode(obj, encoding='utf-8'):
    """
    Decode obj to unicode if it is a basestring.
    """
    if isinstance(obj, basestring):
        if not isinstance(obj, unicode):
            obj = unicode(obj, encoding)
    return obj


def shorten_name(name, max_length=30, method='initials', encoding='utf-8'):
    """
    Shorten a name by a given or default method if it's too long.
    Possible methods are 'initials' and 'truncate'.

    name is handled as unicode internally, and then decoded back if
    neccessary before it is returned.
    """
    def get_initials(name):
        tmp = name.split()
        # Try making initials
        if len(tmp) == 1:
            return tmp[0] + "."
        elif len(tmp) > 1:
            return ". ".join([x[0] for x in tmp]) + "."

    # Some sanity checks
    assert isinstance(name, basestring) and len(name) > 0 and max_length > 0
    if len(name) <= max_length:
        return name
    # Decode to unicode before shortening
    name_uni = to_unicode(name, encoding=encoding)
    # then shorten name
    if method == 'initials':
        ret = get_initials(name_uni)
        if len(ret) > max_length:
            # If intitials doesn't work, truncate
             return shorten_name(name, max_length=max_length, method='truncate')
    elif method == 'truncate':
        ret = name_uni[:max_length].strip()
    else:
        raise AssertionError("Unknown method value: %s" % method)
    # encode if name's type is str before returning
    if isinstance(name, str):
        return ret.encode(encoding)
    else:
        return ret
    

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
        attr = mangle_name(name, '__super')
        if hasattr(cls, attr):
            # The class-private attribute slot is already taken; the
            # most likely cause for this is a base class with the same
            # name as the subclass we're trying to create.
            raise ValueError, \
                  "Found '%s' in class '%s'; name clash with base class?" % \
                  (attr, name)
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
    ...             print  'A'
    ...
    >>> class B(A):
    ...     __write_attr__ = ('egg', 'sausage', 'bacon')
    ...     __read_attr__ = ('spam',)
    ...     def print_updated(self):
    ...         if self.__updated:
    ...             print  'B'
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
    1
    >>> b.egg
    7
    >>> b.sausage
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    AttributeError: sausage
    >>>

    """
    def __new__(cls, name, bases, dict):
        read = [mangle_name(name, x) for x in
                dict.get('__read_attr__', ())]
        dict['__read_attr__'] = read
        write = [mangle_name(name, x) for x in
                 dict.get('__write_attr__', ())]
        dict['__write_attr__'] = write
        mupdated = mangle_name(name, '__updated')
        msuper = mangle_name(name, '__super')

        # Define the __setattr__ method that should be used in the
        # class we're creating.
        def __setattr__(self, attr, val):
##            print "%s.__setattr__:" % name, self, attr, val
            if attr in read:
                # Only allow setting if attr has no previous
                # value.
                if hasattr(self, attr):
                    raise AttributeError, \
                          "Attribute '%s' is read-only." % attr
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
##            print "%s.__setattr__: setting %s = %s" % (self, attr, val)
            object.__setattr__(self, attr, val)
            if attr in write:
                getattr(self, mupdated).append(attr)
        dict.setdefault('__setattr__', __setattr__)

        def __new__(cls, *args, **kws):
            # Get a bound super object.
            sup = getattr(cls, msuper).__get__(cls)
            # Call base class's __new__() to perform initialization
            # and get an instance of this class.
            obj = sup.__new__(cls, *args, **kws)
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
    xml_hdr = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'

    def conv_colnames(self, cols):
        "Strip tablename prefix from column name"
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
            " ".join(["%s=%s" % (cols[i], self.escape_xml_attr(row[i]))
                      for i in range(len(cols)) if row[i] is not None])+
            "%s%s>" % (extra_attr, close_tag))

    def escape_xml_attr(self, a):
        """Escapes XML attributes.  Expected input format is iso-8859-1"""
        a = str(a).replace('&', "&amp;")
        a = a.replace('"', "&quot;")
        a = a.replace('<', "&lt;")
        a = a.replace('>', "&gt;")
        # http://www.w3.org/TR/1998/REC-xml-19980210.html#NT-Char
        # x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] |
        # [#x10000-#x10FFFF] /* any Unicode character, excluding the
        # surrogate blocks, FFFE, and FFFF. */
        a = re.sub('[^\x09\x0a\x0d\x20-\xff]', '.', a)
        return '"%s"' % a

class Factory(object):
    class_cache = {}
    module_cache = {}
    # mapping between entity type codes and Factory.get() components
    # (user by Entity.object_by_entityid)
    type_component_map = {
        'ou': 'OU',
        'person': 'Person',
        'account': 'Account',
        'group': 'Group',
        'host': 'Host',
        'disk': 'Disk',
    }

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
                      'OrgLDIF': 'CLASS_ORGLDIF',
                      'PosixLDIF': 'CLASS_POSIXLDIF',
                      'PosixUser' : 'CLASS_POSIX_USER',
                      'PosixGroup' : 'CLASS_POSIX_GROUP',
                      'Project': 'CLASS_PROJECT',
                      'Allocation': 'CLASS_ALLOCATION',
                      'AllocationPeriod': 'CLASS_ALLOCATION_PERIOD',
                      'FS': 'CLASS_FS',
                      'LMSImport': 'CLASS_LMS_IMPORT',
                      'LMSExport': 'CLASS_LMS_EXPORT',}
        if Factory.class_cache.has_key(comp):
            return Factory.class_cache[comp]
        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError, "Unknown component %r" % comp
        import_spec = getattr(cereconf, conf_var)
        if isinstance(import_spec, (tuple, list)):
            bases = []
            for c in import_spec:
                (mod_name, class_name) = c.split("/", 1)
                mod = dyn_import(mod_name)
                cls = getattr(mod, class_name)
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
                        raise RuntimeError, \
                              ("Class %r should appear earlier in"
                               " cereconf.%s, as it's a subclass of"
                               " class %r." % (cls, conf_var, override))
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
                comp_class = type('_dynamic_' + comp, tuple(bases), {})
            Factory.class_cache[comp] = comp_class
            return comp_class
        else:
            raise ValueError, \
                  "Invalid import spec for component %s: %r" % (comp,
                                                                import_spec)
    get = staticmethod(get)



    def get_logger(name = None):
        """Return THE cerebrum logger.

        Although this method does very little now, we should keep our
        options open for the future.
        """
        from Cerebrum.modules import cerelog

        return cerelog.get_logger(cereconf.LOGGING_CONFIGFILE, name)
    get_logger = staticmethod(get_logger)
    


    def get_module(comp):
        components = {
            'ClientAPI': 'MODULE_CLIENTAPI',
        }
        if Factory.class_cache.has_key(comp):
            return Factory.class_cache[comp]
        try:
            conf_var = components[comp]
        except KeyError:
            raise ValueError, "Unknown component %r" % comp
        import_spec = getattr(cereconf, conf_var)
        if isinstance(import_spec, (tuple, list)):
            bases = []
            for mod_name in import_spec:
                mod = dyn_import(mod_name)
                bases.append(mod)
            if len(bases) == 1:
                comp_module = bases[0]
            else:
                # Dynamically construct a new module that inherits from
                # all the specified modules.  The name of the created
                # module is the same as the component name with a
                # prefix of "_dynamic_"
                comp_module = new.module('_dynamic_' + comp)
                # Join namespaces, latest first
                for module in bases:
                    for (key, value) in module.__dict__:
                        # Only set it if it isn't there already
                        comp_module.setdefault(key, value)

            Factory.class_cache[comp] = comp_module
            return comp_module
        else:
            raise ValueError, \
                  "Invalid import spec for component %s: %r" % (comp,
                                                                import_spec)
    get_module = staticmethod(get_module)          
        

class fool_auto_super(object):
    def __getattr__(self, attr):
        def no_op(*args, **kws):
            pass
        return no_op

##         # auto_super's .__super attribute should never continue beyond
##         # this class.
##         self.__super = fool_auto_super()


def random_string(length, population='abcdefghijklmnopqrstuvwxyz0123456789'):
    import random
    random.seed()
    return ''.join([random.choice(population) for i in range(length)])


class AtomicFileWriter(object):
    def __init__(self, name, mode='w', buffering=-1, replace_equal=False):
        self._name = name
        self._tmpname = self.make_tmpname(name)
        self.__file = open(self._tmpname, mode, buffering)
        self.closed = False
        self.replaced_file = False
        self._replace_equal = replace_equal

    def close(self, dont_rename=False):
        if self.closed: return
        ret = self.__file.close()
        self.closed = True
        if ret is None:
            # close() didn't encounter any problems.  Do validation of
            # the temporary file's contents.  If that doesn't raise
            # any exceptions rename() to the real file name.
            self.validate_output()
            if not self._replace_equal:
                if (os.path.exists(self._name) and
                    filecmp.cmp(self._tmpname, self._name, shallow=0)):
                    os.unlink(self._tmpname)
                else:
                    if not dont_rename:
                        os.rename(self._tmpname, self._name)
                    self.replaced_file = True
            else:
                if not dont_rename:
                    os.rename(self._tmpname, self._name)
                self.replaced_file = True
        return ret

    def validate_output(self):
        """Validate output (i.e. the temporary file) prior to renaming it.

        This method is intended to be overridden in subclasses.  If
        the content fails to meet the method's expectations, it should
        raise an exception.

        """
        pass

    def make_tmpname(self, realname):
        for i in range(10):
            name = realname + '.' + random_string(5)
            if not os.path.exists(name):
                break
        else:
            raise IOError, "Unable to find available temporary filename"
        return name

    def flush(self):
        return self.__file.flush()

    def write(self, data):
        return self.__file.write(data)



class FileSizeChangeError(RuntimeError):
    """Indicates a problem related to change in file size for files
    updated by the *SizeWriter classes.

    """


class FileChangeTooBigError(FileSizeChangeError):
    """Indicates that a file has either grown or been reduced beyond
    acceptable limits.

    """


class SimilarSizeWriter(AtomicFileWriter):
    """This file writer will fail if the file size has changed by more
    than a certain percentage (if using 'set_size_change_limit')
    and/or by a certain number of lines (if using
    'set_line_count_change_limit') from the old to the new version.

    Clients will normally govern the exact limits for 'similar size'
    themselves, but there are times when it is convenient to have
    central overrides/modifications of these values. SimilarSizeWriter
    therefore makes use of the following 'cereconf'-variables:

    SIMILARSIZE_CHECK_DISABLED - If this is set to True, no checks
    will be done when validating the file size, i.e. validation will
    always succeed.

    SIMILARSIZE_LIMIT_MULTIPLIER - Modifies the change limit by
    multiplying it by the given number (default is 1.0, i.e. to not
    modify the value given by the client)

    Since central changes to the defaults for these values (especially
    central disabling) is risky, non-default values for these
    variables will generate warnings via the logger.

    Clients can also disable/enable the checks directly by calling the
    'set_checks_enabled', though this will not override
    SIMILARSIZE_CHECK_DISABLED.

    """

    
    __checks_enabled = True


    def __init__(self, *args, **kwargs):
        super(SimilarSizeWriter, self).__init__(*args, **kwargs)
        self.__percentage = self.__line_count = None
        self._logger = Factory.get_logger("cronjob")


    def set_checks_enabled(self, new_enabled_status):
        """Method for activating (new_enabled_status is 'True') or
        de-activating (new_enabled_status is 'False') all similar size
        checks being run by a given program.

        Default state, before this method has been called, is for
        checks to be enabled.

        """
        self._logger.debug("SimilarSizeWriter: setting checks_enabled to '%s'"
                           % new_enabled_status)
        SimilarSizeWriter.__checks_enabled = new_enabled_status


    def set_size_change_limit(self, percentage):
        """Method for setting a limit based on percentage change in
        file size (bytes). The exact percentage can be centrally
        modified by setting SIMILARSIZE_SIZE_LIMIT_MULTIPLIER to
        something other than 1.0 in cereconf.

        """
        self.__percentage = percentage * cereconf.SIMILARSIZE_LIMIT_MULTIPLIER
        if cereconf.SIMILARSIZE_LIMIT_MULTIPLIER != 1.0:            
            self._logger.warning("SIMILARSIZE_LIMIT_MULTIPLIER is set to "
                                 "a value other than 1.0; change limit "
                                 "will be %s%% rather than client's explicit "
                                 "setting of %s%%.",
                                 self.__percentage, percentage)
        self._logger.debug("SimilarSize size change limit set to '%d'",
                           self.__percentage)


    def set_line_count_change_limit(self, num):
        """Method for setting a limit based on change in number of
        lines in the generated file. The exact number can be centrally
        modified by setting SIMILARSIZE_SIZE_LIMIT_MULTIPLIER to
        something other than 1.0 in cereconf.

        """
        self.__line_count = num * cereconf.SIMILARSIZE_LIMIT_MULTIPLIER
        if cereconf.SIMILARSIZE_LIMIT_MULTIPLIER != 1.0:            
            self._logger.warning(("SIMILARSIZE_LIMIT_MULTIPLIER is set to " +
                                 "a value other than 1.0; change limit " +
                                 "will be %s lines rather than client's "
                                 "explicit " +
                                 "setting of %s lines.")
                                 % (self.__line_count, num))
        self._logger.debug("SimilarSize line count change limit set to '%d'"
                           % self.__line_count)


    def __count_lines(self, fname):
        count = 0
        for line in open(fname):
            count = count + 1
        return count


    def validate_output(self):
        """Checks if the new file's size change (compared to the old
        file) is within acceptable limits as previously set. If the
        file did not exist or if the old file was empty, the new file
        will be considered 'valid' no matter how large or small it is.

        If neither file size nor line count are set, an AssertionError
        will be raised.

        If SIMILARSIZE_CHECK_DISABLED is set to 'True' in cereconf,
        validation will always succeed, no matter what, as is the case
        if 'set_checks_enabled(False)' has been called.
    
        """
        if cereconf.SIMILARSIZE_CHECK_DISABLED:
            # Having the check globally disabled is not A Good Thing(tm),
            # so we warn about it, in all cases.
            self._logger.warning("SIMILARSIZE_CHECK_DISABLED is 'True'; no "
                                 "'similar filesize' comparisons will be done.")
            return
        if not SimilarSizeWriter.__checks_enabled:
            # Checks have been specifically disabled by a client, but
            # we'll still inform them about it, in case they don't
            # realize it
            self._logger.info("Client has disabled similarsize checks for now;"
                              "no 'similar filesize' comparisons will be done.")
            return            
        if not os.path.exists(self._name):
            return
        old = os.path.getsize(self._name)
        if old == 0:
            # Any change in size will be an infinite percent-wise size
            # change.  Treat this as if the old file did not exist at
            # all.
            return
        new = os.path.getsize(self._tmpname)
        assert self.__percentage or self.__line_count
        if self.__percentage:
            change_percentage = 100 * (float(new)/old) - 100
            if abs(change_percentage) > self.__percentage:
                raise FileChangeTooBigError(
                      "%s: File size changed more than %d%%: "
                      "%d -> %d (%+.1f)" % (self._name, self.__percentage,
                                            old, new, change_percentage))
        if self.__line_count:
            old = self.__count_lines(self._name)
            new = self.__count_lines(self._tmpname)
            if abs(old - new) > self.__line_count:
                raise FileChangeTooBigError(
                      "%s: File changed more than %d lines: "
                      "%d -> %d (%i)" % (self._name, self.__line_count,
                                         old, new, abs(old-new)))



class FileTooSmallError(FileSizeChangeError):
    """Indicates that the new version of the file in question is below
    acceptable size.

    """


class MinimumSizeWriter(AtomicFileWriter):
    """This file writer would fail, if the new file size is less than
    a certain number of bytes. All other file size changes are
    permitted, regardless of the original file's size.
    """

    def set_minimum_size_limit(self, bytes):
        self.__minimum_size = bytes

    def validate_output(self):
        super(MinimumSizeWriter, self).validate_output()

        new_size = os.path.getsize(self._tmpname)
        if new_size < self.__minimum_size:
            raise FileTooSmallError, \
                  "%s: File is too small: current: %d, minimum allowed: %d" % \
                  (self._name, new_size, self.__minimum_size)



class RecursiveDict(dict):
    """A variant of dict supporting recursive updates"""
    # This dict is useful for combining complex configuration dicts
    def __init__(self, values={}):
        # Make sure our __setitem__ is called.
        for (key, value) in values.items():
            self[key] = value

    def update(self, other):
        """D.update(E) -> None. Update D from E recursively.  Any
        dicts that exists in both D and E are updated (merged)
        recursively instead of being replaced. Note that items that
        are UserDicts are not updated recursively.
        """
        for (key, value) in other.items():
            if (key in self and 
                isinstance(self[key], RecursiveDict) and 
                isinstance(value, dict)):
                self[key].update(value)
            else:
                self[key] = value

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            # Wrap it, make sure it follows our rules
            value = RecursiveDict(value)
        dict.__setitem__(self, key, value)


def simple_memoize(callobj):
    """Memoize[1] a callable.

    [1] <http://en.wikipedia.org/wiki/Memoize>.
    
    The idea is to memoize a callable object supporting rest/optional
    arguments without placing a limit on the amount of cached pairs. This is
    useful for mapping ou_id to names and such (i.e. situations where the
    number of cached values is small, and the information is requested many
    times for the same 'key').

    NB! keyword arguments ARE NOT supported.

    @type callobj: callable
    @param callobj:
      An object for which callable(callobj) == True. I.e. something we can
      call (lambda, function, bound method, etc.)

    @rtype: function
    @return:
      A wrapper that caches the results of previous invocations of callobj.
    """
    
    cache = dict()
    def wrapper(*rest):
        if rest not in cache:
            cache[rest] = callobj(*rest)
        return cache[rest]
    # end wrapper

    return wrapper
# end simple_memoize



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
    # end wrapper
 
    return wrapper
# end exception_wrapper



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
    
    filename, line, funcname, text = tmp[-1]
    filename = os.path.basename(filename)

    return ("Exception %s occured (in context %s): %s" %
            (etype, "%s/%s() @line %s" % (filename, funcname, line),
             evalue))
# end _format_exc_context



def argument_to_sql(argument, sql_attr_name, binds,
                    transformation=lambda x: x):
    """Help deal with sequences of values for SQL generation.

    On many occasions we want to allow a scalar, many scalars as a sequence,
    or different types for the same scalar as an argument that has to be
    passed to the database backend. This function helps us accomplish that.

    For the purpose of this method a tuple, a list or a set are considered to
    be a 'sequence'. Everything else is considered 'scalar'.

    @type argument: a scalar (of any type) or a sequence thereof.
    @param argument:
      This is the value we want to pass to the database backend and the basis
      for SQL code generation. A single scalar will be turned into SQL
      expression 'x = :x', where x is derived from L{sql_attr_name}. A
      sequence of scalars will be turned into SQL expression
      'x IN (:x1, :x2, ..., :xN)' where :x_i refers to the i'th element of
      L{argument} and the name x itself is based on L{sql_attr_name}.

      E.g. if argument=(1, 2, 3) and sql_attr_name='foo', the resulting SQL
      code will look like::

          (foo in (:foo0, :foo1, :foo2))

      and L{binds} will contain this dictionary::

          {'foo0': transformation(argument[0]),
           'foo1': transformation(argument[1]),
           'foo2': transformation(argument[2])}

      This way we avoid the possibility of SQL-injection for sequences of
      strings that we want to embed into the generated SQL.

    @type sql_attr_name: basestring
    @param sql_attr_name:
      The SQL code generated by this function refers to a specific column by
      name; this parameter contains that name. Additionally, since the
      attribute names are often prefixed with a table name, we extract the
      very last component of the name, when we seek to name the L{binds}
      attribute. E.g. column 'bar' of table 'foo' can be named 'foo.bar', in
      which case the corresponding L{binds}' key will be 'bar'.

    @type binds: dict
    @param binds:
      Contains named parameter bindings to be passed to the SQL backend. This
      function generates new parameter bindings and it will update L{binds}.

    @type transformation: a callable
    @param transformation:
      Since this function generates SQL, we want to avoid SQL-injection by
      converting L{argument} to proper type. Additionally, since Constant
      objects are passed around freely, we want them converted to suitable
      numerical codes before embedding them into SQL. transformation is a
      function (any callable) that converts whatever L{argument} is/consists
      of into something that we can embed into SQL.

    @rtype: basestring
    @return:
      SQL expression that can be safely embedded into SQL code to be passed to
      the backend. The corresponding bindings are registered in L{binds}.
    """

    # last component of the name in binds, so that column bar of
    # table foo (i.e. foo.bar) is named 'bar' in binds.
    binds_name = sql_attr_name.split(".")[-1]

    if isinstance(argument, (tuple, set, list)) and argument:
        tmp = dict()
        for index, item in enumerate(argument):
            name = binds_name + str(index)
            assert name not in binds
            tmp[name] = transformation(item)

        binds.update(tmp)
        return ("(%s IN (%s))" % (sql_attr_name,
                                  ", ".join([":" + x for x in tmp.iterkeys()])))
    else:
        assert binds_name not in binds
        binds[binds_name] = transformation(argument)
        return "(%s = :%s)" % (sql_attr_name, binds_name)

    return ""
# end argument_to_sql
