# -*- coding: utf-8 -*-
# Copyright 2016-2020 University of Oslo, Norway
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
"""
GPG data storage.

The mod_gpg module enables storage of arbitrary GPG-encrypted data for each
entity in Cerebrum.

To encrypt and store a data blob in Cerebrum, you'll need to apply a *tag* to
the data. The tag should describe the purpose of the encrypted data. In
addition, you'll have to configure a list of *recipients* of the data, i.e.
*who* to encrypt the data for.

The data is then encrypted and stored as a GPG message, with a message id.

.. note::
    Data is encrypted once per recipient, rather than once for a list of
    recipients.  This is done in order to easier remove/revoke messages for a
    given recipient, or to enable e.g. a script to decrypt and re-encrypt a
    message for another recipient.
"""

__version__ = "1.0"  # mod_gpg
