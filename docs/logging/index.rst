=======================
Logging and monitoring
=======================

Logging
========
All Cerebrum code should use the stdlib ``logging`` module, and global module
logger objects.

Cerebrum code uses :doc:`logutils` to configure these loggers.  See
:doc:`how-to` for more info.


Monitoring
===========
Cerebrum has some support for monitoring, with support for generating a Zabbix
discovery report.  See :doc:`/job-runner/health-check` for details on this.

Other monitoring of individual processes/daemons should be set up outside of
Cerebrum.


Metrics
========
Cerebrum includes a ``statsd`` client, and will publish basic stats from
:doc:`/bofhd/index` and the API if configured.

See ``Cerebrum.modules.statsd`` for more details.


Documents
=========

.. toctree::
   :maxdepth: 1
   :glob:

   *
