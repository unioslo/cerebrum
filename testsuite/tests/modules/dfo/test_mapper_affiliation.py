# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.no.dfo.mapper` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum.modules.no.dfo import mapper


class _ExampleAffiliationMap(mapper.DfoAffiliations):

    employee_group_map = mapper.AffiliationMap({
        (8, 50): None,  # Explicitly disallow this MG/MUG
        (9, 90): "TILKNYTTET/ekst_partner",
        (9, 91): "TILKNYTTET/ekst_partner",
    })

    assignment_code_map = mapper.AffiliationMap({
        20000214: "ANSATT/vitenskapelig",
        20001085: "ANSATT/tekadm",
        20001095: "ANSATT/tekadm",
        20001183: "ANSATT/vitenskapelig",
    })

    assignment_category_map = mapper.AffiliationMap({
        50078118: "ANSATT/tekadm",
        50078119: "ANSATT/tekadm",
        50078120: "ANSATT/vitenskapelig",
    })


class _ExampleMapper(mapper.EmployeeMapper):
    get_affiliations = _ExampleAffiliationMap()


class MockHrObject(object):

    def __init__(self, enable, affiliations):
        self.enable = enable
        self.affiliations = affiliations

    @classmethod
    def from_data(cls, mapper, employee_data):
        return cls(
            employee_data.get('eksternbruker'),
            mapper.get_affiliations(employee_data),
        )


@pytest.fixture
def mapper():
    return _ExampleMapper()


TODAY = datetime.date(2024, 11, 15)
START = TODAY - datetime.timedelta(days=30)
END = TODAY + datetime.timedelta(days=30)

#
# Template data for the employee fixture.
#
# This template serves as a base for all tests.  The tests can remove or modify
# data as needed - this is easier than providing new data.
#
BASE_EMPLOYEE = {
    'id': 1,
    'eksternbruker': True,
    'stillingId': 500,
    'medarbeidergruppe': 1,
    'medarbeiderundergruppe': 1,
    'startdato': START,
    'sluttdato': END,
    'tilleggsstilling': [
        {
            'stillingId': 501,
            'startdato': START,
            'sluttdato': END,
        }
    ],
    # supplemented assignment data
    'assignments': {
        500: {
            'id': 500,
            'organisasjonId': 100,
            'startdato': START,
            'sluttdato': END,
            'stillingskode': 20001085,
            'stillingskat': [{'stillingskatId': 50078118}],
        },
        501: {
            'id': 501,
            'organisasjonId': 101,
            'startdato': START,
            'sluttdato': END,
            'stillingskode': 20001183,
            'stillingskat': [{'stillingskatId': 50078120}],
        },
    }
}


def _copy(value):
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, (list, set, tuple)):
        return type(value)(_copy(v) for v in value)
    return value


@pytest.fixture
def employee():
    return _copy(BASE_EMPLOYEE)


#
# DfoAffiliations mapper (EmployeeMapper.get_affiliations) tests
#


def test_get_affiliation_from_group(mapper, employee):
    """
    Check that employee group mappings can set the affiliation for our main
    assignment.
    """
    employee.update({
        'medarbeidergruppe': 9,
        'medarbeiderundergruppe': 90,
    })

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 2

    aff, ou, start, end = affiliations[0]
    assert aff == "TILKNYTTET/ekst_partner"
    assert 100 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END

    aff, ou, start, end = affiliations[1]
    assert aff == "ANSATT/vitenskapelig"
    assert 101 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END


def test_omit_affiliation_from_group(mapper, employee):
    """
    Check that explicitly omitted employee groups won't get an affiliation.
    """
    employee.update({
        'medarbeidergruppe': 8,
        'medarbeiderundergruppe': 50,
    })
    del employee['assignments'][501]

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 0


def test_get_affiliation_from_code(mapper, employee):
    """ Check that we can get an affiliation from the assignment code. """
    employee = _copy(BASE_EMPLOYEE)
    del employee['assignments'][501]

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 1
    aff, ou, start, end = affiliations[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END


def test_get_affiliation_from_category(mapper, employee):
    """
    Check that we can get an affiliation from the assignment category when
    the assignment code doesn't exist in our mapping.
    """
    employee = _copy(BASE_EMPLOYEE)
    employee['assignments'][500]['stillingskode'] = 0
    del employee['assignments'][501]

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 1
    aff, ou, start, end = affiliations[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END


def test_get_additional_assignments(mapper, employee):
    """
    Check that we can fetch additional assignment affiliations.
    """
    affiliations = list(mapper.get_affiliations(employee))

    assert len(affiliations) == 2

    aff, ou, start, end = affiliations[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END

    aff, ou, start, end = affiliations[1]
    assert aff == "ANSATT/vitenskapelig"
    assert 101 in [id_value for _, id_value in ou]
    assert start == START
    assert end == END


def test_get_missing_org_id(mapper, employee):
    """
    Check that no affiliations are returned when the assignment org unit is
    missing.
    """
    for v in employee['assignments'].values():
        del v['organisasjonId']

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 0


def test_get_missing_assignment_mapping(mapper, employee):
    """
    Check that no affiliations are returned when employee group, category, and
    code fails to map to an affiliation for all assignments.
    """
    for v in employee['assignments'].values():
        v.update({
            'stillingskat': [],
            'stillingskode': 0,
        })

    affiliations = list(mapper.get_affiliations(employee))
    assert len(affiliations) == 0


#
# EmployeeMapper.get_active_affiliations tests
#


def test_get_active_affiliations(mapper, employee):
    hr_object = MockHrObject.from_data(mapper, employee)

    result = list(mapper.get_active_affiliations(hr_object, TODAY))
    assert len(result) == 2

    aff, ou = result[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]

    aff, ou = result[1]
    assert aff == "ANSATT/vitenskapelig"
    assert 101 in [id_value for _, id_value in ou]


def test_get_active_affiliations_duplicates(mapper, employee):
    employee['assignments'][501]['organisasjonId'] = 100
    hr_object = MockHrObject.from_data(mapper, employee)

    result = list(mapper.get_active_affiliations(hr_object, TODAY))
    assert len(result) == 1

    aff, ou = result[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]


def test_get_active_affiliations_date_main(mapper, employee):
    # TODO: We may want to re-consider this behaviour:
    # For the main assignment, we use the startdato/sluttdato from the employee
    # (and not the assignment itself)
    employee['sluttdato'] = TODAY - datetime.timedelta(days=3)
    hr_object = MockHrObject.from_data(mapper, employee)

    result = list(mapper.get_active_affiliations(hr_object, TODAY))
    assert len(result) == 1

    aff, ou = result[0]
    assert aff == "ANSATT/vitenskapelig"
    assert 101 in [id_value for _, id_value in ou]


def test_get_active_affiliations_date_secondary(mapper, employee):
    # TODO: We may want to re-consider this behaviour:
    # For the secondary assignment, we use the startdato/sluttdato from the
    # employee 'tilleggsstilling' list (and not the assignments themselves)
    for secondary in employee['tilleggsstilling']:
        secondary['sluttdato'] = TODAY - datetime.timedelta(days=3)
    hr_object = MockHrObject.from_data(mapper, employee)

    result = list(mapper.get_active_affiliations(hr_object, TODAY))
    assert len(result) == 1

    aff, ou = result[0]
    assert aff == "ANSATT/tekadm"
    assert 100 in [id_value for _, id_value in ou]


#
# EmployeeMapper.is_active tests
#


def test_is_active(mapper, employee):
    hr_object = MockHrObject.from_data(mapper, employee)
    assert mapper.is_active(hr_object, TODAY)


def test_is_active_not_enabled(mapper, employee):
    employee['eksternbruker'] = False
    hr_object = MockHrObject.from_data(mapper, employee)
    assert not mapper.is_active(hr_object, TODAY)


def test_is_active_no_active_affiliations(mapper, employee):
    hr_object = MockHrObject.from_data(mapper, employee)
    assert not mapper.is_active(hr_object, END + datetime.timedelta(days=3))
