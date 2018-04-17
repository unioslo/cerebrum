#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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

from __future__ import absolute_import, unicode_literals

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration)
from Cerebrum.config.settings import String, Iterable, Setting
from Cerebrum.config import loader
from six import text_type

DEFAULT_TEMPLATES_CONFIG = 'templates'

DEFAULT_RENDER_PDF_CMD = '/usr/bin/chromium-browser --headless --no-margins' \
                         '--disable-gpu --print-to-pdf={dest} file://{src}'

DEFAULT_RENDER_BARCODE_CMD = '/usr/bin/barcode -e EAN -E -n -b {number:012d}' \
                             ' | /usr/bin/convert - {dest}'


class TemplateEntry(Setting):
    _valid_types = (dict, )

    def validate(self, value):
        required_keys = ['file']
        for key in required_keys:
            if value.get(key) is None:
                raise TypeError(
                    'Settings {} requires the following keys: {}'.format(
                        self.__class__, required_keys
                    )
                )

        # Optional Keys
        if value.get('desc') is not None:
            if not isinstance(value['desc'], (str, text_type)):
                raise TypeError(
                    'Key "desc" in TemplateEntry must be a string.'
                )

        if value.get('static_files') is not None:
            error = ('Key "static_files" in TemplateEntry '
                     'must be a list of strings.')
            if not isinstance(value['static_files'], list):
                raise TypeError(error)
            for entry in value['static_files']:
                if not (isinstance(entry, (str, text_type))):
                    raise TypeError(error)

        if value.get('type') is not None:
            if not isinstance(value['type'], (str, text_type)):
                raise TypeError(
                    'Key "type" in TemplateEntry must be a string.'
                )
        return True


class TemplatesConfig(Configuration):
    """ Configures how to process named logging setup. """

    template_folders = ConfigDescriptor(
        Iterable,
        default=['/cerebrum/etc/base-templates',
                 '/cerebrum/etc/templates'],
        doc="Folders containing templates files")

    render_pdf_cmd = ConfigDescriptor(
        String,
        default=DEFAULT_RENDER_PDF_CMD,
        doc="Command for rendering PDF-files")

    render_barcode_cmd = ConfigDescriptor(
        String,
        default=DEFAULT_RENDER_BARCODE_CMD,
        doc="Command for rendering barcode images")

    static_prefix = ConfigDescriptor(
        String,
        default='',
        doc="Prefix to inject for static file references in HTML templates")

    print_password_templates = ConfigDescriptor(
        Iterable,
        template=TemplateEntry(),
        default=[],
        doc="List of templates to be used for printing passwords from BOFH."
    )

    process_students_templates = ConfigDescriptor(
        Iterable,
        template=TemplateEntry(),
        default=[],
        doc="List of templates to be used by process_students.py"
    )


def get_config(config_file=None, namespace=DEFAULT_TEMPLATES_CONFIG):
    """ Autoload a TemplatesConfig config file.

    :param str config_file:
        Read the logging configuration from this file.
    :param str namespace:
        If no `config_file` is given, look for a config with this basename in
        the configuration directory.

    :return TemplatesConfig:
        Returns a configuration object.
    """
    templates_config = TemplatesConfig()

    if config_file:
        templates_config.load_dict(loader.read_config(config_file))
    else:
        loader.read(templates_config, root_ns=namespace)
    return templates_config


config = get_config()
