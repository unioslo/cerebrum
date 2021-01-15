import pytest
import Cerebrum.meta


def test_mangle_name():
    assert Cerebrum.meta._mangle_name('Foo',   '__bar') == '_Foo__bar'
    assert Cerebrum.meta._mangle_name('_Foo',  '__bar') == '_Foo__bar'
    assert Cerebrum.meta._mangle_name('__Foo', '__bar') == '_Foo__bar'


def test_mangle_name_ignore():
    assert Cerebrum.meta._mangle_name('_',   '__bar') == '__bar'
    assert Cerebrum.meta._mangle_name('Foo',   '_bar') == '_bar'
    assert Cerebrum.meta._mangle_name('Foo',   '__bar__') == '__bar__'


class InitMixin(object):
    """ mixin to set attrs from kwargs on init. """

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class SuperBase(InitMixin, Cerebrum.meta.AutoSuperMixin):
    overload = 0


class SuperFoo(SuperBase):
    overload = 1


class SuperBar(SuperFoo):
    overload = 2


def test_has_super_attr():
    obj = SuperBar()

    assert all(hasattr(obj, attr) for attr in ('_SuperBase__super',
                                               '_SuperFoo__super',
                                               '_SuperBar__super'))


def test_super_attr_value():
    obj = SuperBar()
    assert getattr(obj, '_SuperFoo__super').overload == SuperBase.overload
    assert getattr(obj, '_SuperBar__super').overload == SuperFoo.overload


class UpdateBase(InitMixin, Cerebrum.meta.MarkUpdateMixin):
    __read_attr__ = ('foo_1',)
    __write_attr__ = ('bar_1',)


class UpdateFoo(UpdateBase):
    __read_attr__ = ('foo_2', 'foo_3')
    __write_attr__ = ('bar_2', 'bar_3')
    dontclear = ('foo_3',)


class UpdateBar(UpdateFoo):
    __read_attr__ = ('foo_4', 'foo_5')
    __write_attr__ = ('bar_4', 'bar_5')
    __slots__ = ('other_1',)


@pytest.fixture
def update_bar_obj():
    return UpdateBar(
        # __read_attr__
        foo_1=1, foo_2=2, foo_3=3, foo_4=4, foo_5=5,
        # __write_attr__
        bar_1='a', bar_2='b', bar_3='c', bar_4='d', bar_5='e',
        # other attrs
        other_1='something')


def test_meta_update_init(update_bar_obj):
    # the fixture actually inits our object
    # note: read-attrs can only be set if previously unset
    assert update_bar_obj.foo_1 == 1
    assert update_bar_obj.foo_3 == 3
    assert update_bar_obj.foo_5 == 5
    assert update_bar_obj.bar_1 == 'a'
    assert update_bar_obj.bar_3 == 'c'
    assert update_bar_obj.bar_5 == 'e'
    assert update_bar_obj.other_1 == 'something'


def test_mark_update_slots():
    # __slots__ are updated with all read/write attrs
    slots = set(UpdateBar.__slots__)
    require = (set(UpdateBar.__read_attr__)
               | set(UpdateBar.__write_attr__)
               | set(('other_1',)))
    assert slots.intersection(require) == require


def test_mark_update_noslots():
    # UpdateFoo should not have __slots__
    with pytest.raises(AttributeError):
        UpdateFoo.__slots__


def test_meta_update_updated(update_bar_obj):
    # any write-attribute should be added to __updated when set
    # our fixture sets all write-attrs
    assert (set(update_bar_obj._UpdateBase__updated)
            == set(UpdateBase.__write_attr__))
    assert (set(update_bar_obj._UpdateFoo__updated)
            == set(UpdateFoo.__write_attr__))
    assert (set(update_bar_obj._UpdateBar__updated)
            == set(UpdateBar.__write_attr__))


def test_meta_update_read_attr(update_bar_obj):
    # we should not be able to re-set a read-only attribute
    with pytest.raises(AttributeError):
        update_bar_obj.foo_1 = 'something else'


def test_meta_update_reset_read_attr(update_bar_obj):
    del update_bar_obj.foo_1
    update_bar_obj.foo_1 = 'something else'
    assert update_bar_obj.foo_1 == 'something else'


def test_meta_update_clear(update_bar_obj):
    update_bar_obj.clear()

    # other_1 is not handled by MetaUpdate
    assert update_bar_obj.other_1 == 'something'

    # foo_3 is exempt from clear()
    assert update_bar_obj.foo_3 == 3

    # read attributes are *deleted* - so that they can be re-set
    read = {attr: hasattr(update_bar_obj, attr)
            for attr in ('foo_1', 'foo_2', 'foo_4', 'foo_5',)}

    # write attributes are set to None
    write = {attr: getattr(update_bar_obj, attr, 'is set')
             for attr in ('bar_1', 'bar_2', 'bar_3', 'bar_4', 'bar_5')}

    assert not any(read.values())
    assert all(v is None for v in write.values())


def test_is_updated(update_bar_obj):
    # after init -- no classes should require update
    assert True


def test_xerox(update_bar_obj):

    # xerox only copies supported read/write attrs
    foo = UpdateFoo()
    foo.__xerox__(update_bar_obj)
    assert foo.foo_1 == 1
    assert foo.foo_3 == 3
    assert foo.bar_3 == 'c'
    assert not hasattr(foo, 'foo_4')

    bar = UpdateBar()
    bar.__xerox__(foo)
    assert bar.foo_1 == 1
    assert bar.foo_3 == 3
    assert bar.bar_3 == 'c'
    assert not hasattr(bar, 'foo_4')
