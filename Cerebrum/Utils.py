# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""

import sys
import re
import cereconf
import time
import os
import smtplib
import email
from email.MIMEText import MIMEText
import string
import new
import popen2

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
    caller_frame = sys._getframe(1)
    globals = caller_frame.f_globals
    #
    # If anyone knows a better way (e.g. one that isn't based on
    # iteration over sys.modules) to get at the module object
    # corresponding to a frame/code object, please do tell!
    correct_mod = None
    for mod in filter(None, sys.modules.values()):
        if globals is mod.__dict__:
            assert correct_mod is None
            correct_mod = mod
    assert correct_mod is not None
    return correct_mod

def sendmail(toaddr, fromaddr, subject, body, cc=None,
             charset='iso-8859-1', debug=False):
    """Sends e-mail, mime-encoding the subject.  If debug is set,
    message won't be send, and the encoded message will be
    returned."""
    msg = MIMEText(body, _charset=charset)
    msg['Subject'] = email.Header.Header(subject, charset)
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Date'] = email.Utils.formatdate(localtime=True)
    if cc:
        msg['Cc'] = cc
    if debug:
        return msg.as_string()
    smtp = smtplib.SMTP(cereconf.SMTP_HOST)
    smtp.sendmail(fromaddr, toaddr, msg.as_string())
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
            if classname[i] <> "_":
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
    f = file(name, "w")
    return f, name

def make_temp_dir(dir="/tmp", prefix="cerebrum_tmp"):
    # TODO: Assert unique filename, and avoid potential security risks
    name = make_temp_file(dir=dir, only_name=1, ext="", prefix=prefix)
    os.mkdir(name)
    return name

def latin1_to_iso646_60(s, substitute=''):
    #
    # Wash known accented letters and some common charset confusions.
    tr = string.maketrans(
        'ÆØÅæø¦¿åÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäçèéêëìíîïñòóôõöùúûüýÿ¨­¯´',
        '[\\]{|||}AAAAACEEEEIIIINOOOOOUUUUYaaaaaceeeeiiiinooooouuuuyy"--\'')
    s = string.translate(s, tr)

    xlate = {}
    for y in range(0x00, 0x1f): xlate[chr(y)] = ''
    for y in range(0x7f, 0xff): xlate[chr(y)] = ''
    xlate['Ð'] = 'Dh'
    xlate['ð'] = 'dh'
    xlate['Þ'] = 'Th'
    xlate['þ'] = 'th'
    xlate['ß'] = 'ss'
    return string.join(map(lambda x:xlate.get(x, x), s), '')

def pgp_encrypt(message, id):
    cmd = [cereconf.PGPPROG, '--recipient', id, '--default-key', id,
           '--encrypt', '--armor', '--batch', '--quiet']

    child = popen2.Popen3(cmd)
    child.tochild.write(message)
    child.tochild.close()
    msg = child.fromchild.read()
    exit_code = child.wait()
    if exit_code:
        raise IOError, "gpg exited with %i" % exit_code
    return msg

def pgp_decrypt(message, password):
    cmd = [cereconf.PGPPROG, '--batch', '--passphrase-fd', "0",
           '--decrypt', '--quiet']
    child = popen2.Popen3(cmd)
    
    child.tochild.write(password+"\n")
    child.tochild.write(message)
    child.tochild.close()
    msg = child.fromchild.read()
    exit_code = child.wait()
    if exit_code:
        raise IOError, "gpg exited with %i" % exit_code
    return msg

def format_as_int(i):
    """Get rid of PgNumeric while preserving NULL values"""
    if i is not None:
        return int(i)
    return i

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
      Iff a class has an explicit definition of ``__slots__``, this
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
            elif attr <> mupdated:
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
            extra_attr = " " + " ".join(["%s=%s" % (k, self.escape_xml_attr(extra_attr[k]))
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
        components = {'OU': 'CLASS_OU',
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
                      'EmailLDAP': 'CLASS_EMAILLDAP'}
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
        """
        Return THE cerebrum logger.

        Although this method does very little now, we should keep our
        options open for the future.
        """
        from Cerebrum.modules import cerelog

        return cerelog.get_logger(cereconf.LOGGING_CONFIGFILE_NEW, name)
    # end get_logger
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
    def __init__(self, name, mode='w', buffering=-1):
        self._name = name
        self._tmpname = self.make_tmpname(name)
        self.__file = file(self._tmpname, mode, buffering)
        self.closed = False

    def close(self):
        if self.closed: return
        ret = self.__file.close()
        self.closed = True
        if ret is None:
            # close() didn't encounter any problems.  Do validation of
            # the temporary file's contents.  If that doesn't raise
            # any exceptions rename() to the real file name.
            self.validate_output()
            os.rename(self._tmpname, self._name)
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

class SimilarSizeWriter(AtomicFileWriter):
    def set_size_change_limit(self, percentage):
        self.__percentage = percentage

    def validate_output(self):
        super(SimilarSizeWriter, self).validate_output()
        if not os.path.exists(self._name):
            return
        old = os.path.getsize(self._name)
        if old == 0:
            # Any change in size will be an infinite percent-wise size
            # change.  Treat this as if the old file did not exist at
            # all.
            return
        new = os.path.getsize(self._tmpname)
        change_percentage = 100 * (float(new)/old) - 100
        if abs(change_percentage) > self.__percentage:
            raise RuntimeError, \
                  "File size changed more than %d%%: %d -> %d (%+.1f)" % (
                self.__percentage, old, new, change_percentage)


class MinimumSizeWriter(AtomicFileWriter):
    """
    This file writer would fail, if the new file size is less than a certain
    number of bytes. All other file size changes are permitted, regardless
    of the original file's size.
    """

    def set_minimum_size_limit(self, bytes):
        self.__minimum_size = bytes
    # end set_minimum_size_limit

    def validate_output(self):
        super(MinimumSizeWriter, self).validate_output()

        new_size = os.path.getsize(self._tmpname)
        if new_size < self.__minimum_size:
            raise RuntimeError, \
                  "File is too small: current: %d, minimum allowed: %d" % (
                  new_size, self.__minimum_size )
        # fi
    # end validate_output
# end MinimumSizeWriter


class RecursiveDict(dict):
    """A variant of dict supporting recursive updates"""
    # This dict is useful for combining complex configuration dicts
    def update(self, other):
        """D.update(E) -> None. Update D from E recursive.
           Any dicts that exists in both D and E are updated recursive
           instead of being replaced.
           Note that items that are UserDicts are not updated recursive.
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
                      
                
