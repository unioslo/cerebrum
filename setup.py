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

# To install python modules in standard locations, and cerebrum files
# under /cerebrum, run like:
#  python2.2 setup.py install install_data --install-dir=/cerebrum
#
# To get the files in /etc under /cerebrum/etc, add:
#  --root=/cerebrum
#
# To build dist file:
#  python2.2 setup.py sdist

from distutils.command.build import build
from distutils.command import install_data
from distutils.core import setup, Command
from distutils.util import change_root, convert_path
import os
import pwd

#
# Which user should own the installed files
#
cerebrum_user = "cerebrum"

class my_install_data (install_data.install_data):
    def run (self):
        self.mkpath(self.install_dir)
        for f in self.data_files:
            # it's a tuple with dict to install to and a list of files
            tdict = f[0]
            dir = convert_path(tdict['path'])
            if not os.path.isabs(dir):
                dir = os.path.join(self.install_dir, dir)
            elif self.root:
                dir = change_root(self.root, dir)
            self.mkpath(dir)
            os.chmod(dir, tdict['mode'])
            if(os.geteuid() == 0):
                uinfo = pwd.getpwnam(tdict['owner'])
                uid, gid = uinfo[2], uinfo[3]
                os.chown(dir, uid, gid)
            if f[1] == []:
                # If there are no files listed, the user must be
                # trying to create an empty directory, so add the
                # directory to the list of output files.
                self.outfiles.append(dir)
            else:
                # Copy files, adding them to the list of output files.
                for data, mode in f[1]:
                    data = convert_path(data)
                    (out, _) = self.copy_file(data, dir)
                    self.outfiles.append(out)
                    os.chmod(out, mode)
                    if(os.geteuid() == 0):
                        os.chown(out, uid, gid)

# class my_install_data

prefix="."  # Should preferably be initialized from the command-line argument
sharedir="%s/share" % prefix
sbindir="%s/sbin" % prefix
bindir="%s/bin" % prefix
sysconfdir = "%s/etc/cerebrum" % prefix # Should be /etc/cerebrum/
logdir = "%s/var/log/cerebrum" % prefix # Should be /var/log/cerebrum/

setup (name = "Cerebrum", version = "0.1",
       url = "http://cerebrum.sourceforge.net",
       maintainer = "Cerebrum Developers",
       maintainer_email = "do.we@want.this.here",
       description = "Cerebrum...",
       # NOTE: all scripts ends up in the same dir!
       # scripts = ['contrib/no/uio/import_FS.py', 'contrib/generate_nismaps.py'],
       packages = ['Cerebrum',
                   'Cerebrum/extlib',
                   'Cerebrum/extlib/Plex',
                   'Cerebrum/modules',
                   'Cerebrum/modules/no',
                   'Cerebrum/modules/no/uio'],

       # options override --prefix
       #options = {'install_data': {'root' : '/foo/bar',  # prefix on slash
       #                            'install_dir': '/dddddddd' # prefix on no-slash
       #                            }},
       # data_files doesn't seem to handle wildcards
       data_files = [({'path': "%s/doc/cerebrum/design" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('design/drop_mod_stedkode.sql', 0644),
                       ('design/drop_mod_nis.sql', 0644),
                       ('design/drop_mod_posix_user.sql', 0644),
                       ('design/drop_core_tables.sql', 0644),
                       ('design/core_tables.sql', 0644),

                       ('design/mod_posix_user.sql', 0644),
                       ('design/mod_nis.sql', 0644),
                       ('design/core_data.sql', 0644),
                       ('design/mod_stedkode.sql', 0644)
                       ]),
                     ({'path': "%s/doc/cerebrum" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('design/cerebrum-core.dia', 0644),
                       ('design/cerebrum-core.html', 0644),
                       ('design/adminprotocol.html', 0644),
                       ('README', 0644),
                       ('COPYING', 0644)
                       # 'doc/*'
                       ]),
                     ## ("%s/samples" % sharedir,
                     ##  ['doc/*.cron']),
                     ({'path': "%s" % bindir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('cerebrum_path.py', 0644)]
                      ),
                     ({'path': "%s" % sbindir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('cerebrum_path.py', 0644)]
                      ),
                     ({'path': "%s" % sbindir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('server/bofhd.py', 0755),
                       ('server/bofhd_cmds.py', 0644),   # WRONG!
                       ('server/cmd_param.py', 0644),    # WRONG!
                       ('contrib/generate_nismaps.py', 0755),
                       ('contrib/no/import_SATS.py', 0755),
                       ('contrib/no/import_from_MSTAS.py', 0755),
                       ('contrib/no/uio/import_OU.py', 0755),  # TODO: These should not allways be installed?
                       ('contrib/no/uio/import_FS.py', 0755),
                       ('contrib/no/uio/import_LT.py', 0755),
                       ('contrib/no/uio/import_from_FS.py', 0755),
                       ('contrib/no/uio/import_from_LT.py', 0755),
                       ('contrib/no/uio/import_userdb_XML.py', 0755)
                       
                       ]),
                     ({'path': "%s" % bindir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('client/bofh.py', 0755)]),
                     ({'path': "%s/cerebrum/client" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                       [('client/passweb.py', 0755),
                        ('client/passweb_form.html', 0644),
                        ('client/passweb_receipt.html', 0644),
                        ('java/jbofh/dist/lib/JBofh.jar', 0644)]),
                     ({'path': "%s/cerebrum/client/linux" % sharedir,  # TODO: arch
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('java/jbofh/lib/libJavaReadline.so', 0644)]),
                     ({'path': sysconfdir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      [('cereconf.py', 0644),
                       ('server/config.dat', 0644)
                       ]),
                     ({'path': logdir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      []),
                     ({'path': "%s/cerebrum/data" % sharedir,
                       'owner': cerebrum_user,
                       'mode': 0750},
                      []),
                     ],
       # Overridden command classes
       cmdclass = {'install_data': my_install_data}
      )
