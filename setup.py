#!/usr/bin/env python2.2
#
# Placing of files when installing Cerebrum
# -----------------------------------------
#
# NOTE: Atleast while developing, I would reccomend using "--prefix
# /cerebrum".  Otherwise all these paths are relative to / unless
# otherwise noted.
#
# / 
#   README:       usr/share/cerebrum/doc/
#   COPYING:      usr/share/cerebrum/doc/
#
# Cerebrum/
#   */*.py:       under site-packages of the running python interpreter
#   cereconf.py:  etc/cerebrum/
#   */tests/*:    Not installed
#
#   Note that the entire Cerebrum/modules catalog is installed.
#   Site-specific components should assert that they do not use names
#   that clashes with the files distributed with cerebrum, otherwise
#   they may be overwritten by a later installation.  The naming
#   syntax should be that of a reversed dns name with '.' replaced with
#   '/'.  Eg, for uio.no, the directory modules/uio/no is used.
#
# design/
#   *.sql:        usr/share/cerebrum/doc/design/
#   *.html,*.dia: usr/share/cerebrum/doc/
# 
# doc/
#   *:            usr/share/cerebrum/doc/
#   *cron*:       usr/share/cerebrum/doc/samples
#
# testsuite/
#   *:            Not installed
#
# server/
#   bofhd.py:     usr/sbin/
#   config.dat:   etc/cerebrum/bofhd.config
#   *.py:         usr/share/cerebrum/bofhd (site-packages/modules/bofhd better?)
#
# client/
#   bofh.py:      usr/bin
#   config-files: etc/cerebrum/client
#   template.ps:  usr/share/cerebrum/client
#   passweb.py:   usr/share/cerebrum/client ?
#
#   As the client will be installed stand-alone on numerous machines,
#   the files for it resides in a separate directory to make
#   distribution easier.  All clients should share atleast one config
#   file
#
# java/jbofh/
#   jbofh.jar:    usr/share/cerebrum/client
#   libJavaReadline.so:
#                 usr/share/cerebrum/client/linux
#   jbofh.sh:     usr/bin
#
# contrib/
#   generate_nismaps.py:  usr/sbin
#
# contrib/no
#   *.py:         usr/sbin 
# contrib/no/uio
#   *.py:         usr/sbin 
#
# contrib/no/uio/studit
#   *:            usr/share/cerebrum/studit
#
#
# Other directories/files:
#
#   var/log/cerebrum/:
#        All log-files for cerebrum, unless the number of files is
#        above 4, when a seperate directory should be created.
#
#   usr/share/cerebrum/data:
#        A number of subdirectories for various backends

# Run like:
#  python2.2 setup.py -n install --prefix /foobar
# To build dist file:
#  python2.2 setup.py sdist

from distutils.core import setup

setup (name = "Cerebrum", version = "0.1",
       url = "http://cerebrum.sourceforge.net",
       maintainer = "Cerebrum Developers",
       maintainer_email = "do.we@want.this.here",
       description = "Cerebrum...",
       # NOTE: all scripts ends up in the same dir!
       scripts = ['contrib/no/uio/import_FS.py', 'contrib/generate_nismaps.py'],
       packages = ['Cerebrum'],
       # data_files doesn't seem to handle wildcards
       data_files = [("usr/share/doc/cerebrum/design",
                      ['design/drop_mod_stedkode.sql',
                       'design/drop_mod_nis.sql',
                       'design/drop_mod_posix_user.sql',
                       'design/drop_core_tables.sql',
                       'design/core_tables.sql',
                       'design/mod_posix_user.sql',
                       'design/mod_nis.sql',
                       'design/core_data.sql',
                       'design/mod_stedkode.sql'
                       ]),
                     ("etc/cerebrum",
                      ["Cerebrum/cereconf.py"
                       ])
                     ]
      )
