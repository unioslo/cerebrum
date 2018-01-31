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
u""" TeX helper functions.

Configuration
-------------
PRINT_LATEX_CMD
    Full path to a 'latex' command, to prepare '.tex' files. Only used by
    the `prepare_tex' function. Without this setting, it is not possible to
    prepare TeX files for printing.

    Example:

      PRINT_LATEX_CMD = '/usr/bin/latex'

PRINT_DVIPS_CMD
    Full path to a 'dvips' command, to prepare '.dvi' files. Only used by
    the `prepare_tex' function. Without any of the PRINT_DVI*_CMD settings, it
    is not possible to prepare TeX files for printing.

    `prepare_tex' will prefer PRINT_DVIPS_CMD over PRINT_DVIPDF_CMD.

    Example:

      PRINT_DVIPS_CMD = '/usr/bin/dvips'

PRINT_DVIPDF_CMD
    Full path to the 'dvipdf' command, to prepare '.dvi' files. Only used by
    the `prepare_tex' function. Without any of the PRINT_DVI*_CMD settings, it
    is not possible to prepare TeX files for printing.

    `prepare_tex' will prefer PRINT_DVIPS_CMD over PRINT_DVIPDF_CMD.

    Example:

      PRINT_DVIPDF_CMD = '/usr/bin/dvipdf'

"""
import os
import time
import tempfile

import cereconf

from Cerebrum.Utils import Factory


__tex_log = None
u""" Shared log for subprocess output. """


def _get_tex_log():
    u""" Lazy instantiation of __tex_log. """
    global __tex_log
    if __tex_log is None or not os.path.isfile(__tex_log):
        fd, __tex_log = tempfile.mkstemp(
            prefix='cerebrum_tex_{}'.format(time.time()))
        fd.close()
    return __tex_log


def prepare_tex(filename):
    u""" Prepare a tex document for printing.

    :param str filename: The TeX file to prepare.

    :return str: The output filename.

    :raise IOError: When unable to create an output file.

    """
    def _new_ext(filename, ext):
        base = os.path.splitext(filename)[0]
        return os.path.extsep.join((base, ext))

    logger = Factory.get_logger('cronjob')
    logfile = _get_tex_log()
    output = None

    ext = os.path.splitext(filename)[1]
    if not ext or not ext[len(os.path.extsep):] in ('tex', 'latex'):
        raise IOError("Invalid file type (%s), expecting TeX document" % ext)

    oldpwd = os.getcwd()
    if os.path.dirname(filename):
        os.chdir(os.path.dirname(filename))
    filename = os.path.basename(filename)
    try:
        # tex to dvi
        rc = os.system(
            "%s --interaction nonstopmode %s >> %s 2>&1" % (
                cereconf.PRINT_LATEX_CMD, filename, logfile))
        dvi_file = _new_ext(filename, 'dvi')
        if rc != 0:
            logger.warn(
                "Exit code %d when preparing tex document %r, "
                "see %s for details", rc, filename, logfile)
        if not os.path.isfile(dvi_file):
            raise IOError("Error preparing document %r, "
                          "see %s for details" % (filename, logfile))

        # dvi to ps/pdf
        if cereconf.PRINT_DVIPS_CMD:
            output = os.path.abspath(_new_ext(filename, 'ps'))
            rc = os.system("%s -f < %s > %s 2>> %s" % (
                cereconf.PRINT_DVIPS_CMD,
                dvi_file,
                output,
                logfile))
        elif cereconf.PRINT_DVIPDF_CMD:
            output = os.path.abspath(_new_ext(filename, 'pdf')),
            rc = os.system("%s %s %s 2>> %s" % (
                cereconf.PRINT_DVIPDF_CMD,
                dvi_file,
                output,
                logfile))
        else:
            logger.error(
                "Unable to prepare TeX dvi document, no command in config")
            raise IOError(
                "Unable to prepare document %r, missing config" % filename)

        if rc != 0:
            logger.warn(
                "Exit code %d when preparing dvi document %r, "
                "see %s for details", rc, dvi_file, logfile)
        if not output or not os.path.isfile(output):
            raise IOError("Error preparing document %r, "
                          "see %s for details" % (filename, logfile))
    finally:
        os.chdir(oldpwd)

    return output
