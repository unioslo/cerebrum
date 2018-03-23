#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010 University of Oslo, Norway
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
""" Utility methods for CIS webservices. """

from Cerebrum.Utils import Factory
from Cerebrum.Errors import CerebrumError, CerebrumRPCException
import twisted.python.log
from functools import wraps

# only needed for the rpclib-types
from rpclib.model import nillable_string
from rpclib.model.primitive import DateTime as RpcDateTime, Unicode as RpcUnicode
from mx.DateTime import DateTimeType as MxDateTimeType, DateTime as MxDateTime


class SimpleLogger(object):
    """ Simple log wrapper. This logger use the same API as the Cerebrum
    logger. Set up to log to L{twisted.python.log}.
    """

    def __init__(self):
        pass

    def _log(self, *args):
        """ Log to the twisted logger."""
        # TODO: note that this has to be changed if we won't use twisted in
        # the future
        twisted.python.log.msg(' '.join(args))

    def error(self, msg, *args):
        """ Log an error. Will show up as 'ERROR: <msg>' """
        self._log('ERROR:', msg % args if args else msg)

    def warning(self, msg, *args):
        """ Log a warning. Will show up as 'WARNING: <msg>' """
        self._log('WARNING:', msg % args if args else msg)

    def info(self, msg, *args):
        """ Log a notice. Will show up as 'INFO: <msg>' """
        self._log('INFO:', msg % args if args else msg)

    def debug(self, msg, *args):
        """ Log a debug notice. Will show up as 'DEBUG: <msg>' """
        self._log('DEBUG:', msg % args if args else msg)


def require_id(method):
    """ A simple decorator that throws an error if C{self.operator_id} is
    missing or C{None}. This can be used for methods that must perform a
    permission check based on the C{account_id} of the logged in user.
    C{self.operator_id} should only be set by the authentication process.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if not getattr(self, 'operator_id', None):
            if hasattr(self, 'log'):
                self.log.debug('Method (%s) requires operator_id')
            raise CerebrumError('%s requires login')
        return method(self, *args, **kwargs)
    return wrapper


def commit_handler(dryrun=False):
    """ Decorator for I{methods} that do database write operations. 
    This method handles decorator arguments, the actual wrapper is C{wrap}.
    The decorator will only work on instance methods with a DatabaseAccessor
    attribute C{db}.

    @type dryrun: bool
    @param dryrun: If True, changes by the wrapped method will never be
                   commited.

    @rtype: method
    @return: The wrapped method
    """
    def wrap(method):
        """ This is the I{actual} decorator. It returns a wrapped C{method}.
        If the C{method} raises a C{CerebrumRPCException}, that means an
        error occured before we called any functions that may have performed
        changes in the database.
        If the C{method} encounters any other exceptions, that means the
        it failed after calling a function that may have performed a
        db change, and we should roll back.
        In all other cases, the method succeeded, and we should commit any
        changes.
        """
        # The 'wraps' decorator sets up proper __doc__ and __name__ attrs
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            """ See help L{%s} for info""" % method.__name__
            if not hasattr(self, 'db'):
                return method(self, *args, **kwargs)

            try:
                result = method(self, *args, **kwargs)
            except CerebrumRPCException, e:
                # Failed looking up arguments, nothing to roll back or commit.
                if hasattr(self, 'log'):
                    self.log.debug('Method (%s) failed: %s.' % (method, e))
                raise
            except:
                # L{method} has been called, we need to roll back.
                if hasattr(self, 'log'):
                    self.log.debug('Method (%s) failed, roll back.' % method)
                self.db.rollback()
                raise

            if hasattr(self, 'log'):
                self.log.debug('Method (%s) succeeded, Dryrun: %s' % (method, dryrun))
            if dryrun:
                self.db.rollback()
            else:
                self.db.commit()
            return result
        return wrapper
    return wrap



class CisModule(object):
    """ The base class for a CIS module. Sets up the db-connection, changelog
    and log. Contains common helper functions.
    """

    def __init__(self, name):
        """ Init

        @type name: str
        @param name: A name identifying this instance, for the changelog.
        """
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program=name)
        self.log = SimpleLogger()
        self.operator_id = None

    @commit_handler(dryrun=True)
    def test_rpc_error(self):
        # Without docstring, this looks weird on help
        raise CerebrumRPCException('test')

    @commit_handler(dryrun=True)
    def test_error(self):
        raise CerebrumError('test')

    @commit_handler(dryrun=False)
    def commit(self):
        """ Force a commit. Should really never be used. """
        pass

    def close(self):
        """Explicitly close this instance of the class. This is to make sure
        that all is closed down correctly, even if the garbage collector can't
        destroy the instance. """
        try:
            self.db.close()
        except Exception, e:
            self.log.warning("Problems with db.close: %s" % e)


# The following classes are fixes for rpclib 2.6. These classes replaces the
# classes of the same name in rpclib.model.primitive

# There's a bug in roclib.model.primitive.Unicode, it only handles text in the
# ascii charset. We need to override the to_string method, which is used to
# prepare a string before it's wrapped in a lxml.etree object.
# FIXME: This should no longer be needed if we upgrade to Spyne
class Unicode(RpcUnicode):

    @classmethod
    @nillable_string
    def to_string(cls, val):
        if isinstance(val, unicode):
            return val
        elif isinstance(val, str):
            if cls.Attributes.encoding is not None:
                return unicode(val, cls.Attributes.encoding,
                               errors=cls.Attributes.unicode_errors)
            return unicode(val, errors=cls.Attributes.unicode_errors)
        # FIXME: Else, don't know, let super() deal with it?
        return super(Unicode, cls).to_string(val)


# The mx.DateTime.DateTime objects doesn't have an 'isoformat' method (at least
# not mxDateTime <= v3.2). Passing them to rpclib.model.primitive.DateTime will
# fail. This class wraps the rpclib DateTime type to handle
# mx.DateTime.DateTime objects.
# FIXME: This is no longer neccessary if we move away from using the
# mx.DateTime module.
class DateTime(RpcDateTime):

    @classmethod
    @nillable_string
    def to_string(cls, value):
        if isinstance(value, MxDateTimeType):
            return value.Format('%Y-%m-%dT%H:%M:%S')
        # For some reason, a standard datetime object was passed
        return super(DateTime, cls).to_string(value)

    @classmethod
    @nillable_string
    def from_string(cls, string):
        # Let's make the parent parse and create a standard datetime object
        dt = super(DateTime, cls).from_string(string)
        return MxDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                          dt.second)

