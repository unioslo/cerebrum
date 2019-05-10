#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copied from Leetah
from __future__ import unicode_literals

import argparse
import datetime
import logging
import os

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options

logger = logging.getLogger(__name__)


def ldap_export():
    global_ret = 0
    today = datetime.date.today()

    script_dir = os.path.join(cereconf.CB_PREFIX,
                              'share', 'cerebrum', 'contrib')

    logger.info("Starting export of ldap data")

    # 1. create the posix_user_ldif
    script = os.path.join(script_dir, 'generate_posix_ldif.py')
    script_arg = (
        "--user-spread system@ldap --user-file %s/ldap_users_ldif" %
        (cereconf.DUMPDIR, ))

    script_cmd = "%s %s %s" % ('python', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret += ret
    logger.info("generate_posix_ldif.py: %s" % ret)

    # 2. create the ou_ldif
    script = os.path.join(script_dir, 'generate_org_ldif.py')
    script_arg = "-o %s/ldap/ou_ldif" % (cereconf.DUMPDIR, )
    script_cmd = "%s %s %s" % ('python', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret += ret
    logger.info("generate_org_ldif.py: %s" % ret)

    # 3. concatenate all the ldif files into temp_uit_ldif
    my_dump = os.path.join(cereconf.DUMPDIR, "ldap")

    script_cmd = ' '.join((
        "/bin/cat",
        os.path.join(my_dump, "ou_ldif"),
        os.path.join(my_dump, "group.ldif"),
        os.path.join(my_dump, "/users_ldif"),
        os.path.join(my_dump, "kurs.ldif"),
        os.path.join(cereconf.CB_PREFIX,
                     "var/source/ldap/fake_ldap_users.ldif"),
        ">",
        os.path.join(my_dump, "temp_uit_ldif"),
    ))

    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    global_ret += ret
    logger.info("cat ou_ldif users_ldif ... > temp_uit_ldif: %s", ret)

    # 4. create a new ldif file based on the difference between the old and new
    #    data from cerebrum
    outfile = 'uit_diff_{}'.format(today.strftime('%Y%m%d'))
    outcpy = 'uit_diff_{}'.format(today.strftime('%Y%m%d_%H%M'))

    script = os.path.join(script_dir, 'no', 'uit', 'ldif-diff.pl')
    script_arg = ' '.join((
        os.path.join(cereconf.DUMPDIR, "/ldap/uit_ldif"),
        os.path.join(cereconf.DUMPDIR, "ldap/temp_uit_ldif"),
        ">",
        os.path.join(cereconf.DUMPDIR, "ldap", outfile),
    ))
    script_cmd = "%s %s %s" % ('perl', script, script_arg)
    logger.debug("Running %s" % script_cmd)
    ret = os.system(script_cmd)
    logger.info("ldif-diff.pl: %s" % ret)
    aret = os.system(
        ' '.join((
            "cp",
            os.path.join(cereconf.DUMPDIR, 'ldap', outfile),
            os.path.join(cereconf.DUMPDIR, 'ldap', outcpy),
        )))
    global_ret += ret + aret
    logger.info("cp: %s" % aret)

    logger.debug("Finished running ldap export: global ret=%s", global_ret)
    return global_ret


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate combined ldap export file")
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    retval = ldap_export()
    exit_code = 1 if retval else 0

    logger.info('Done %s (%d)', parser.prog, exit_code)
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
