# -*- coding: utf-8 -*-
# Copyright 2012 University of Oslo, Norway
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
"""Default settings for all CIS services. These settings are overidden at each
instance and for most CIS services.

"""

from __future__ import unicode_literals

#
# The connection
#

# The port the CIS daemon should run at.
PORT = 0

# The interface the CIS daemon should listen at. Default is 0.0.0.0 which means
# that it accept incoming connections from every interface.
INTERFACE = '0.0.0.0'

#
# Certificate management
#

# The file with the private key used by the CIS servers for TLS connections.
# Note that the server's certificate's public key must correspond to this
# private key.
SERVER_PRIVATE_KEY_FILE = None

# The file with the x509 certificate of the server. Note that the private key
# must correspond to the certificate's public key.
SERVER_CERTIFICATE_FILE = None

# The file(s) with the certificates for which is accepted as the issuers of
# client certificates. This means that a client must have a certificate that is
# signed by one of these CAs to be able to connect to the CIS service. A normal
# solution is to let CIS' own server certificate be the CA, which means that
# the clients has to be signed by the server itself.
#
# Note that to support chains of certificates, you need to supply all the
# certificates in the chain to be able to accept them. An example of a chain is
# a client which is signed be a middle CA, which again has been signed by a
# proper CA.
#
# You could specify directories in the list, but you then have to run
# `cacertdir_rehash` on the directory to make it work. This creates hashed
# symlinks to the certificates, so that OpenSSL could easily find them. What
# the script does is just running::
#
#   openssl x509 -noout -subject_hash -in cert.pem
#
# The output becomes the symlink's filenames. Note that the hashes might vary
# between OpenSSL versions, so this has to be run on on production server.
CERTIFICATE_AUTHORITIES = []

# Whitelist of fingerprints of client certificates that should get accepted for
# connecting to the server(s). If the list is None, it will be ignored and
# every client signed by the CAs will be accepted. Note that if it's an empty
# list no client will be accepted - this is to avoid misconfigurations leading
# to a wide open service.
#
# Note that it is not enough to just put a fingerprint in this list. The issuer
# of the client certificate must be listed in CERTIFICATE_AUTHORITIES as well.
#
# The fingerprints are by default in SHA-1 format, but that could be changed,
# see FINGERPRINT_ALGORITHM.
#
# The reason for having such a whitelist is to avoid accepting every
# certificate from an issuer, e.g. the server certificate, in case it is used
# for other services as well.
#
# Note that every certificate that is used in a certificate chain has to be
# whitelisted, which includes the CAs certificates. To get the SHA-1
# fingerprint of a certificate, use the command:
#
#   openssl x509 -in certificate.pem -noout -fingerprint -sha1
#
FINGERPRINTS = []

# The algorithm used to create the fingerprint of an algorithm. Fingerprints
# can, in theory, be hacked through collision attacks. Use SHA-256 or SHA-512
# in the future. Or rather SHA-3 when that is ready.
#
# See `openssl dgst -h` for a list of supported algorithms.
FINGERPRINT_ALGORITHM = 'sha1'


#
# Logging
#

# Note that the CIS services use twisted's log functionality instead of
# Cerebrum's own. This is to avoid blocking conflicts, since the services are
# threaded, and it is easier to use the native logger instead of adapting our
# current logger.
#
# Note that two different daemons must not log to the same file, as this would
# create race conditions and write conflicts.
LOG_FILE = None

# Regexes that should be applied to emitted logs.
# I.e.
#
# LOG_FORMATTERS = (
#         # Regexes should not overlap as patterns are matched one after
#         # another on the same log message. Check
#         # SoapListener.TwistedCerebrumLogger
#         (# Filter password values in method calls out of log
#                      #  pattern
#             r"(authenticate\(username=.*, ?password=['\"])(.*?)(['\"]\))$",
#                     #replacement
#             r"\1secret\3"
#         ),
# )
LOG_FORMATTERS = ()

# The name of the job to be put in the log files. Cerebrum's root logs contains
# the elements:
#
#  YYYY-MM-DD HH:mm:ss <jobname>: <loglevel> <message>
#
# The job name is an identifier to be able to separate the different jobs'
# logs, and is useful e.g. for mailloggers. The default is just 'cis' for all
# CIS servers, but it is changeable to split out certain servers.
LOG_NAME = 'cis'

# The number of bytes a log file may contain before it gets rotated.
LOG_LENGTH = 50 * 1024 * 1024  # = 50MiB

# The maxiumum number of rotated files. If the number is reached, the oldest
# log file gets deleted.
LOG_MAXROTATES = 10

# The prefix to be added to logs. This is to comply with Cerebrum's log
# format, e.g:
#
#   2011-09-13 15:40:28 cis_individuation: DEBUG: Logger started
#
# where the 'cis_individuation:' is the prefix being used. Without this the
# logs will not get parsed and sent by e-mail to the sysadmins.
LOG_PREFIX = 'cis:'

#
# Miscellaneous
#

# The Cerebrum class that will be used for the Cerebrum related functionality.
# A server's main service contains public methods that is callable by the
# clients. These methods are again calling an instance of this Cerebrum class.
# This is done to separate the server functionality with the Cerebrum
# functionality, to easier be able to switch server software if that is needed.
#
# The string must be in a format understandable by Cerebrum.Utils.dyn_import.
# Example:
#
#   ['Cerebrum.modules.no.uio.Individuation/Indiv',] # UiO's simple service
CEREBRUM_CLASS = None


#
# Individuation specific settings
#

# The following settings are only related to the forgotten-password service.


# The number of days a person or account should be considered "fresh". This is
# used to avoid blocking recent changes phone numbers for fresh entities. Note
# that this must be longer than the max delay value, to avoid that some fresh
# students could still be blocked.
FRESH_DAYS = 10
