#!/usr/bin/env python2.2

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
