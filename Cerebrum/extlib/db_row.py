# -*- coding: iso-8859-1 -*-
'''
File:          db_row.py

Authors:       Kevin Jacobs (jacobs@theopalgroup.com)

Created:       February 12, 2002

Abstract:      This module defines light-weight objects which allow very
               flexible access to a fixed number of positional and named
               attributes via several interfaces.

Compatibility: Python 2.2

Requires:      new-style classes, Python 2.2 super builtin, types module

Revision:      $Id$

Copyright (c) 2002 The OPAL Group.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.

----------------------------------------------------------------------------------

This module defines light-weight objects suitable for many applications,
though the primary goal of the implementer is for storage of database query
results.  The primary design criteria for the data-structure where:

  1) store a sequence of arbitrary Python objects
  2) the number of items stored in each instance should be constant
  3) each instance must be as light-weight as possible, since many thousands
     of them could be created
  4) values must be retrievable by index
     e.g.: d[3]
  5) values must be retrievable by a field name using the Python attribute syntax:
     e.g.: d.field
  6) values must be retrievable by a field name using the Python item syntax:
     e.g.: d['field']
  7) optionally, operations using field names should be case-insensitive
     e.g.: d['FiElD']
  8) should support standard list and dictionary -like interfaces, including
     slicing
  9) should be convertible to a list, tuple or dictionary

These criteria are chosen to simplify access to rows that are returned from
database queries.  Lets say that you run this query:

  cursor.execute('SELECT a,b,c FROM blah;')
  results = cursor.fetchall()

The resulting data-structure is typically a list if row tuples. e.g.:

  results = [ (1,2,3), (3,4,5), (6,7,8) ]

While entirely functional, these data types only allow integer indexed
access.  e.g., to query the b attribute of the second row:

  b = results[1][1]

This requires that all query results are accessed by index, which can be
very tedious and the code using this technique tends to be hard to maintain.
The alternative has always been to return a list of native Python
dictionaries, one for each row.  e.g.:

  results = [ {'a':1,'b':2,'c':3}, {'a':3,'b':4,'c':5},
              {'a':6,'b':7,'c':8} ]

This has the advantage of easier access to attributes by name, e.g.:

  b = results[1]['b']

however, there are several serious disadvantages.

  1) each row requires a heavy-weight dictionary _per instance_.  This can
     damage performance when returning, say, 100,000 rows from a query.

  2) access by index is lost since Python dictionaries are unordered.

  3) attribute-access syntax is somewhat sub-optimal (or at least
     inflexible) since it must use the item-access syntax.

     i.e., x['a'] vs. x.a.

Of course, the second and third problems can be addressed by creating a
UserDict (a Python class that looks and acts like a dictionary), though that
only magnifies the performance problems.

HOWEVER, there are some new features in Python 2.2 that can provide the best
of all possible worlds.  Here is an example:

  # Create a new class type to store the results from our query
  # (we'll make field names case-insensitive just to show off)
  > R=make_row_class(['a','b','c'], insensitive = 1)

  # Create an instance of our new tuple class with values 1,2,3
  > r=R( (1,2,3) )

  # Demonstrate all three accessor types
  > print r['a'], r[1], r.c
  1 2 3

  # Demonstrate case-insensitive operation
  > print r['a'], r['A']
  1 1

  # Return the keys (column names)
  > print r._keys()
  ('a', 'b', 'c')

  # Return the values
  > print r._values()
  (1, 2, 3)

  # Return a list of keys and values
  > print r._items()
  (('a', 1), ('b', 2), ('c', 3))

  # Return a dictionary of the keys and values
  > print r._dict()
  {'a': 1, 'c': 3, 'b': 2}

  # Demonstrate slicing behavior
  > print r[1:3]
  (2, 3)

This solution uses some new Python 2.2 features and ends up allocating only
one dictionary _per row class_, not per row instance.  i.e., the row
instances do not allocate a dictionary at all!  This is accomplished using
the new-style object 'slots' mechanism.

Here is how you could use these objects:

  cursor.execute('SELECT a,b,c FROM blah;')

  # Build the field list from the field names returned by the query
  fields = [ d[0] for d in cursor.description ]

  # Make a class to store the resulting rows
  R = make_row_class(fields, insensitive = 1)

  # Build the rows from the row class and each tuple returned from the cursor
  results = [ R(row) for row in cursor.fetchall() ]

  print results[1].b, results[2].B, results[3]['b'], results[2][1]

Performance:

  Memory and object construction benchmark:

  This benchmark was created to test that the memory footprint savings using
  Python 2.2 slots mechanism.  In these tests, 200,000 row objects were
  created using various representations and the process size
  (code+heap+stack) and program execution time where measured in these
  situations:

         baseline: measures the memory and time required to allocate a list
                   of 200,000 None objects.

            tuple: measures the memory and time required to allocate a list
                   of 200,000 tuple objects, each with 11 integer members.

                   rows = []
                   N=200000
                   for i in range(N):
                     rows.append( (i,i,i,i,i,i,i,i,i,i,i) )

             dict: measures the memory and time required to allocate a list
                   of 200,000 dictionary objects, each with 11 integer members.

                   fields = ('a','b','c','d','e','f','g','h','i','j','k')
                   rows = []
                   N=200000
                   for i in range(N):
                     rows.append( dict(zip(fields,(i,i,i,i,i,i,i,i,i,i,i))) )

      db_row slot: measures the memory and time required to allocate a list
                   of 200,000 db_row objects (using the slots mechanism),
                   each with 11 integer members.

                   fields = ('a','b','c','d','e','f','g','h','i','j','k')
                   rows = []
                   N=200000
                   R=db_row.make_row_class( fields )
                   for i in range(N):
                     rows.append( R((i,i,i,i,i,i,i,i,i,i,i)) )

      db_row dict: as above, except the db_row implementation uses
                   per-instance dictionaries instead of slots.  (i.e.,
                   globally search and replace __slots__ with
                   _slots_ in the rb_row implementation)

         C db_row: The same as the db_row slot except coded as a C extension
                   module.  This implementaion is not yet complete, though
                   object construction and initialization is working.

  RESULTS:

        [Results generated on a quiescent dual processor Intel  III
         733MHz system w/ 256MB RAM running Linux 2.4.1 (uptime 372 days!)]

                                     Time     Approx.
                             SIZE    (sec)  Bytes/row
                         --------   ------  ---------
            baseline:     4,744KB     0.56        -
               tuple:    18,948KB     2.49       73
                dict:       117MB    13.50      589
         db_row slot:    18,960KB    17.23       73
         db_row dict:       117MB    24.09      589
            C db_row:    18,924KB     4.85       73

  Real world benchmark:

  This (native-Python) implementation was tested in a very large business
  report generation engine.  An automated test suite was run which produced
  84 complex reports and generating ~11MB of HTML/XML output over a local
  HTTPS connection.  The report server performed many large and small
  queries for security access checks, user interface generation, as well as
  for the reports themselves.

  Here are the results of running the same test suite 3 different ways:

            baseline: These are the results that are obtained before any
                      modifications where made to add db_row support.

        basic db_row: All queries were modified to produce case-sensitive
                      db_row objects, though none of the reports were
                      modified to use the new access methods.  Since access
                      by index is now the most expensive way to access the
                      data values, and many small queries are run that do
                      not benefit from db_rows at all, this scenario
                      demonstrates the near worst-case behavior.

       insens db_row: This is the same as the basic db_row test, except all
                      db_row objects are now case-insensitive.  Here, the
                      functional call overhead for each attribute access is
                      doubled.

         dict db_row: This implementation uses an instance dictionary instead
                      of the slots mechanism to implement field access.

  insens dict db_row: This is the same as the dict db_row test, except all
                      db_row objects are now case-sensitive.
                      doubled.

            C db_row: This is the same as basic db_row except that it is
                      implemented as a C extension module.

  RESULTS:
        [Results generated on a quiescent dual processor Intel Pentium III
         733MHz system w/ 256MB RAM running Linux 2.4.1 (uptime 372 days!)]

                         Output     Total       Average
                           Size      Time    Throughput
                        -------     -----    ----------
             baseline:  11.00MB     3.66m     53.05KB/s
         basic db_row:  11.00MB     4.12m     47.10KB/s
        insens db_row:  11.00MB     4.75m     40.84KB/s
          dict db_row:  11.00MB     4.14m     46.87KB/s
   insens dict db_row:  11.00MB     4.77m     40.62KB/s
             C db_row:  11.00MB     3.67m     52.86KB/s

  Conclusions:

    For many applications, db_row objects incur an acceptable performance
    penalty relative to other access methods.  The very minimal difference
    in running time between the slot and dictionary based db_row objects
    indicates that the inherent performance difference due to the different
    data-structures is negligible compared to other sources of runtime
    overhead.  We can also infer that much of the slow-down is due to the
    penalty imposed by Python when replacing native object containers with
    Python coded containers.  The implementation of rb_row as a C extension
    module reduces the performance gap between tuples and db_rows to the
    point where it is negligible.


Open implementation issues:

  o This implementation will likely break when Python 2.3 comes out, since
    super will become a keyword, and possibly due to other syntactic changes.
    The code will be trivial to fix, so this is not a big concern.

  o Values are currently mutable.  This opens the door to several problems:

     1) ._items(), ._values() and ._keys() do not skip slots that do not
        have values assigned.  This is so that the field indices will always
        be consistent.  Missing, unassigned, or deleted values are
        represented with 'None' objects.  e.g.:

          > R=make_row_class(['a','b','c'], insensitive = 1)
          > r=R([1,2,3])
          > print r._items()
          (('a', 1), ('b', 2), ('c', 3))
          > del r[:]
          > print r._items()
          (('a', None), ('b', None), ('c', None))

     2) Row equality and hashing are open issues.  I do not intend to
        compare rows or store them in dictionaries, so this does not bother
        me much.  Others may want to, so maybe it is desirable to have both
        mutable and immutable instance types.

   o The current code returns its _keys, _values, _items and slices as tuples.
     This is done to better conform to legacy code which assumes that rows
     are always tuples.  This seems sensible enough, though I welcome other
     opinions on the subject.

   o Concatenation of db_rows with lists, tuples and other db_rows is
     implemented, though the result is a list, tuple, or tuple,
     respectively.  The behavior of the last case may not be optimal for all
     users, though I am hesitant to create dynamic row classes "on the fly".

   o More doc-strings are needed, including dynamic row class doc-strings

   o Add integrated unit-tests (a la doctest, most likely)

   o Maybe some better example code
'''

import types

class abstract_row(object):
  '''abstract_row:

     A light-weight object which allows very flexible access to a fixed
     number of positional and named attributes via several interfaces.

     Use make_row_class(...) to construct row types.
  '''

  __slots__ = ()

  def __init__(self, values=None):
    if values:
      self[:] = values

  def __len__(self):
    '''x.__len__() <==> len(x)'''
    return len(self.__slots__)

  def _keys(self):
    '''r._keys() -> list of r's fields'''
    return tuple(self.__slots__)

  def _values(self):
    '''r._values() -> tuple of r's values'''
    return tuple([ getattr(self,name,None) for name in self.__slots__ ])

  def _items(self):
    '''r._items() -> tuple of r's (field, value) pairs, as 2-tuples'''
    return tuple([ (name,getattr(self,name,None)) for name in self.__slots__ ])

  def _has_key(self, key):
    '''r._has_key(k) -> 1 if r has a field k, else 0'''
    return key in self.__slots__ and hasattr(self, key)

  def __contains__(self, value):
    '''r.__contains__(y) <==> y in r'''
    return value in self._values()

  def _dict(self):
    '''r._dict() -> dictionary mapping r's fields to its values'''
    return dict(self._items())

  def __getitem__(self, key):
    '''x.__getitem__(i) <==> x[i], where i is an integer index or a case-sensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    return getattr(self, key)

  def __setitem__(self, key, value):
    '''x.__setitem__(i, y) <==> x[i]=y, where i is an integer index or a case-sensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    setattr(self, key, value)

  def __delitem__(self, key):
    '''x.__delitem__(i) <==> del x[i], where i is an integer index or a case-sensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    return delattr(self, key)

  def __setslice__(self, i, j, values):
    '''x.__setslice__(i, j, y) <==> x[i:j]=y'''
    slots=self.__slots__[i:j]
    if len(slots) != len(values):
      raise IndexError, "list index out of range"
    for name,value in zip(slots, values):
      setattr(self, name, value)

  def __getslice__(self, i, j):
    '''x.__getslice__(i, j) <==> x[i:j]'''
    return tuple([ getattr(self,name,None) for name in self.__slots__[i:j] ])

  def __delslice__(self, i, j):
    '''x.__delslice__(i, j) <==> del x[i:j]'''
    for name in self.__slots__[i:j]:
      delattr(self, name)

  def __add__(self, x):
    '''r.__add__(y) <==> T(r)+y, where T is tuple() unless y is a list, then T is list()'''
    if type(x) == types.TupleType:
      return tuple(self._values()) + x
    elif type(x) == types.ListType:
      return list(self._values()) + x
    elif isinstance(x, abstract_row):
      return self._values() + x._values()
    else:
      raise TypeError, 'Invalid concatenation type'

  def __radd__(self, x):
    '''r.__radd__(y) <==> y+T(r), where T is tuple() unless y is a list, then T is list()'''
    if type(x) == types.TupleType:
      return x + tuple(self._values())
    elif type(x) == types.ListType:
      return x + list(self._values())
    elif isinstance(x, abstract_row):
      return x._values() + self._values()
    else:
      raise TypeError, 'Invalid concatenation type'


class insensitive_abstract_row(abstract_row):
  '''An row object that supports case-insensitive string keys'''

  __slots__ = ()

  def _has_key(self, key):
    '''r._has_key(k) -> 1 if r has a field k, else 0, insensitive to the case of k'''
    key = key.lower()
    return super(insensitive_abstract_row, self).has_key(key)

  def __getitem__(self, key):
    '''x.__getitem__(i) <==> x[i], where i is an integer index or a case-insensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    else:
      key = key.lower()
    return super(insensitive_abstract_row, self).__getattribute__(key)

  def __setitem__(self, key, value):
    '''x.__setitem__(i, y) <==> x[i]=y, where i is an integer index or a case-insensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    else:
      key = key.lower()
    super(insensitive_abstract_row, self).__setattr__(key, value)

  def __delitem__(self, key):
    '''x.__delitem__(i) <==> del x[i], where i is an integer index or a case-insensitive string'''
    if type(key) == type(1):
      key = self.__slots__[key]
    else:
      key = key.lower()
    super(insensitive_abstract_row, self).__delattr__(key)

  def __getattr__(self, key):
    '''x.__getattr__(a) <==> x.a, insensitive to the case of a'''
    key = key.lower()
    return super(insensitive_abstract_row, self).__getattribute__(key)

  def __setattr__(self, key, value):
    '''x.__setattr__(a,y) <==> x.a=y, insensitive to the case of a'''
    key = key.lower()
    super(insensitive_abstract_row, self).__setattr__(key, value)

  def __delattr__(self, key):
    '''x.__delattr__(a) <==> del x.a, insensitive to the case of a'''
    key = key.lower()
    super(insensitive_abstract_row, self).__delattr__(key)


def make_row_class(fields, insensitive = 0):
  '''Helper function that creates row classes'''

  field_dict = {}

  for f in fields:
    if type(f) != types.StringType:
      raise TypeError, 'Field names must be ASCII strings'
    if not f:
      raise ValueError, 'Field names cannot be empty'

    if insensitive:
      f = f.lower()

    if field_dict.has_key(f):
      raise ValueError, 'Field names must be unique'
    field_dict[f] = 1

  if insensitive:
    base_class = insensitive_abstract_row
    fields = [ f.lower() for f in fields ]
  else:
    base_class = abstract_row

  return type('row', (base_class,), { '__slots__' : tuple(fields) })


def test():
  D=make_row_class(['a','b','c'])
  print dir(D)
  d=D( (1,2,3) )

  assert d['a']==d[0]==d.a==1
  assert d['b']==d[1]==d.b==2
  assert d['c']==d[2]==d.c==3

  print d['a'],d[0],d.a
  print d._keys()
  print d._values()
  print d._items()
  print d._dict()
  print d[-1]
  print d[1:3]
  del d[0]
  del d.b
  del d['c']
  print d._items()
  print d._dict()

def test_insensitive():
  D=make_row_class(['a','b','c'], insensitive = 1)

  d=D( (1,2,3) )

  assert d['a']==d['A']==d[0]==d.A==d.a==1
  assert d['b']==d['B']==d[1]==d.B==d.b==2
  assert d['c']==d['C']==d[2]==d.C==d.c==3

  d.A    += 1
  d['B'] += 1
  d[2]   += 1

  assert d['a']==d['A']==d[0]==d.A==d.a==2
  assert d['b']==d['B']==d[1]==d.B==d.b==3
  assert d['c']==d['C']==d[2]==d.C==d.c==4

  del d.A
  del d['B']
  del d[2]

  dd=d._dict()

  assert dd['a'] == dd['b'] == dd['c'] == None

def test_concat():
  D=make_row_class(['a','b','c'], insensitive = 1)
  d=D( (1,2,3) )

  print d+(4,5,6)
  print [4,5,6]+d
  print d+[4,5,6]
  print (4,5,6)+d
  print d+d

if __name__ == '__main__':
  test()
  test_insensitive()
  test_concat()

# arch-tag: 8aacc7bc-31a2-4545-ad10-a7de82bb95ea
