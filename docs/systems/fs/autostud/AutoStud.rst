===============================
Student management in Cerebrum
===============================

.. admonition:: Needs review

   This is an old document, some of the instructions may be out of date.


Technical details
==================
Most of the routines for automatic student management in Cerebrum
are handled by ``Cerebrum.modules.no.uio.AutoStud``.  Typical usage is
something like:
::

    def process_students_callback(person_info):
        # Handle student data
        profile = autostud.get_profile(person_info)
        logger.debug("disk: %s" % profile.get_disk())
        …

    def main():
        …
        autostud = AutoStud.AutoStud(
            db,
            logger,
            debug=debug,
            cfg_file=studconfig_file,
            studieprogs_file=studieprogs_file,
            …
        )
        autostud.start_student_callbacks(
            student_info_file,
            process_students_callback,
        )


``cfg_file``
    The AutoStud ``cfg_file`` is an XML file that contains rules for all the
    various types of student accounts.  See ``design/studconfig.dtd`` for more
    details on the config file format.

``studieprogs_file``
    The AUtoStud ``studieprogs_file`` is an XML file describing the various
    study programs (studieprogrammer).


``student_info_file``
    The ``student_info_file`` used with ``AutoStud.start_student_callbacks`` is
    an XML file that describes all students, student roles, and student
    properties.  It is typically called ``merged_persons.xml``, and is merged
    from multiple other XML files with student data from FS.


 * ``AutoStud.AutoStud`` is the main class, and is normally the only
   one you would initialize.
 * ``Util.ProgressReporter`` is an alternative to ``logging.py``, and
   should probably be replaced by that module.
 * ``Util.LookupHelper`` contains various helper functions for
   DB-lookup
 * ``ProfileConfig.Config`` parses the ``studconfig.xml`` file and
   stores it internaly
 * ``ProfileConfig.ProfileDefinition`` internal class that stores data
   about a spesific profile
 * ``ProfileConfig.StudconfigParser`` is the actual XML parser for the
   ``studconfig.xml`` file.
 * ``ProfileHandler.Profile`` contains logic that expands the actual
   profile matches to the disk, groups etc. that a user should have.
 * ``Studentinfo.StudentInfoParser`` is a XML parser for the
   ``merged_persons.xml`` file.
 * ``Studentinfo.StudieprogDefParser`` is a XML parser for the file
   with "studieprogrammer".

The figure belo shows a schematic view of the classes (should be UML,
but the author is no UML expert).  It should give you a rough idea
about where things are implemeted.

.. _class_overview :

Figure: Class overview

.. image:: figures/AutoStud.png


Studconfig.xml file
====================
The file ``studconfig.xml`` controls how the automated student
maintenance is performed.  It defines a list of profiles containing
attributes for accounts as well as select criterias reuired to match
the profile.

`Example <autoconfig-student-eksempel.xml>`_

After editing ``studconfig.xml``, you should validate it against
``studconfig.dtd``.  This can be done with the
``contrib/fs/validate-studconfig.py`` script.
