import pytest

from Cerebrum.utils.date import to_seconds


@pytest.mark.parametrize(
    "result,args",
    [
        (8, {'seconds': 8}),
        (129, {'minutes': 2, 'seconds': 9}),
        (2017920, {'days': 23, 'minutes': 512}),
        (1242000, {'weeks': 2, 'hours': 9}),
    ]
)
def test_to_seconds(args, result):
    assert to_seconds(**args) == result
