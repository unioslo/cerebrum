# -*- coding: utf-8 -*-
"""
Test fixtures for :mod:`Cerebrum.modules.consent`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

import Cerebrum.Errors
from Cerebrum.modules.consent import ConsentConstants


@pytest.fixture
def database(database):
    """ Database with cl_init set. """
    database.cl_init(change_program='mod-consent-tests')
    return database


@pytest.fixture(autouse=True)
def _patch_constant_module(constant_module):
    """ Ensure that our constants exists. """
    co_cls = constant_module.Constants

    co_cls.ConsentType = ConsentConstants._ConsentTypeCode
    ConsentConstants._ConsentTypeCode._cache = {}

    co_cls.EntityConsent = ConsentConstants._EntityConsentCode
    ConsentConstants._EntityConsentCode._cache = {}

    co_cls.opt_in = ConsentConstants.Constants.consent_opt_in
    co_cls.opt_out = ConsentConstants.Constants.consent_opt_out

    cl_cls = constant_module.CLConstants
    cl_cls.consent_approve = ConsentConstants.CLConstants.consent_approve
    cl_cls.consent_decline = ConsentConstants.CLConstants.consent_decline
    cl_cls.consent_remove = ConsentConstants.CLConstants.consent_remove

    for code in (cl_cls.consent_approve,
                 cl_cls.consent_decline,
                 cl_cls.consent_remove,
                 co_cls.opt_in,
                 co_cls.opt_out):
        try:
            int(code)
        except Cerebrum.Errors.NotFoundError:
            code.insert()


@pytest.fixture
def opt_in(constant_module):
    return constant_module.Constants.opt_in


@pytest.fixture
def opt_out(constant_module):
    return constant_module.Constants.opt_out


@pytest.fixture
def entity_type(constant_module):
    cls = constant_module._EntityTypeCode
    code = cls('dfff34bdd3fde7da', description='Test type')
    code.insert()
    return code


@pytest.fixture
def consent_foo(entity_type, opt_in):
    code = ConsentConstants._EntityConsentCode(
        "test-consent-foo",
        entity_type=entity_type,
        consent_type=opt_in,
        description="test consent-foo opt-in",
    )
    code.insert()
    return code


@pytest.fixture
def consent_bar(entity_type, opt_out):
    code = ConsentConstants._EntityConsentCode(
        "test-consent-bar",
        entity_type=entity_type,
        consent_type=opt_out,
        description="test consent-bar opt-out",
    )
    code.insert()
    return code
