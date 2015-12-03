#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests adopted from the old PasswordChecker class

HISTORY
-------
These tests were moved from Cerebrum.modules.PasswordChecker. For the old
structure of the PasswordChecker and tests, please see

> commit 9a01d8b6ac93513a57ac8d6393de842939582f51
> Mon Jul 20 14:12:55 2015 +0200

"""
import cereconf

from nose import tools

from Cerebrum.modules.pwcheck import simple
from Cerebrum.modules.pwcheck.common import PasswordChecker
from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough
from Cerebrum.Utils import Factory


db = Factory.get('Database')()


class InvalidChars(simple.CheckInvalidCharsMixin, PasswordChecker):
    pass


@tools.raises(PasswordNotGoodEnough)
def test_nul_byte_fails():
    pc = InvalidChars(db)
    pc.password_good_enough("foo\0bar")


@tools.raises(PasswordNotGoodEnough)
def test_non_latin1_fails():
    pc = InvalidChars(db)
    pc.password_good_enough("fooæøåbar")


class InvalidLength(simple.CheckLengthMixin, PasswordChecker):
    pass


@tools.raises(PasswordNotGoodEnough)
def test_too_short_1():
    pc = InvalidLength(db)
    pc.password_good_enough("123")


@tools.raises(PasswordNotGoodEnough)
def test_too_short_2():
    pc = InvalidLength(db)
    pc.password_good_enough("1234567")


@tools.raises(PasswordNotGoodEnough)
def test_too_long():
    pc = InvalidLength(db)
    pc.password_good_enough("-"*20, password_max_length=18)


class InvalidConcat(simple.CheckConcatMixin, PasswordChecker):
    pass


def test_concat_succeeds():
    pc = InvalidConcat(db)
    pc.password_good_enough("CmToe")


@tools.raises(PasswordNotGoodEnough)
def test_concat_fails():
    pc = InvalidConcat(db)
    pc.password_good_enough("Camel*Toe")


class InvalidVariation(simple.CheckEntropyMixin, PasswordChecker):
    pass


def test_invalid_variations():
    failing_pwds = (
        "House",
        "housE",
        "hou3se",
        "Hous3",     # <- fails, because leadnig upcase does NOT
                     #    contribute to variation score
        "12345678",  # <- just digits
        "house",     # <- just lowercase
        "HOUSE",     # <- just uppercase
        "hoUSE",     # <- just upper+lower
        "ho123",     # <- just lower+digits
        "ho()/)",    # <- just lower+special
        "HO123",     # <- just upper+digits
        "HO/(#)",    # <- just upper+special
        "12()&)",    # <- just digits+special
        )
    pc = InvalidVariation(db)
    not_good = tools.raises(PasswordNotGoodEnough)(pc.password_good_enough)
    for fail in failing_pwds:
        yield not_good, fail


def test_valid_variations():
    successful_pwds = ("hOus3", "h()us3",)
    pc = InvalidVariation(db)
    for success in successful_pwds:
        yield pc.password_good_enough, success


class InvalidSequence(simple.CheckCharSeqMixin, PasswordChecker):
    pass


def test_invalid_sequences():
    fail_seqs = (
        "0123456789",        # <- digits
        "abcdefg",           # <- alphabet
        "hijkl",
        "mnopqrst",
        "uvwxyz",
        "qwerty", "rtyuio",  # <- 'qwerty'-row
        "asdfg", "ghjkl",    # <- 'asdf'-row
        "zxcvb", "bnm,.",    # <- 'zxcv'-row
        '!@#$%^',            # <- row with digits
        )
    pc = InvalidSequence(db)
    not_good = tools.raises(PasswordNotGoodEnough)(pc.password_good_enough)
    for fail in fail_seqs:
        yield not_good, fail


def test_valid_sequences():
    success_seqs = (
        "qwrty",   # gap of 2
        "abcefg",  # gap of 2
        "123567",  # gap of 2
        "bygg",    # used to fail
        "yhn",     # same offset in different kbd rows
        )
    pc = InvalidSequence(db)
    for success in success_seqs:
        yield pc.password_good_enough, success


class InvalidRepetition(simple.CheckRepeatedPatternMixin, PasswordChecker):
    pass


def test_invalid_repetition():
    fail_seqs = ("aaaaaa",
                 "ababab",
                 "bababa",
                 "abcabc",
                 "cbacba",
                 "abcdabcd",
                 "abccba",
                 "xyz11zyx",)

    pc = InvalidRepetition(db)
    not_good = tools.raises(PasswordNotGoodEnough)(pc.password_good_enough)

    for fail in fail_seqs:
        yield not_good, fail


def test_valid_repetition():
    success_seqs = ("aaaa",     # <- repetition is too short :)
                    "ababa",    # <- we need at least 3 consec pairs for a fail
                    "abcdab",   # <- non-consecutive repetition
                    "ab*ba",    # <- same story
                    "abc*cba",  # <- same story
                    "a1a2a3",
                    )
    pc = InvalidRepetition(db)
    for success in success_seqs:
        yield pc.password_good_enough, success


class InvalidUname(simple.CheckUsernameMixin, PasswordChecker):
    def __init__(self, uname):
        self.account_name = uname


def test_uname_in_password():
    user = "schnappi"
    pwds = (user, user[::-1])

    pc = InvalidUname(user)
    not_good = tools.raises(PasswordNotGoodEnough)(pc.password_good_enough)

    for fail in pwds:
        yield not_good, fail


class InvalidName(simple.CheckOwnerNameMixin, PasswordChecker):
    # TODO: Create personal accounts with names
    pass


def test_failing_name_passwords():
    pc = InvalidName(db)

    failing_tests = {
        "Schnappi von Krokodil": (
            "Schn-Kroko", "S*Krokodil", "Sc#Krok", "schn4ppi", "Schn-vo",
            "S-v-Kroko", "Kroko-Sch", "von-Schn", "Schn4Schn", "Kroko-Kroko",),
        "Ola Nordmann": (
            "O-Nordmann", "O-Nordman", "Nor-Ola", "Nord-Ola", "N-Ola",
            "No*Ola",), }

    test = tools.raises(PasswordNotGoodEnough)(pc._match_password_to_name)

    for name, failures in failing_tests.iteritems():
        for failure in failures:
            yield test, name, failure, None


def test_allowed_name_passwords():
    pc = InvalidName(db)

    passing_tests = {
        "Schnappi von Krokodil": (
            "S-Kr-blab",   # <- too few chars match
            "ScOn*Krble",  # <- not enough chars in each prefix for match
            ), }

    for name, successes in passing_tests.iteritems():
        for success in successes:
            yield pc._match_password_to_name, name, success, 5
