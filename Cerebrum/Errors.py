# -*- coding: iso-8859-1 -*-
# Copyright 2002 University of Oslo, Norway
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

"""Generic and specific exception classes for Cerebrum."""

class DocstringException(Exception):
    """Makes it easy to define more descriptive error messages.
       
       >>> class RealityError(DocstringException):
       ...     '''Unreachable point'''

       >>> raise RealityError
       Traceback (most recent call last):
         File "<stdin>", line 1, in ?
       RealityError: Unreachable point

       With argument: 
       
       >>> raise RealityError, "Outside handler"
       Traceback (most recent call last):
         File "<stdin>", line 1, in ?
       RealityError: Unreachable point: Outside handler

       Without docstring: 
       
       >>> class SomeError(RealityError):
       ...     pass    
       >>> raise SomeError
       Traceback (most recent call last):
         File "<stdin>", line 1, in ?
       SomeError
       
       Without docstring, with argument:
       
       >>> raise SomeError, 129
       Traceback (most recent call last):
         File "<stdin>", line 1, in ?
       SomeError: 129
       """
    def __str__(self):
        args = Exception.__str__(self) # Get our arguments
        
        # We'll only include the docstring if it has been defined in
        # our direct class. This avoids printing "General Error" when
        # a class SpecificError(GeneralError) just forgot to specify a
        # docstring. 
        doc = self.__class__.__doc__ 
        if args and doc:
            return doc + ': ' + args
        elif args:
            # don't worry, our class name will be printed
            return args    
        else:
            return doc or ""

class PoliteException(SystemExit):
    """Exception used to exit with an error message but no traceback.

    The argument should be a complete explanation of the error, so no
    traceback will be needed to identify and correct the problem.

    It is a subclass of the SystemExit exception, used by sys.exit()."""


class CerebrumError(DocstringException):           
    """Generic Cerebrum error"""

class RealityError(CerebrumError):
    """This should never happen"""
    ## example:
    ##     if 0:
    ##         raise RealityError, "Not 0"

class UnreachableCodeError(RealityError):
    """Unreachable code"""


class ProgrammingError(CerebrumError):
    """Programming error"""
    ## example:
    ##     def function(arg1=None, arg2=None):
    ##         if (arg1 and arg2) or not (arg1 or arg2):
    ##             raise ProgrammingError, "Must specify arg1 OR arg2"

class DatabaseException(CerebrumError):
    """Database error"""

class DatabaseConnectionError(DatabaseException, PoliteException):
    """Database connection error"""

class NotFoundError(DatabaseException):
    """Could not find"""

class TooManyRowsError(DatabaseException):
    """Too many rows"""

class NoEntityAssociationError(CerebrumError):
    # What does this mean?
    pass

def _test():
    import doctest,Errors 
    return doctest.testmod(Errors)
            
if __name__ == "__main__":
    _test()    

# arch-tag: 6918977f-ef13-4a6d-9e9b-3457e7730023
