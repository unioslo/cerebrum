#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
""" Basic tests for GnuPG encryption and decryption.
"""

import random
import string
import unittest

import cerebrum_path
import cereconf
from Cerebrum.utils.gpg import gpgme_encrypt, gpgme_decrypt, get_gpgme_context


RECIPIENT_KEY_ID = '06B0A991A41F3955F1DFD524D04D25F75D4C1CC4'


def can_test():
    """
    We can only test this functionality if the recipient key ID is available
    to GPG.
    """
    context = get_gpgme_context()
    try:
        context.get_key(RECIPIENT_KEY_ID)
    except Exception:
        return False
    return True


class GnuPGPasswordTest(unittest.TestCase):
    """
    Test cases for GPG-passwords
    """

    def setUp(self):
        uni_chars = unicode(string.ascii_letters) + unicode(string.digits)
        # generate a random 32 characters long unicode string and then append
        # 'æøå' in order to provoke some errors
        random_prefix = u''.join(random.choice(uni_chars) for _ in range(32))
        self.rnd_password_unicode = random_prefix + 'æøå'.decode('utf-8')
        self.rnd_password_str = self.rnd_password_unicode.encode('utf-8')
        # our test key
        self.recipient_key_id = RECIPIENT_KEY_ID

    @unittest.skipIf(not can_test(), "GPG incorrectly configured for testing")
    def test_gnupg_encrypt_decrypt(self):
        """
        Tests GnuPG encryption and decryption
        """
        # test for unicode input
        ciphertext_for_unicode = gpgme_encrypt(
            message=self.rnd_password_unicode,
            recipient_key_id=self.recipient_key_id)
        ciphertext_for_unicode2 = gpgme_encrypt(
            message=self.rnd_password_unicode,
            recipient_key_id=self.recipient_key_id)
        # test for bytestring input
        ciphertext_for_str = gpgme_encrypt(
            message=self.rnd_password_str,
            recipient_key_id=self.recipient_key_id)
        # test for decrypt of unicode
        self.assertEqual(self.rnd_password_unicode,
                         gpgme_decrypt(ciphertext_for_unicode).decode('utf-8'),
                         'Unicode string not properly decrypted')
        # test decrypt for bytesstring
        self.assertEqual(self.rnd_password_str,
                         gpgme_decrypt(ciphertext_for_str),
                         'Bytestring not properly decrypted')
        # theoretical and HIGHLY improbable chance for failure
        # when GnuPG and the OS work properly
        # The same input encrypted twice should NOT result
        # in identical ciphertext
        self.assertNotEqual(ciphertext_for_unicode,
                            ciphertext_for_unicode2,
                            'Weak cryptography')
        self.assertEqual(gpgme_decrypt(ciphertext_for_unicode),
                         gpgme_decrypt(ciphertext_for_unicode2),
                         'Identical input should result in identical decrypt')


if __name__ == '__main__':
    unittest.main()
