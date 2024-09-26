# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.tasks.formatting` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import textwrap

import pytest

from Cerebrum.modules.tasks import formatting


@pytest.mark.parametrize(
    "value, expect",
    [
        (None, ""),
        (3, "3"),
        (datetime.datetime(1998, 6, 28, 23, 30, 11), "1998-06-28 23:30:11"),
        ({1: 3}, "{1: 3}"),
    ],
)
def test_to_text(value, expect):
    assert formatting.to_text(value) == expect


@pytest.mark.parametrize(
    "value, maxlen, expect",
    [
        ("123", 3, "123"),
        ("1234", 3, "..."),
        ("1234567890", 9, "123456..."),
    ],
)
def test_limit_str(value, maxlen, expect):
    assert formatting.limit_str(value, maxlen) == expect


def test_format_task():
    formatter = formatting.TaskFormatter(('queue', 'key', 'sub', 'attempts'))
    tasks = [
        {
            'queue': "example-queue",
            'sub': None,
            'key': "123",
            'attempts': 0,
        },
        {
            'queue': "example-queue",
            'sub': "too-long-sub-queue-name",
            'key': "xyz",
            'attempts': 23,
        },
    ]

    expected = textwrap.dedent(
        """
        queue            key         sub              attempts
        ---------------  ----------  ---------------  --------
        example-queue    123                          0       
        example-queue    xyz         too-long-sub...  23      
        """  # noqa: W291
    ).lstrip().rstrip("\n")

    result = "\n".join(formatter(tasks, header=True))
    # for debuging
    print(result)
    print(expected)
    assert result == expected
