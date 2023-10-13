# -*- coding: utf-8 -*-
#
# Copyright 2020-2023 University of Oslo, Norway
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
This module contains various tools for fuzzy string matching.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


def restricted_damerau_levenshtein(first, second):
    """
    Calculate the Damerau-Levenshtein distance between strings.

    This function calculates the edit distance between `first` and `second`
    using the Damerau-Levenshtein optimal string alignment algorithm.

    :returns int: The edit distance
    """
    # input strings are 1-indexed:
    first = " " + first
    second = " " + second

    distance_matrix = [
        [0 for i in range(len(first))]
        for b in range(len(second))
    ]

    for i in range(len(second)):
        distance_matrix[i][0] = i

    for j in range(len(first)):
        distance_matrix[0][j] = j

    for i in range(1, len(distance_matrix)):
        for j in range(1, len(distance_matrix[0])):
            possible_choices = [
                # delete:
                distance_matrix[i-1][j] + 1,
                # insert:
                distance_matrix[i][j-1] + 1,
            ]
            if first[j] == second[i]:
                # equal:
                possible_choices.append(distance_matrix[i-1][j-1])
            elif first[j] == second[i-1] and first[j-1] == second[i]:
                # transpose:
                possible_choices.append(distance_matrix[i-2][j-2] + 1)
            else:
                # substitute:
                possible_choices.append(distance_matrix[i-1][j-1] + 1)
            distance_matrix[i][j] = min(possible_choices)

    return distance_matrix[-1][-1]


def longest_common_subsequence(first, second):
    """
    Determine the longest common subsequence (LCS) of two strings.

    :returns str: the longest common substring
    """
    if not first or not second:
        return ""
    lengths = [
        [0 for j in range(len(second)+1)]
        for i in range(len(first)+1)
    ]
    # row 0 and column 0 are initialized to 0 already
    for i, x in enumerate(first):
        for j, y in enumerate(second):
            if x == y:
                lengths[i+1][j+1] = lengths[i][j] + 1
            else:
                lengths[i+1][j+1] = max(lengths[i+1][j], lengths[i][j+1])

    # read the substring out from the matrix
    result = ""
    x, y = len(first), len(second)
    while x != 0 and y != 0:
        if lengths[x][y] == lengths[x-1][y]:
            x -= 1
        elif lengths[x][y] == lengths[x][y-1]:
            y -= 1
        else:
            assert first[x-1] == second[y-1]
            result = first[x-1] + result
            x -= 1
            y -= 1
    return result


def words_diff(first, second, threshold=0):
    """
    Calculate if fuzzy words from one string occur in another.

    This function is good for matching *full names*, and other similar strings,
    as it checks if all words from one string occurs in another, but allowing
    for typos or accented characters.

    >>> words_diff("foo baz", "foo bar baz")
    0

    >>> words_diff("foo bar", "foo bár baz")
    1

    :param str first: A string to compare.
    :param str second: Another string to compare.
    :param int threshold:
        Stop matching if an edit distance threshold is reached.

        This allows us to abort early if there are too many differences.  The
        default is 0, which won't apply a threshold.  A threshold of 2 is good
        for e.g. fullname matching.

    :returns int:
        The edit distance of all words in shortest string (by wordcount).
    """
    total_difference = 0
    fewer_words = first.split()
    words = second.split()
    if len(fewer_words) > len(words):
        fewer_words, words = words, fewer_words

    for base_word in fewer_words:
        best_match = (0, 5)
        for wordnum, word in enumerate(words, 1):
            diff = restricted_damerau_levenshtein(base_word, word)
            if diff < best_match[1]:
                best_match = (wordnum, diff)

        total_difference += best_match[1]
        words = words[best_match[0]:]
        if threshold > 0 and total_difference > threshold:
            break
    return total_difference
