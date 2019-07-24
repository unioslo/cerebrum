#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""Creates a report of all the jobs defined in scheduled jobs in .rst format

Runs through all jobs defined in scheduled jobs, fetches the command and
parameters of the job, and looks up the docstring of the script if it is a .py
file.

"""
from __future__ import unicode_literals

import argparse

from Cerebrum.modules.job_runner.job_config import get_job_config


def get_module_docstring(filepath):
    """Get module-level docstring of Python module at filepath.

    e.g. 'path/to/file.py'.
    """
    co = compile(open(filepath).read(), filepath, 'exec')
    if co.co_consts and isinstance(co.co_consts[0], basestring):
        docstring = co.co_consts[0]
    else:
        docstring = None
    return docstring


def create_job_info(job, job_name, docstring=None):
    """Creates an entry ready to be printed to file for a given job

    :param job:
    :param job_name:
    :param docstring:
    :return:
    """
    output = job_name + '\n' + '-'*len(job_name)
    output += '\n\n| Command: ' + job.call.cmd
    output += '\n| Params: ' + ' '.join(job.call.params).replace('*', '\\*')
    output += '\n'*2 + '::\n'
    if docstring is not None:
        output += ' ' + docstring.replace('\n', '\n ')
    else:
        output += ' Module has no docstring'
    output += '\n\n| When/Freq: ' + str(job.when)
    output += '\n| Pre: ' + ', '.join(job.pre) or 'None'
    output += '\n| Post: ' + ', '.join(job.post) or 'None'
    output += '\n'*2
    return output


def write_to_file(filename, all_jobs):
    """Write to file

    :param str filename: the filename of the file to write to
    :param basestring all_jobs: an enormous string of correctly formatted rst
    :return: None
    """
    with open(filename, mode='w') as fh:
        fh.write(all_jobs.encode('utf-8'))


def title(text):
    """Creates a title string in rst format given a title

    :param basestring text: the title string
    :return: string in rst title format
    """
    return text + '\n' + '=' * len(text) + '\n'*2


def generate_output(jobs):
    """Builds the output file from a list of jobs

    :param list jobs: List of strings, one for each job
    :return str: The string of correctly formatted rst ready to be written to
     file
    """
    output = title("Job Runner Jobs")
    output += ("This is an overview of the currently defined jobs in "
               "scheduled jobs.py, which files they run with which "
               "parameters, and the docstring of that script if it is a "
               "python file. We also include then when/freq, pre, and post "
               "arguments for each job. "
               "Beware that not all scripts have docstrings, and as such "
               "there is no information to automatically gather for that "
               "script. If you would like to remedy this feel free to write "
               "one for any scripts you find.")
    output += '\n'*2
    for job in jobs:
        output += job
    return output


def main(inargs=None):
    """Parses arguments and writes the jobs to file

    :param inargs:
    :return:
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-f', '--filename',
                        dest='filename',
                        help='Filename of report file',
                        required=True,
                        )
    args = parser.parse_args(inargs)

    config = get_job_config('scheduled_jobs')
    jobs = config.get_jobs()
    all_jobs = []

    for job_name, job in jobs.items():
        command = job.call.cmd
        # Don't look for docstrings in non python files
        if command.endswith('.py'):
            docstring = get_module_docstring(command)
        else:
            docstring = 'Non python file\n'
        all_jobs.append(create_job_info(job, job_name, docstring))
    output = generate_output(all_jobs)
    write_to_file(args.filename, output)


if __name__ == '__main__':
    main()
