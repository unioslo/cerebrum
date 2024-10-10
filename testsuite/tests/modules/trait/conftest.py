# encoding: utf-8
"""
Common fixtures for :mod:`Cerebrum.modules.trait` tests
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

import Cerebrum.Group
import Cerebrum.Person
import Cerebrum.OU
from Cerebrum.testutils import datasource
from Cerebrum.modules.trait import constants


@pytest.fixture
def person_cls():
    return Cerebrum.Person.Person


@pytest.fixture
def person_creator(database, const, person_cls):
    """
    A helper fixture to create person objects.
    """
    person_ds = datasource.BasicPersonSource()

    def _create_persons(limit=1):
        for person_dict in person_ds(limit=limit):
            person = person_cls(database)
            gender = person_dict.get('gender')
            if gender:
                gender = const.human2constant(gender, const.Gender)
            gender = gender or const.gender_unknown
            person.populate(
                person_dict['birth_date'],
                gender,
                person_dict.get('description'),
            )
            person.write_db()
            person_dict['entity_id'] = person.entity_id
            yield person, person_dict

    return _create_persons


#
# Some traits
#


@pytest.fixture
def constant_creator(constant_module):
    """ create constants that can be found with const.get_constant(). """
    attrs = []

    def create_constant(constant_type, value, *args, **kwargs):
        description = kwargs.pop('description',
                                 "test constant " + six.text_type(value))
        kwargs['description'] = description
        code = constant_type(value, *args, **kwargs)
        code.insert()

        # Inject the code as an attribute of a class that exists both in
        # in the Factory.get("Constants") and `const` fixture mro
        #
        # This is needed for some of the ConstantsBase lookup methods (e.g.
        # `get_constant`)
        attr = 'test_code_' + format(id(code), 'x')
        setattr(constant_module.CoreConstants, attr, code)
        attrs.append(attr)
        return code

    yield create_constant

    for attr in attrs:
        delattr(constant_module.CoreConstants, attr)


@pytest.fixture(autouse=True)
def _clear_trait_code_cache():
    """ Clear the trait code cache. """
    constants._EntityTraitCode._cache = {}


@pytest.fixture
def trait_a(constant_module, constant_creator):
    return constant_creator(
        constants._EntityTraitCode,
        "pta-ffe2dcd46eac",
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def trait_b(constant_module, constant_creator):
    return constant_creator(
        constants._EntityTraitCode,
        "ptb-9da7bfc5984d",
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def trait_c(constant_module, constant_creator):
    return constant_creator(
        constants._EntityTraitCode,
        "ptc-e2ad43f59ddd",
        constant_module.CoreConstants.entity_person,
    )


@pytest.fixture
def trait_d(constant_module, constant_creator):
    return constant_creator(
        constants._EntityTraitCode,
        "ptd-feffeadb9dcd",
        constant_module.CoreConstants.entity_person,
    )
