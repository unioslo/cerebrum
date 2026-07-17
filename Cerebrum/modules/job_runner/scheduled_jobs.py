# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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
"""
Example job config.

This is an example of scheduling settings that can be used in a
cerebrum installation.  See the documentation for job_runner for
details.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import sys

from Cerebrum.utils.date import to_seconds
from Cerebrum.modules.job_runner.job_actions import Action, Jobs, System
from Cerebrum.modules.job_runner.job_config import pretty_jobs_presenter
from Cerebrum.modules.job_runner.times import When, Time

sbin = os.path.join(sys.prefix, "sbin")
cache = os.path.join(sys.prefix, "var/cache")
ypsrc = os.path.join(cache, "yp/src")


class AllJobs(Jobs):

    # Employee imports

    import_from_lt = Action(
        call=System(
            os.path.join(sbin, "import_from_LT.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=6),
    )
    import_ou = Action(
        pre=["import_from_lt"],
        call=System(
            os.path.join(sbin, "import_OU.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=6),
    )
    import_lt = Action(
        pre=["import_ou", "import_from_lt"],
        call=System(
            os.path.join(sbin, "import_LT.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=6),
    )

    # student imports

    import_from_fs = Action(
        call=System(
            os.path.join(sbin, "import_from_FS.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=6),
    )
    import_fs = Action(
        pre=["import_from_fs"],
        call=System(
            os.path.join(sbin, "import_FS.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=6),
    )
    process_students = Action(
        pre=["import_fs"],
        call=System(
            os.path.join(sbin, "process_students.py"),
            params=[],
        ),
        max_freq=to_seconds(minutes=5),
    )

    # daily import triggers

    daily = Action(
        pre=["import_lt", "import_fs", "process_students"],
        call=None,
        when=When(time=[Time(min=[10], hour=[1])]),
        post=["backup", "rotate_logs"],
    )

    backup = Action(
        call=System(
            os.path.join(sbin, "backup.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=23),
    )
    rotate_logs = Action(
        call=System(
            os.path.join(sbin, "rotate_logs.py"),
            params=[],
        ),
        max_freq=to_seconds(hours=23),
    )

    # exports

    generate_passwd = Action(
        call=System(
            os.path.join(sbin, "generate_nismaps.py"),
            params=[
                "--user_spread", "NIS_user@uio",
                "-p", os.path.join(ypsrc, "passwd"),
            ]
        ),
        max_freq=to_seconds(minutes=5),
    )
    generate_group = Action(
        call=System(
            os.path.join(sbin, "generate_nismaps.py"),
            params=[
                "--group_spread", "NIS_fg@ifi",
                "-g", os.path.join(ypsrc, "group"),
            ]
        ),
        max_freq=to_seconds(minutes=15),
    )
    convert_ypmap = Action(
        call=System(
            "make",
            params=["-s", "-C", "/var/yp"],
            stdout_ok=1,
        ),
        multi_ok=1,
    )
    dist_passwords = Action(
        pre=["generate_passwd", "convert_ypmap"],
        call=System(
            os.path.join(sbin, "passdist.pl"),
        ),
        max_freq=to_seconds(minutes=5),
        when=When(freq=to_seconds(minutes=10)),
    )
    dist_groups = Action(
        pre=["generate_group", "convert_ypmap"],
        call=System(
            os.path.join(sbin, "passdist.pl"),
        ),
        max_freq=to_seconds(minutes=5),
        when=When(freq=to_seconds(minutes=30)),
    )


def get_jobs():
    alljobs = AllJobs()
    return alljobs.get_jobs()


if __name__ == "__main__":
    pretty_jobs_presenter(AllJobs(), sys.argv[1:])
