#!/usr/bin/env python
# -*- coding: utf-8 -*-

__doc__="""
Uit specific extension for Cerebrum. For handling of contact information.
"""

class PhoneNums:
    """
    This class provides functionality for "massaging" phone numbers.
    """
    def __init__(self, logger):
        self.logger = logger

    def convert_to_e164_format(self, number, country_code = "NO"):
        """
        Takes a phone number as input and returns it in the format "+<Country code><phone number>".
        Returns None if there is a problem when parsing the number.
        :param string number: Phone number to convert.
        :param string country_code: Country code to use as default. Default value is 'NO'
        """
        import phonenumbers

        try:
            res = phonenumbers.parse(number, country_code)
        except phonenumbers.phonenumberutil.NumberParseException as e:
            self.logger.warn("Problem when parsing '%s'. Error message: %s" % (number, e))
            return None

        if phonenumbers.is_possible_number(res):
            return phonenumbers.format_number(res, phonenumbers.PhoneNumberFormat.E164)
        else:
            self.logger.warn("'%s' is not an accepted number." % number)
            return None

