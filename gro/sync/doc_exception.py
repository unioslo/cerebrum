#!/usr/bin/env python

"""Uses Exception docstrings in Exception printouts.

Copyright (c) 2002-2004 Stian Soiland

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Author: Stian Soiland <stian@soiland.no>
License: MIT
URL: http://soiland.no/software
"""


# -*- coding: iso-8859-1 -*-

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

class RealityError(DocstringException):
    """This should never happen"""
    ## example:
    ##     a = "Something"
    ##     if not a == "Something":
    ##         raise RealityError

class UnreachableCodeError(RealityError):
    """Unreachable code"""
    ## example:
    ##     if 0:
    ##         raise RealityError, "Not 0"

class ProgrammingError(DocstringException):
    """Programming error"""
    ## example:
    ##     def function(arg1=None, arg2=None):
    ##         if (arg1 and arg2) or not (arg1 or arg2):
    ##             raise ProgrammingError, "Must specify arg1 OR arg2"

def _test():
    import doctest,doc_exception
    return doctest.testmod(doc_exception)
            
if __name__ == "__main__":
    _test()    

