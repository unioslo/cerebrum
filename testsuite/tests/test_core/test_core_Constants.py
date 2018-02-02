#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic tests for Cerebrum/Constants.py.

NOTE: Most constants that we write to the db in tests and fixtures have random
hex string values. This is an attempt to avoid any collision with constants in
the db that gets inserted by `makedb`.


TODOs
-----
There's still some stuff to write tests for in the Constants module:

* _CerebrumCode.sql getter and setter
* SynchronizedDatabase and locking
* Errors
* ConstanstBase.initialize with delete


Known issues
------------
Constants cache
    Each _CerebrumCode subclass stores all known constants in a cache. This
    happens on instantiation, so if you do `_EntityTypeCode('foo')`, then that
    object gets cached in the class _EntityTypeCode, under the key 'foo'.

    In the unit tests here, we have to patch each _CerebrumCode class to clear
    this cache between tests (see `constant_module`).

ConstantsBase db-cursor
    Regardless of what we pass to ConstantsBase(), we will get a new
    SynchronizedDatabase db-cursor.

Functionality
    We really need to clean up and add some utility functions in Constants and
    CerebrumCode.

"""
from __future__ import unicode_literals
import pytest
from Cerebrum.Errors import NotFoundError


# @pytest.fixtures(params=['_ChangeTypeCode'])
# def ChangeType(request, constant_module):
#     return getattr(constant_module, request.param)


# @pytest.fixtures(params=['_QuarantineCode'])
# def QuarantineCode(request, constant_module):
#     return getattr(constant_module, request.param)


# @pytest.fixtures(params=['_PersonAffStatusCode'])
# def AffStatusCode(request, constant_module):
#     return getattr(constant_module, request.param)


# @pytest.fixtures(params=['_CountryCode'])
# def CountryCode(request, constant_module):
#     return getattr(constant_module, request.param)


@pytest.fixture
def Language(constant_module):
    return getattr(constant_module, '_LanguageCode')


@pytest.fixture
def EntityType(constant_module):
    return getattr(constant_module, '_EntityTypeCode')


@pytest.fixture(params=['_EntityTypeCode', '_ContactInfoCode', '_GenderCode',
                        '_PersonAffiliationCode', ])
def CerebrumCode(request, constant_module):
    u""" _CerebrumCode types that doesn't alter behaviour. """
    return getattr(constant_module, request.param)


@pytest.fixture(params=['_EntityExternalIdCode', '_SpreadCode'])
def TypedCerebrumCode(request, constant_module):
    return getattr(constant_module, request.param)


@pytest.fixture
def languages(Language):
    u""" A tuple with three language constants. """
    langs = tuple(
        (Language('208e1453fea1f5e3', description='europanto'),
         Language('e778fd19f744eab3', description='e-prime'),
         Language('d8be0fb3ac08dfaf', description='klingon')))
    for lang in langs:
        lang.insert()
    return langs


@pytest.fixture
def simple_const(CerebrumCode):
    code = CerebrumCode('simple', description='simple')
    print 'simple db', code.sql, code.sql._cursor
    code.insert()
    return code


@pytest.fixture
def typed_const(EntityType, TypedCerebrumCode):
    etype = EntityType('ce55b876a633486a', description='thing')
    etype.insert()
    code = TypedCerebrumCode('d35bdac19ba560f5',
                             entity_type=etype,
                             description='type conserning thing')
    code.insert()
    return code


@pytest.fixture
def constants(constant_module, Language, EntityType):
    base = getattr(constant_module, 'ConstantsBase')

    class ConstantContainer(base):
        entity_foo = EntityType('4620a2402a8db1c3', description='foo')
        entity_bar = EntityType('da0e1bf8bd56dcf7', description='bar')

        lang_foo = Language('984fe8eae7bdec0a', description='foo')
        lang_bar = Language('7c7afea1fb3b8eff', description='bar')

        # foo = Foo('a18c7d98b3f34ebe', description='foo')
        # bar = Foo('eae87dd4f8fbed46', description='bar')
    return ConstantContainer()


def test_init_simple_cerebrum_code(CerebrumCode):
    strval = 'ddf6ebf5ea3bbb3e'
    code = CerebrumCode(strval)
    print repr(code)
    assert str(code) == strval


def test_insert(CerebrumCode):
    code = CerebrumCode('cdd0de3e59cd93eb', description='insert test')
    code.insert()
    print repr(code)
    int(code)
    assert True  # Found the constant with int()


def test_delete(simple_const, CerebrumCode):
    intval = int(simple_const)
    simple_const.delete()
    with pytest.raises(NotFoundError):
        CerebrumCode(intval)


def test_update(simple_const, CerebrumCode):
    assert simple_const.description == 'simple'
    simple_const._desc = 'something else'
    simple_const.update()
    # Force clear cache
    CerebrumCode._cache = dict()
    simple_copy = CerebrumCode(str(simple_const))
    simple_copy.description == 'something else'


def test_constant_with_description(simple_const, CerebrumCode):
    assert simple_const.description == 'simple'
    # Force clear cache
    CerebrumCode._cache = dict()
    simple_copy = CerebrumCode(str(simple_const))
    assert simple_const.description == simple_copy.description


def test_constant_enforce_description(database, simple_const, CerebrumCode):
    code = CerebrumCode('3eb30c3bf24e7ae')
    with pytest.raises(database.IntegrityError):
        code.insert()


def test_constant_with_language(languages, CerebrumCode):
    assert len(languages) >= 3
    code = CerebrumCode(
        'ef1bafcc3d0c4baf',
        description='localized constant',
        lang={str(languages[0]): 'foo', str(languages[1]): 'bar'})
    # str-lookup
    assert code.lang(str(languages[0])) == 'foo'
    # int-lookup
    assert code.lang(int(languages[0])) == 'foo'
    # const-lookup
    assert code.lang(languages[0]) == 'foo'
    assert code.lang(languages[1]) == 'bar'
    # Language without localization
    assert code.lang(languages[2]) == 'localized constant'


@pytest.mark.skipif(True, reason="How is this supposed to work?")
def test_pickle(simple_const):
    pickle = pytest.importorskip("pickle")
    pickle_str = pickle.dumps(simple_const)
    print pickle_str
    assert True


def test_typed_constant(typed_const, EntityType):
    intval = int(typed_const.entity_type)
    code = EntityType(intval)
    assert code.description == 'thing'


def test_map_constants(constants, Language, EntityType):
    for item in (getattr(constants, name) for name in dir(constants)):
        if isinstance(item, (Language, EntityType)):
            item.insert()
    fooval = int(constants.lang_foo)
    assert constants.map_const(fooval) == constants.lang_foo


def test_init_insert(constants, Language, EntityType):
    clist = filter(
        lambda attr: isinstance(attr, (Language, EntityType)),
        map(lambda name: getattr(constants, name), dir(constants)))
    print clist
    stats = constants.initialize(update=False, delete=False)
    print stats
    assert stats['total'] == len(clist)
    assert stats['inserted'] == len(clist)
    for const in clist:
        # Look up intval from db
        int(const)


def test_init_update(constants, Language, EntityType):
    clist = filter(
        lambda attr: isinstance(attr, (Language, EntityType)),
        map(lambda name: getattr(constants, name), dir(constants)))
    print clist
    # Insert constants
    stats = constants.initialize(update=False, delete=False)
    print stats
    assert stats['total'] == len(clist)
    assert stats['inserted'] == len(clist)
    # Update
    constants.lang_foo._desc = 'something else'
    stats = constants.initialize(update=True, delete=False)
    print stats
    assert stats['total'] == len(clist)
    assert stats['updated'] == 1
    # TODO: Read updated description from db?


@pytest.mark.skipif(
    True,
    reason="How to delete when we have a bunch of constants from makedb?")
def test_init_delete(constants, Language, EntityType):
    clist = filter(
        lambda attr: isinstance(attr, (Language, EntityType)),
        map(lambda name: getattr(constants, name), dir(constants)))
    print clist
    stats = constants.initialize(update=False, delete=False)
    print stats
    assert stats['total'] == len(clist)
    assert stats['inserted'] == len(clist)
    # Delete
    print dir(constants)
    print clist
    delattr(type(constants), 'lang_foo')
    stats = constants.initialize(update=True, delete=True)
    print stats
    assert stats['total'] == len(clist) - 1
    assert stats['deleted'] == 1


def test_fetch_constants(constants, Language):
    constants.initialize(update=False, delete=False)
    clist = constants.fetch_constants(Language)
    assert len(clist) == 2
    assert all(c in clist for c in [constants.lang_foo, constants.lang_bar])
    prefix = str(constants.lang_foo)[:-3]
    clist = constants.fetch_constants(Language, prefix_match=prefix)
    assert len(clist) == 1
    assert constants.lang_foo in clist


def test_human2constant_attr(constants, Language):
    constants.initialize(update=False, delete=False)
    const = constants.human2constant('lang_foo', const_type=Language)
    assert const == constants.lang_foo


def test_human2constant_strval(constants, Language):
    constants.initialize(update=False, delete=False)
    strval = str(constants.lang_foo)
    const = constants.human2constant(strval, const_type=Language)
    assert const == constants.lang_foo


def test_human2constant_intval(constants, Language):
    constants.initialize(update=False, delete=False)
    intval = int(constants.lang_foo)
    const = constants.human2constant(intval, const_type=Language)
    assert const == constants.lang_foo


def test_human2constant_str_intval(constants, Language):
    constants.initialize(update=False, delete=False)
    intval = str(int(constants.lang_foo))
    const = constants.human2constant(intval, const_type=Language)
    assert const == constants.lang_foo
