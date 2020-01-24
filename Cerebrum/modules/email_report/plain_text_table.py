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


def get_longest_item_length(lst):
    return max(*map(len, lst))


def get_cell_widths(columns):
    return map(get_longest_item_length, columns)


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

     >>> table = assemble_plaintext_table([['This', 'is'], ['a', 'table']])
     >>> print(table)
     +----+-----+
     |This|is   |
     +----+-----+
     |a   |table|
     +----+-----+
    """
    columns = transpose(table_rows)
    cell_widths = get_cell_widths(columns)
    separators = map(lambda length: length * '-', cell_widths)
    divider_line = assemble_line('+', separators)

    output_rows = '\n' + divider_line + '\n'
    for row in table_rows:
        row_content_line = assemble_line(
            '|',
            get_cell_contents(row, cell_widths)
        )
        output_rows += row_content_line + '\n' + divider_line + '\n'
    return output_rows
