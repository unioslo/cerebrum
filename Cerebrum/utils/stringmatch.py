# -*- coding: utf-8 -*-
#
# Copyright 2017 University of Oslo, Norway
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
This module contains tools for string matching
"""


def restricted_damarau_levenshtein(first, second):
    """
    Calculate the edit distance between two string using restricted damarau
    levenshtein. Allowing deletion, insertion, substitution and transposition
    of characters.
    """
    first = ' ' + first
    second = ' ' + second
    dist_matrix = [[0 for i in range(len(first))] for b in range(len(second))]

    for i in range(len(second)):
        dist_matrix[i][0] = i

    for j in range(len(first)):
        dist_matrix[0][j] = j

    for i in range(1, len(dist_matrix)):
        for j in range(1, len(dist_matrix[0])):
            possible_choices = [dist_matrix[i-1][j] + 1,           #del
                                dist_matrix[i][j-1] + 1]           #ins
            if first[j] == second[i]:
                possible_choices.append(dist_matrix[i-1][j-1])     #equal
            elif first[j] == second[i-1] and first[j-1] == second[i]:
                possible_choices.append(dist_matrix[i-2][j-2] + 1) #trans
            else:
                possible_choices.append(dist_matrix[i-1][j-1] + 1) #sub
            dist_matrix[i][j] = min(possible_choices)

    return dist_matrix[-1][-1]


def name_diff(full_name1, full_name2, threshold=2):
    """
    Calculate the difference between two names, allowing one name to be
    longer than the other by only checking whether all names in the shortest
    seem to be included in the longest.
    e.g. name_diff('foo bar', 'foo test bar') = 0

    If the total difference is larger than a given threshold after any part of
    the name, the function will return early. Useful when only close matches
    are interesting.
    """
    total_difference = 0
    names1 = full_name1.split()
    names2 = full_name2.split()
    if len(names1) > len(names2):
        names1, names2 = names2, names1

    for n1 in names1:
        best_match = (0, 5)
        for i, n2 in enumerate(names2, 1):
            diff = restricted_damarau_levenshtein(n1, n2)
            if diff < best_match[1]:
                best_match = (i, diff)

        total_difference += best_match[1]
        names2 = names2[best_match[0]:]
        if total_difference > threshold:
            break
    return total_difference
