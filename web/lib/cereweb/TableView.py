# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import forgetHTML as html
import sci_exp

class TableView:
    """Selects columns and sorts by several columns from a given dataset."""
    def __init__(self, *columns):
        """Defines the initial set of columns to be selected. 
           Other columns might be defined by changing self.columns. Columns is
           a list of strings. See add()."""
        self.columns = columns
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
        >>> t.columns = ("name", "tel")

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
        
    def sorted(self, includeData=False):
        """Returns a two dimensional sorted list. 
           Rows are taken from self._rows with the columns selected from
           self.columns, and sorted by the rules in self.sort.

           If includeData is true, each row returned is a tuple of (columns,
           rowdata) - where columns are the selected columns and rowdata the
           original row data as a dict.
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

    def html(self, **titles):
        """Returns a HTML version of the sorted table. Keyword arguments
           defines headers for the columns, only titles which names are
           in self.columns will be output."""
        table = html.SimpleTable(header="row")
        headers = []
        for column in self.columns:
            # header defined as keyword argument
            header = titles.get(column)
            if header is None:
                # select header from self.columns
                header = column.capitalize()
            headers.append(header)
        table.add(*headers)       
        for row in self.sorted():
            row = map(row.get, self.columns)
            # Prepare values to be HTML-able
            row = map(_prepareForHTML, row)
            table.add(*row)
        return table    

def _prepareForHTML(value):
    """Returns a forgetHTML-compatible value"""
    if isinstance(value, html.Element):
        return value
    if type(value) in (int, long):
        return Value(value, decimals=0)
    if type(value) == float:
        return Value(value)
    if value is None:
        return ""        
    return str(value)

class Value(html.Text):
    """A special html-text containing a number.
       The item is sorted according to the numeric value, but 
       printed with the given decimal counts and the optional unit. 
       """
    def __init__(self, value, unit="", decimals=2, 
                 sciunit=False, **kwargs):
        try:
            _ = value + 0
            assert _ == value
        except:
            raise "Value %r not a number" % value
        self.value = value
        self.decimals = decimals
        self.unit = unit
        self.sciunit = sciunit
        html.Text.__init__(self, self._display(), **kwargs)
    def _display(self):
        format = "%0." + str(self.decimals) + "f"
        if self.sciunit:
            (value, unit) = sci_exp.sci(self.value)
            unit = unit + self.unit
        else:
            unit = self.unit
            value = self.value
        formatted = format % value
        return formatted + unit
    def __cmp__(self, other):
        if isinstance(other, html.TableCell):
            return cmp(self.value, other.value)
        else:
            return cmp(self.value, other)

# arch-tag: 01e42737-62f0-4f30-9dd9-03ce5c9962bb
