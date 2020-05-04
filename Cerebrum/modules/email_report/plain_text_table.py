# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
"""Functionality for generating plain text tables from tables represented by
lists
"""
from __future__ import unicode_literals

from six import itertools


def get_cell_content(text, cell_width):
    return text + (cell_width - len(text)) * ' '


def get_cell_contents(texts, cell_widths):
    return [get_cell_content(t, l) for t, l in zip(texts, cell_widths)]


def assemble_line(divider, cell_contents):
    return divider + divider.join(cell_contents) + divider


def get_padded_contents(content, cell_height):
    if isinstance(content, unicode):
        content = [content]
    content.extend(['' for x in range(len(content), cell_height)])
    return content


def assemble_row(divider, row, widths):
    row_height = get_row_height(row)
    content = [get_padded_contents(content, row_height) for content in row]
    lines = [assemble_line(divider, get_cell_contents(c, widths)) for c in
             transpose(content)]
    return '\n'.join(lines)


def get_column_width(argument):
    """Get the widest width of the columns given

    :type argument: list or unicode
    """
    if isinstance(argument, unicode):
        return len(argument)
    if isinstance(argument, list):
        return max(*map(get_column_width, argument))
    raise TypeError('Argument %s type: %s', argument, type(argument))


def get_column_widths(columns):
    """Get the width of each column

    :type columns: list
    Example:

    >>> get_column_widths(['c1,r1', 'c1,r2', ['c1,r3,l1', 'c1,r3,l2']])
    8
    """
    return map(get_column_width, columns)


def get_cell_height(cell_content):
    if isinstance(cell_content, list):
        return len(cell_content)
    elif isinstance(cell_content, unicode):
        return 1
    raise TypeError('Cell content type: %s', type(cell_content))


def get_row_height(row):
    return max(*map(get_cell_height, row))


def transpose(table):
    """Transpose a table represented by a list of lists

    Example:

    >>> transpose([[1, 2], [3, 4]])
    [[1, 3], [2, 4]]
    """
    return list(itertools.imap(list, zip(*table)))


def get_table(table_rows):
    """Assembles and returns a plain text table

     Given the rows which make up a table, a correctly formatted table is
     returned.

     Example:

     >>> table = get_table([['This', 'is'], ['a', 'table']])
     >>> print(table)
     +----+-----+
     |This|is   |
     +----+-----+
     |a   |table|
     +----+-----+
    """
    columns = transpose(table_rows)
    column_widths = get_column_widths(columns)
    separators = map(lambda length: length * '-', column_widths)
    divider_line = assemble_line('+', separators)

    output_rows = '\n' + divider_line + '\n'
    for row in table_rows:
        row_content_lines = assemble_row('|', row, column_widths)
        output_rows += row_content_lines + '\n' + divider_line + '\n'
    return output_rows
