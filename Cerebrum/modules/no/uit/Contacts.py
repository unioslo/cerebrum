# -*- coding: utf-8 -*-
"""
Uit specific extension for Cerebrum. For handling of contact information.
"""
import logging

import phonenumbers

logger = logging.getLogger(__name__)


class PhoneNums(object):
    """
    This class provides functionality for "massaging" phone numbers.
    """
    def __init__(self, logger=None):
        pass

    def convert_to_e164_format(self, number, country_code="NO"):
        """
        Takes a phone number as input and returns it in E.164 format.

        - Returns valid phone numbers on the E.164 format
        ("+<Country code><phone number>").
        - Returns None if there is a problem when parsing the number.

        :param string number:
            Phone number to convert.
        :param string country_code:
            Country code to use as default. Default value is 'NO'
        """
        try:
            res = phonenumbers.parse(number, country_code)
        except phonenumbers.phonenumberutil.NumberParseException as e:
            logger.warning("Problem when parsing %r: %s", number, e)
            return None

        if phonenumbers.is_possible_number(res):
            return phonenumbers.format_number(
                res, phonenumbers.PhoneNumberFormat.E164)
        else:
            logger.warning("'%s' is not an accepted number", number)
            return None
