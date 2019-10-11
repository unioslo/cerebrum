#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gunicorn wrapper script for properly configuring logging.

This script sets up logging using ``Cerebrum.logutils`` and logging ipc using
``Cerebrum.logutils.mp``.

..note::
    gunicorn insists on handling the gunicorn.access and gunicorn.error logs by
    itself to some degree.

    Ideally, gunicorn should be configured with:

    - ``accesslog = '-'`` (log to stdout, option --access-logfile)
    - ``errorlog = ''``  (log to stderr, option --error-logfile)

    And logging configured so that:

    - gunicorn.access has no handlers and *doesn't* propagate
    - gunicorn.error has no handlers and *does* propagate

.. warning::
    No matter how gunicorn.access is configured - nothing will be logged to
    this logger unless the gunicorn config enables the access log (e.g. by
    setting ``accesslog``)
"""
from __future__ import absolute_import, unicode_literals, print_function

import logging
from collections import Mapping
from multiprocessing import JoinableQueue as Queue

from gunicorn.app.wsgiapp import WSGIApplication

import Cerebrum.logutils
from Cerebrum.logutils import mp


def store_logger_params(logger, *attrs):
    """ Store supported settings """
    params = {}
    for attr in set(attrs):
        if attr == 'level':
            params['level'] = logger.level
        elif attr == 'propagate':
            params['propagate'] = logger.propagate
        elif attr == 'handlers':
            params['handlers'] = logger.handlers[:]
        else:
            raise ValueError('Unsupported attr %r' % (attr,))
    return params


def apply_logger_params(logger, params):
    if 'level' in params:
        logger.setLevel(params.pop('level'))
    if 'propagate' in params:
        logger.propagate = params.pop('propagate')
    for handler in params.pop('handlers', ()):
        logger.addHandler(handler)
    if params:
        raise ValueError('Unknown logger params %r', tuple(sorted(params)))


class LogManager(object):
    """ Namespace for configuring logging internals. """

    poll_timeout = 0.5
    join_timeout = 1.5
    monitor_interval = 60

    def __init__(self):
        serializer = mp.protocol.JsonSerializer()
        protocol = mp.protocol.LogRecordProtocol(serializer)
        self.log_queue = Queue()
        self.log_channel = mp.channel.QueueChannel(self.log_queue, protocol)

        self.thread_log = mp.threads.LogRecordThread(
            self.log_channel,
            timeout=self.poll_timeout)

        self.thread_mon = mp.threads.QueueMonitorThread(
            self.log_queue,
            interval=self.monitor_interval)

        # Store the initial settings for propagate, level
        self.init_access = store_logger_params(
            logging.getLogger('gunicorn.access'), 'propagate', 'level')
        self.init_error = store_logger_params(
            logging.getLogger('gunicorn.error'), 'propagate', 'level')

    def reset_gunicorn_loggers(self):
        """ Restore initial logger settings in worker processes """
        apply_logger_params(logging.getLogger('gunicorn.access'),
                            self.init_access)
        apply_logger_params(logging.getLogger('gunicorn.error'),
                            self.init_error)

    def start_threads(self):
        """ Start logger threads. """
        if not self.thread_log.is_alive():
            self.thread_log.start()
        if not self.thread_mon.is_alive():
            self.thread_mon.start()

    def stop_threads(self):
        """ Stop logger threads. """
        self.thread_mon.stop()
        self.thread_log.stop()
        if self.thread_mon.is_alive():
            self.thread_mon.join(self.join_timeout)
        if self.thread_log.is_alive():
            self.thread_log.join(self.join_timeout)


class Event(object):

    def __init__(self, name):
        self.name = name
        self.callbacks = []

    def __call__(self, *args):
        for callback in self.callbacks:
            callback(*args)


class WrapperHooks(Mapping):
    """ Inventory of event hooks for gunicorn (event -> callback).  """

    def __init__(self):
        self._events = dict()

    def __getitem__(self, key):
        return self._events[key]

    def __iter__(self):
        return iter(self._events)

    def __len__(self):
        return len(self._events)

    def __call__(self, event):
        def wrapper(fn):
            if event in self._events:
                raise KeyError(
                    "Hook for event={0!r} already registered".format(event))
            self._events[event] = fn
            return fn
        return wrapper

    def wrap_hooks(self, config, params):
        """
        Apply hooks to gunicorn config.

        :param config: gunicorn config object.
        """
        for event, wrapper in self.items():
            hook = wrapper(getattr(config, event), params)
            config.set(event, hook)


def configure_worker_logging(channel):
    # preserve access logger state
    access_log = store_logger_params(logging.getLogger('gunicorn.access'),
                                     'propagate', 'level', 'handlers')

    mp.utils.reset_logging()
    root = logging.getLogger()
    root.addHandler(mp.handlers.ChannelHandler(channel))

    # restore access logger state
    apply_logger_params(logging.getLogger('gunicorn.access'), access_log)


sync_hooks = WrapperHooks()


@sync_hooks('on_starting')
def on_starting_wrapper(real_hook, mgr):
    """ Called just before the master process is initialized. """
    def hook(server):
        mgr.start_threads()
        real_hook(server)
    return hook


@sync_hooks('on_exit')
def on_exit_wrapper(real_hook, mgr):
    """ Called just before exiting Gunicorn. """
    def hook(server):
        mgr.stop_threads()
        real_hook(server)
    return hook


@sync_hooks('post_fork')
def post_fork_wrapper(real_hook, mgr):
    """ Called just after a worker has been forked. """
    def hook(server, worker):
        configure_worker_logging(mgr.log_channel)
        real_hook(server, worker)
    return hook


@sync_hooks('when_ready')
def when_ready_wrapper(real_hook, mgr):
    """ Called just after the server is started. """
    def hook(server):
        mgr.reset_gunicorn_loggers()
        real_hook(server)
    return hook


worker_class_hooks = {
    'SyncWorker': sync_hooks,
}


class LoggingApplication(WSGIApplication):
    """ Inject logger hooks into the gunicorn WSGIApplication.  """

    def __init__(self, *args, **kwargs):
        self.log_manager = kwargs.pop('log_manager')
        super(LoggingApplication, self).__init__(*args, **kwargs)

    def load_config(self):
        super(LoggingApplication, self).load_config()
        hooks = worker_class_hooks.get(self.cfg.worker_class.__name__)
        if hasattr(hooks, 'wrap_hooks'):
            getattr(hooks, 'wrap_hooks')(self.cfg, self.log_manager)


def main():
    """Start Gunicorn with Cerebrum-logging and a generic WSGI application."""
    try:
        Cerebrum.logutils.autoconf('gunicorn', None)
        mgr = LogManager()
        app = LoggingApplication("%(prog)s [OPTIONS] [APP_MODULE]",
                                 log_manager=mgr)
        app.run()
    except SystemExit:
        # If the app fails to start up, we may never get an on_exit signal, so
        # we'll have to make sure to stop the threads here.
        mgr.stop_threads()
        raise


if __name__ == '__main__':
    main()
