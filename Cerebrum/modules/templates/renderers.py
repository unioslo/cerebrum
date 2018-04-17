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
from __future__ import unicode_literals, absolute_import
import os
import io
from subprocess import Popen

from .env import (create_environment,
                  format_template_name,
                  get_template,
                  fetch_static_files)


def render(config, template, values, lang=None):
    """
    Render a template with the passed values.
    """
    env = create_environment(config)
    if lang is not None:
        tmpl_name = format_template_name(template, lang)
    else:
        tmpl_name = template

    tmpl = get_template(env, tmpl_name)
    return tmpl.render(**values)


def render_pdf(config, src, dest):
    """
    Render a PDF from an already existing HTML-file.
    As we have no internal web-service to handle map src/href-references more
    intelligently, all files referenced within the HTML-file must be present
    in the same folder.

    @param config: TemplatesConfig-object/dict built by create_template_config.
    @param src: absolute path to a HTML-file.
    @param dest: absolute path to the PDF-file to render.
    """
    Popen(
        config['render_pdf_cmd'].format(src=src, dest=dest), shell=True
    ).wait()


def render_barcode(config, number, dest):
    """
    Render a barcode image in PNG-format from a number.

    @param config: TemplatesConfig-object/dict built by create_template_config.
    @param number: int number used to generate the barcode.
    @param dest: absolute path to the PNG-file to render.
    """
    Popen(
        config['render_barcode_cmd'].format(number=number, dest=dest),
        shell=True
    ).wait()


def render_to_file(config, file_path, template_name, tmpl_vars, lang=None):
    """
    Renders a template into a file.
    When rendering a HTML-based template that relies on the presence of
    static files, use render_html_to_file instead.

    @param config: TemplatesConfig-object/dict built by create_template_config.
    @param file_path: absolute path to file.
    @param template_name: name of the template.
    @param tmpl_vars: dict of vars to be used when rendering template.
    @param lang: language code to use if template has
           language-specific versions, eg. "en"/"no".
    @return: absolute file path of the output file.
    """
    rendered_template = render(config, template_name, tmpl_vars, lang)
    with io.open(file_path, 'w') as f:
        f.write(rendered_template)
    return file_path


def render_html_to_file(config, folder, template_name, tmpl_vars,
                        lang=None, static_files=[]):
    """
    Renders a HTML-based template, along with the required static files,
    into a folder.

    @param config: TemplatesConfig-object/dict built by create_template_config.
    @param folder: The folder to generate html and static files.
    @param template_name: Name of the template.
    @param tmpl_vars: Dict of vars to be used when rendering template.
    @param lang: Language code to use if template has
           language-specific versions, eg. "en"/"no".
    @param static_files: List of required static files to copy.
    @return:
    """
    file_path = os.path.join(folder, template_name)
    rendered_html_file = render_to_file(
        config, file_path, template_name, tmpl_vars, lang
    )
    fetch_static_files(config, folder, static_files)
    return rendered_html_file


def html_template_to_pdf(config, folder, template_name, tmpl_vars,
                         lang=None, static_files=[], pdf_abspath=None):
    """
    @param config: TemplatesConfig-object/dict built by create_template_config.
    @param folder: The folder to generate html and static files.
    @param template_name: Name of the template.
    @param tmpl_vars: Dict of vars to be used when rendering template.
    @param lang: Language code to use if template has
           language-specific versions, eg. "en"/"no".
    @param static_files: List of required static files to copy.
    @param pdf_abspath: Path to pdf file.
    @return: Path to pdf file. If pdf_abspath is None, this will be placed
             inside the passed folder path.
    """
    html_file_path = render_html_to_file(
        config, folder, template_name, tmpl_vars, lang, static_files
    )
    if pdf_abspath is None:
        pdf_file_path = os.path.join(folder, 'output.pdf')
    else:
        pdf_file_path = pdf_abspath
        render_pdf(config, html_file_path, pdf_file_path)
    return pdf_file_path
