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
from __future__ import unicode_literals
import os
import shutil
from os.path import isfile, join

from jinja2 import (Environment,
                    FileSystemLoader,
                    StrictUndefined,
                    nodes)
from jinja2.ext import Extension


class StylesExtension(Extension):
    # a set of names that trigger the extension.
    tags = set(['styles'])

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        args = [parser.parse_expression()]
        return nodes.CallBlock(
            self.call_method('_inject_styles', args),
            [], [], []
        ).set_lineno(lineno)

    def _inject_styles(self, file_name, caller):
        styles = self.environment.get_template(file_name).render()
        return ''.join(['<style>', styles, '</style>'])


def create_template_config(tmpl_folders,
                           render_pdf_cmd=None,
                           render_barcode_cmd=None,
                           static_prefix=''):
    return {
        'template_folders': tmpl_folders,
        'render_pdf_cmd': render_pdf_cmd,
        'render_barcode_cmd': render_barcode_cmd,
        'static_prefix': static_prefix
    }


def create_environment(config):
    env = Environment(
        loader=FileSystemLoader(config['template_folders']),
        extensions=[StylesExtension],
        undefined=StrictUndefined,
        autoescape=True
    )
    env.globals['static_prefix'] = config['static_prefix']
    return env


def get_static_file_path(env, filename):
    for path in env.loader.searchpath:
        abs_path = join(path, filename)
        if isfile(abs_path):
            return abs_path
    raise IOError('File not found: {}'.format(filename))


def fetch_static_files(config, folder, static_files):
    env = create_environment(config)
    for f in static_files:
        file_path = get_static_file_path(env, f)
        shutil.copyfile(file_path, os.path.join(folder, f))


def format_template_name(name, lang):
    """ Format localized template name

    >>> format_template_name('foo', 'en')
    foo.en
    >>> format_template_name('foo.txt', 'en')
    foo.en.txt
    >>> format_template_name('foo.bar.txt', 'en')
    foo.bar.en.txt

    :param str name: A template name
    :param lang: A language tag, ie. 'en'

    :return str: A localized template name
    """
    if lang is not None:
        base, ext = os.path.splitext(name)
        return "{base!s}.{lang!s}{ext!s}".format(
            base=base, lang=lang, ext=ext)
    return name


def get_template(env, template, lang=None):
    template_name = format_template_name(template, lang)
    return env.get_template(template_name)
