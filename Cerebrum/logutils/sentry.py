# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
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
Sentry setup.

Configuration
-------------
See :cls:`.config.SentryConfig` and :func:`.config.setup_sentry_sdk` for
details on how :func:`.sentry_init` is usually called.

The *dsn* setting will normally be set in a `logenv` config.  The *environment*
setting will usually default to ``cereconf.ENVIRONMENT``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sentry_sdk

from sentry_sdk.integrations.argv import ArgvIntegration
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.excepthook import ExcepthookIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.stdlib import StdlibIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration


def sentry_init(dsn, environment=None):
    """
    Initialize and enable Sentry integrations

    :param str dsn:
        Connection string for a Sentry project.
    """
    # *Our* set of default integrations for Sentry.  The list mainly includes
    # the sentry-sdk default integrations, except we explicitly exclude the
    # *module interation*, which adds a lot of unneccessary context.
    integrations = [
        # provide argv context to errors:
        ArgvIntegration(),
        # flush remaining entries before exit:
        AtexitIntegration(),
        # prevent duplicates:
        DedupeIntegration(),
        # log unhandled exceptions:
        ExcepthookIntegration(),
        # flask integration, for our api
        # include error log entries:
        LoggingIntegration(),
        # add extra stdlib breadcrumbs:
        StdlibIntegration(),
        # log crashing threads:
        ThreadingIntegration(),
    ]

    # TODO: We may want to enable the FlaskIntegration, but it requries
    # *blinker*.  Do we install this just to get a little bit extra context?
    # We could also consider using the SentryWsgiMiddleware in stead?

    # TODO: We probably want to add some tags in some way or another?  One
    # useful tag to include, would be to include a main component (e.g.
    # "job-runner", "api", "task-consumer", "event-publisher", "cronjob"
    # for jobs started by the job-runner).
    # tags = []

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,

        # auto_enabling_integrations:
        #
        # If enabled, some integrations are automatically added to the Hub.
        # To prevent sensitive data being sent automatically to Sentry, we
        # hard-code and actively choose which integrations to include.
        auto_enabling_integrations=False,

        # default_integrations:
        #
        # If enabled, all default integrations are automatically added to the
        # Hub.  There is currently no way to block individual default
        # integrations, so we explicitly set up all integrations ourselves.
        #
        # This way we'll also prevent any *new* integrations from automatically
        # getting enabled after a sentry_sdk upgrade.
        default_integrations=False,
        integrations=integrations,

        # for flask and wsgi - don't include request bodies
        request_bodies="never",

        # for all modules, always exclude personally identifiable information
        send_default_pii=False,

        # don't include locals, as there may be sensitive information
        with_locals=False,
    )
