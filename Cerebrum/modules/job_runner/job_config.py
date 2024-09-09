# -*- coding: utf-8 -*-
#
# Copyright 2018-2024 University of Oslo, Norway
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
""" Job Runner job configuration. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import logging
import os

import six

from Cerebrum.utils import module as module_utils
from .times import fmt_time


DEFAULT_MODULE_NAME = 'scheduled_jobs'
DEFAULT_JOB_CLASS = 'AllJobs'

logger = logging.getLogger(__name__)


def reload_job_config(module):
    """
    Reload module.

    This is typically used to force a reload of the job config, based on the
    module path reported by the module itself.
    """
    name, filename = module.__name__, module.__file__
    logger.debug("reloading %s (name=%s, filename=%s)",
                 repr(module), repr(name), repr(filename))

    basename = os.path.splitext(filename)[0]
    py_file = basename + '.py'
    pyc_file = basename + '.pyc'
    if os.path.exists(py_file):
        filename = py_file
        # The legacy 'imp' implementation used by load_source will not read the
        # .py file if a matching .pyc file exists:
        if os.path.exists(pyc_file):
            logger.debug("removing %s to force re-read of %s",
                         repr(pyc_file), repr(py_file))
            os.unlink(pyc_file)

    # Re-import
    if os.path.exists(filename):
        # load source *will* reload the module
        module = module_utils.load_source(name, filename)
        logger.info("Re-loaded %s from %s",
                    repr(name), repr(filename))
    else:
        # Path changed?
        module = module_utils.import_item(name)
        logger.warning("Unable to re-load %s from %s",
                       repr(name), repr(filename))
    return module


def get_job_config(name):
    """ Get initial job config (e.g. from cli argument). """
    if os.path.exists(name):
        module = module_utils.load_source(DEFAULT_MODULE_NAME, name)
        logger.info("Loaded config module %s from %s",
                    repr(DEFAULT_MODULE_NAME), repr(name))
    else:
        module = module_utils.import_item(name)
        logger.info("Loaded config module %s", repr(DEFAULT_MODULE_NAME))
    return module


def pretty_jobs_parser():
    """ Get argparse parser for use in job config module. """
    parser = argparse.ArgumentParser(
        description="Show job runner config",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        '-l', '--list',
        dest='list_jobs',
        action='store_true',
        default=False,
        help="List all the jobs",
    )
    action.add_argument(
        '-v', '--list-verbose',
        dest='list_verbose',
        action='store_true',
        default=False,
        help="List jobs verbosely",
    )
    action.add_argument(
        '-s', '--show-job',
        dest='show_job',
        metavar="NAME",
        help="Show a given job %(metavar)s",
    )
    return parser


def _pretty_jobs_presenter(jobs, args):
    """
    Print a human readable presentation of a collection of jobs.

    :type jobs: class Cerebrum.modules.job_runner.job_actions.Jobs
    :param jobs:
        A class with all the jobs to present. Normally the AllJobs class in a
        given scheduled_jobs.

    :type args: argparse.Namespace
    :param args: Options on what to print (result of pretty_jobs_parser).
    """
    if args.list_jobs:
        for name in sorted(jobs.get_jobs()):
            print(name)

    elif args.show_job:
        jobname = args.show_job
        try:
            job = jobs.get_jobs()[jobname]
        except KeyError:
            print("No such job: %s" % repr(jobname))
            return
        print("Command: %s" % job.get_pretty_cmd())
        print("Pre-jobs: %s" % job.pre)
        print("Post-jobs: %s" % job.post)
        print("Non-concurrent jobs: %s" % job.nonconcurrent)
        print("When: %s, max-freq: %s" % (job.when, job.max_freq))

    elif getattr(args, 'dump', False):
        # dumplevel = args[args.index('--dump') + 1]
        raise NotImplementedError("not implemented yet...")

    elif args.list_verbose:
        for name, job in sorted(six.iteritems(jobs.get_jobs())):
            print("Job: %s:" % name)
            print("  Command: %s" % job.get_pretty_cmd())
            if job.pre:
                print("  Pre-jobs: %s" % job.pre)
            if job.post:
                print("  Post-jobs: %s" % job.post)
            if job.nonconcurrent:
                print("  Non-concurrent jobs: %s" % job.nonconcurrent)
            print("  When: %s, max-freq: %s" % (job.when, job.max_freq))

    else:
        print("%d jobs defined" % len(jobs.get_jobs()))


def pretty_jobs_presenter(jobs, args):
    """
    Entry point for providing cli-arguments in job config modules.
    """
    args = pretty_jobs_parser().parse_args(args)
    return _pretty_jobs_presenter(jobs, args)


def dump_jobs(scheduled_jobs, details=0):
    """ The job_runner implementation of --dump-jobs. """
    jobs = scheduled_jobs.get_jobs()
    shown = {}

    def dump(name, indent):
        info = []
        if details > 0:
            if jobs[name].when:
                info.append(six.text_type(jobs[name].when))
        if details > 1:
            if jobs[name].max_freq:
                info.append(
                    "max_freq=%s" % fmt_time(jobs[name].max_freq, local=False))
        if details > 2:
            if jobs[name].pre:
                info.append("pre=%s" % repr(jobs[name].pre))
            if jobs[name].post:
                info.append("post=%s" % repr(jobs[name].post))
        print("%-40s %s" % ("   " * indent + name, ", ".join(info)))
        shown[name] = True
        for k in jobs[name].pre or ():
            dump(k, indent + 2)
        for k in jobs[name].post or ():
            dump(k, indent + 2)
    keys = sorted(jobs.keys())
    for k in keys:
        if jobs[k].when is None:
            continue
        dump(k, 0)

    remaining = ["  %s" % k for k in keys if k not in shown]
    print("Never run:", "\n".join(remaining), sep="\n")


# python -m Cerebrum.modules.job_runner.job_config

def main(args=None):
    parser = pretty_jobs_parser()
    parser.add_argument(
        '--config',
        dest='config',
        metavar='NAME',
        default=DEFAULT_MODULE_NAME,
        help='A python module (or file) with jobs',
    )
    parser.add_argument(
        '--jobs',
        dest='config_attr',
        default=DEFAULT_JOB_CLASS,
        help="The config attribute that contains jobs",
    )

    args = parser.parse_args(args)
    config = get_job_config(args.config)
    all_jobs = getattr(config, args.config_attr)
    _pretty_jobs_presenter(all_jobs(), args)


if __name__ == '__main__':
    main()
