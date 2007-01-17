# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

class TableView:
    """Selects columns and sorts by several columns from a given dataset."""
    def __init__(self, columns, headers=None):
        """Defines the initial set of columns and the associated headers.
           See add()."""
        self.columns = columns
        self.headers = headers or columns
        self._headerMap = dict(zip(self.columns, self.headers))
        # sort is a list of column names, prepended with + and - to
        # denote ascending or descending sorting. + or - IS required.
        # by default, sorted left to right ascending
        self.sort = ["+" + field for field in self.columns]
        self._width = len(self.columns)
        self._rows = []

    def column_order(self, columnname):
        """Returns the current column order for the given column"""
        for column in self.sort:
            if not columnname == column[1:]:
                continue
            way = column[0]
            if way == "+":
                return 1
            elif way == "-":
                return -1
            else:        
                raise "Invalid sort order %s - should start with + or -" % column
        return 0          
        
    def add(self, *data, **fields):
        """Adds a data row with field=value. 
        If positional arguments are given, their value are 
        associated according to fields in self.columns
        
        Example:
        
        >>> t.add(name="stain", fullname="Stian Soiland", tel="92019694")
        >>> t.columns = {"name": "First Name", "tel": "Telephone"}

        t.sorted() will then return a table contaning data from fields 
        'name' and 'tel' from each row.
        """
        myfields = dict(zip(self.columns, data))
        myfields.update(fields)
        self._rows.append(myfields)
    
    def _sorter(self, a, b):
        """Sorts according to rules in self.sort. This is called for each
           elements that needs to be compared."""
        for column in self.sort:
            column = column[1:]
            diff = cmp(a.get(column), b.get(column))
            if diff:
                return self.column_order(column) * diff
        return diff        

    def header(self, column):
        """Returns the columns header name.  Or an empty string if it's
           unknown."""
        return self._headerMap.get(column, '')
        
    def sorted(self, includeData=False):
        """Returns a two dimensional sorted list. 
           Rows are taken from self._rows with the columns selected from
           self.columns, and sorted by the rules in self.sort.

           If includeData is true, each row returned is a tuple of
           (columns, rowdata) - where columns are the selected columns
           and rowdata the original row data as a dict.
           """
        self._rows.sort(self._sorter)
        result = []
        for row in self._rows:
            columns = [row.get(column) for column in self.columns]
            if includeData:
                # include row data dict 
                result.append( (columns, row) )
            else:    
                result.append(row)
        return result
