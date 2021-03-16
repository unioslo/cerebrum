""" Tests for Cerebrum.utils.reprutils. """
import pytest

import Cerebrum.utils.reprutils


@pytest.fixture
def field_obj():

    class Fields(Cerebrum.utils.reprutils.ReprFieldMixin):

        repr_id = False
        repr_module = False
        repr_fields = ('foo', 'bar', 'baz', 'missing')

        def __init__(self, foo, bar, baz):
            self.foo = foo
            self.bar = bar
            self.baz = baz

    return Fields('text', None, dict(x=1))


def test_fields(field_obj):
    assert repr(field_obj) == "<Fields foo='text' bar=None baz={'x': 1}>"


@pytest.fixture
def eval_obj():

    class Eval(Cerebrum.utils.reprutils.ReprEvalMixin):

        repr_id = False
        repr_module = False
        repr_args = ('foo', 'bar')
        repr_kwargs = ('baz',)

        def __init__(self, foo, bar, baz=None):
            self.foo = foo
            self.bar = bar
            self.baz = baz

    return Eval('text', None, 3)


def test_eval(eval_obj):
    assert repr(eval_obj) == "Eval('text', None, baz=3)"
