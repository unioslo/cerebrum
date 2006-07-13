#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

# $Id$

import sys
import os
import logging
import shutil
import pwd
import grp

__doc__ = """Contains the basic elements of the Cerebrum installation framework.

"""

__version__ = "$Revision$"
# $Source$


class CerebrumInstallationError(Exception):
    
    """Raised when an error occurs during installation."""


    
class InstallationQueueController(object):

    """Controls the queue containing the installation modules.

    Makes sure to check that prerequisites are installed before
    handing over modules to the main installation controller.

    """

    def __init__(self, initial_queue):
        """Initializes queue controller."""
        logging.debug("Setting up installation queue controller")
        self.installed_modules = []
        self.waiting_for_prereqs = []
        self.installation_queue = []
        self.module_by_name = {}

        for module_name in initial_queue:
            self.add_to_queue(module_name)


    def load_installation_module(self, module_identifier):
        """Dynamically loads module for use by installation.
        
        Also checks to see that it is in fact an installation module.

        @param module_identifier: Name of module to load.
            Needs to be formatted a la 'Modulegroup:Module'.
        @type module_identifier: String

        @raise CerebrumInstallationError: If unable to instantiate an
            object of the specified class or if the instantiated object
            isn't a CerebrumInstallationModule.
        
        """
        python_module_string, install_class_string = module_identifier.split(':')
        logging.debug("Will attempt to load class '%s' from module '%s'"
                      % (install_class_string, python_module_string))
        try:
            python_module = __import__(python_module_string)
            install_object = object.__new__(python_module.__dict__[install_class_string])
            install_object.__init__(self)
            logging.debug("Successfully loaded class '%s'" % install_object)
        except ImportError, importerror:
            raise CerebrumInstallationError("Unable to load '%s': %s"
                                            % (module_identifier, importerror))

        if not isinstance(install_object, CerebrumInstallationModule):
            raise CerebrumInstallationError("'%s' is not a CerebrumInstallationModule"
                                            % str(install_object))
    
        return install_object


    def queue_is_not_empty(self):
        """Checks whether or not the installation queue is empty or not.

        @return: True if more elements in queue, False if not.

        """       
        return self.installation_queue


    def get_next_module(self):
        """Returns the next module in the queue, after verifying that
        any and all prerequisites have been installed.

        @return: CerebrumInstallationModule that is next in line for installation.

        """       
        while self.queue_is_not_empty():
            candidate_name = self.installation_queue.pop(0)
            candidate = self.module_by_name[candidate_name]
            if candidate.check_module_dependencies():
                logging.debug("All dependicies in place for '%s' - ready to install" % candidate)
                return candidate
            else:
                logging.debug("All dependicies NOT in place for '%s' - postponing" % candidate)
                self.waiting_for_prereqs.append(str(candidate))
                

    def commit(self, installed_module):
        """Adds given module to list of successfully installed modules.

        Checks the list of modules waiting for prereqs to be installed
        to see if 'installed_module' was the last module they were
        waiting for to become eligible for installation.

        @param installed_module: The module that has been successfully installed.
        @type installed_module: CerebrumInstallationModule

        """
        self.installed_modules.append(str(installed_module))
        logging.info("Installation of '%s' considered complete and successful" % installed_module)

        # Iterate over all modules waiting for prereqs to see if
        # 'installed_module' was the last one they waited for.
        for module_name in self.waiting_for_prereqs:
            module = self.module_by_name[module_name]
            if module.check_module_dependencies():
                self.installation_queue.append(module_name)
                self.waiting_for_prereqs.remove(module_name)


    def add_to_queue(self, name_of_module_to_queue):
        """Adds given module to installation queue if it isn't already there.

        Also makes sure that the object belonging to/represented by
        the module is loaded and cached by this queue-controller.

        @param name_of_module_to_queue: Name of the module that is to be queued.
        @type name_of_module_to_queue: String

        @return: Nothing

        @raise CerebrumInstallationError: If trying to queue an already installed module.

        """
        logging.debug("Adding module '%s' to installation queue" % name_of_module_to_queue)
        
        if not name_of_module_to_queue in self.module_by_name:
            module_to_queue = self.load_installation_module(name_of_module_to_queue)
            self.module_by_name[name_of_module_to_queue] = module_to_queue            
        
        if name_of_module_to_queue in self.installed_modules:
            # Why are we queuing when module is already installed?
            raise CerebrumInstallationError("Trying to queue module '%s', but it is already installed",
                                            name_of_module_to_queue)
        
        if name_of_module_to_queue not in self.installation_queue:
            logging.debug("Adding '%s' to installation queue", name_of_module_to_queue)
            self.installation_queue.append(name_of_module_to_queue)



class CerebrumInstallationModule(object):

    """Root class for Cerebrum installation modules.

    Installation modules should be represented by a subclass of this.

    """    

    def __init__(self, installation_queue_controller):
        """Initializes module by linking to other parts of the
        installation system.

        """
        self.installation_queue_controller = installation_queue_controller
        self.prerequisite_modules = []
      

    def __str__(self):
        """String representation of this module's 'qualified' name, i.e. 'module:class'"""
        return "Framework:CerebrumInstallationModule"


    def install(self):
        """Runs installation.

        Should return 'True' if install successful; 'False' otherwise.

        Must be implemented by subclasses.

        """
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    
    def check_module_dependencies(self):
        """Checks to see if modules this module depend on have been
        installed properly.

        Any prerequisites found to be not installed are added to the
        installation queue.

        @return: True if all modules in this module's list of
            prerequisites have been installed, False otherwise.

        """

        # We'll consider everything is in place til proven otherwise
        all_dependencies_in_place = True
        
        for prereq in self.prerequisite_modules:
            if prereq not in self.installation_queue_controller.installed_modules:
                # "Otherwise" got proven. Continue iterating so we
                # make sure all prereqs are queued.
                self.installation_queue_controller.add_to_queue(prereq)
                all_dependencies_in_place = False
            
        return all_dependencies_in_place



class CerebrumInstallationData(object):

    """Borg that handles information that should be consistent
    throughout the installation.

    """

    __shared_state = {}
    initialized = False

    def __init__(self):
        self.__dict__ = self.__shared_state
        if not self.initialized:
            # This is the first member of the Borg; set up variables
            self.data = {}

        self.initialized = True


    def __setitem__(self, key, value):
        self.data[key] = value


    def __getitem__(self, key):
        try:
            return self.data[key]
        except KeyError:
            return None


    def __iter__(self):
        return iter(self.data)


    def __contains__(self, element):
        return element in self.data



def ask_user(info=None, question=None, default="", env=None):
    """Gets input from user.

    If the user gives no value (e.g. by simply pressing return), then
    the value given as 'default' will be returned. The user is
    informed about this value in square brackets immediately after the
    question itself.

    If 'env' is given, and there exists a value for 'env' in
    CerebrumInstallationData, that value will override the default
    given as a parameter, both in the question asked and in the value
    returned upon no user input.

    If 'info' is given, it is formatted into nicely lengthed lines;
    'question' (if lengthy), isn't.

    @param info: Information about the question asked, given to user
      before the question is asked. Optional.
    @type info: String
    
    @param question: The question itself. Mandatory.
    @type question: String
    
    @param default: Default answer for the question asked.
    @type default: String
    
    @param env: If given, the corresponding data-value will be used as
      'default'-value, rather than the one given by the
      'default'-parameter.    
    @type env: String
    
    @return: Input from user. If no input, the default is returned, as
      per 'default'/'env' above.

    @raise CerebrumInstallationError: If 'question' isn't given.

    """
    if question is None:
        raise CerebrumInstallationError("Trying to ask something silently. Not good.")
    
    installation_data = CerebrumInstallationData()

    if info is not None:
        print
        max_width = 77
        while len(info) > max_width:
            # Break string into suitable width pieces
            last_space = info.rindex(" ", 0, max_width)
            print info[:last_space]
            info = info[last_space+1:] # +1 to strip 'space'
        print info
        print

    if env is not None:
        if env in installation_data:
            default = installation_data[env]

    print "   %s [%s]: " % (question, default),

    if installation_data["batch"]:
        print "%s\n" % default
        return default
    else:
        value = sys.stdin.readline()
        returnvalue = value.splitlines()[0]  # Strip end-of-line characters

    print

    if len(returnvalue) > 0: 
        return returnvalue
    else:
        return default



def check_python_library(module=None, component=None):
    """Check to see if given module (and possibly a given component of
    that module) is properly installed and made available.

    @param module: The module we wish to check for. Required.
    @type module: String

    @param component: If given, the sub-parts of 'module' that we
        wish to check for. Can be a comma-seperated list. Optional.
    @type component: String

    @return: True if all is OK

    @raise CerebrumInstallationError: If the module/component is not available

    """
    if module is None:
        raise CerebrumInstallationError("Trying to import unspecified module")

    if component is None:
        component_string = ""
    else:
        component_string = "'%s' from " % component

    logging.debug("Checking to see if we can use %smodule '%s'" % (component_string, module))

    try:
        if component is None or component == "*":
            __import__(module)
        else:
            imported_module = __import__(module, globals(), locals(), [component])
            for element in component.split(","):
                if not element in imported_module.__dict__:
                    raise ImportError("Component %s not found in module %s" % (element, module))
    except ImportError, import_error:
        raise CerebrumInstallationError("Unable to load %smodule '%s': %s"
                                        % (component_string, module, import_error))

    logging.debug("%smodule '%s' - verified" % (component_string, module))
    return True


def check_python_version(atleast=None, atmost=None):
    """Checks to see if the python version is suitable.

    Note that this function is nice in a dumb way; if you only specify
    that the version needs to be '2' (either way), it will be
    considered valid for all versions of '2.x.x', both for minimum
    version and as maximum version. In other words, make sure to
    qualify the versions properly if that's what you need.

    @param atleast: The minimum/oldest version allowed
    @type atleast: Tuple of numbers, e.g. (2,3,1) or simply (2,)

    @param atmost: The maximum/newest version allowed
    @type atmost: Tuple of numbers, e.g. (2,3,1) or simply (2,)

    @return: True is all goes well

    @raise CerebrumInstallationError: If system version is invalid.
    
    @raise TypeError: If parameter(s) is/are invalid.
    
    """
    if atleast is None and atmost is None:
        raise CerebrumInstallationError("Trying to check python version without giving any parameters")

    if atleast is not None and not isinstance(atleast, tuple):
        raise TypeError("'atleast'-parameter need to be a tuple rather than a %s" % type(atleast))

    if atmost is not None and not isinstance(atmost, tuple):
        raise TypeError("'atleast'-parameter need to be a tuple rather than a %s" % type(atmost))

    system_version = sys.version_info
    
    # The checks will take it that things are good till proven otherwise.
    
    # If the compared numbers are equal, iteration will continue,
    # since we need to check the less significant numbers to
    # determine; if info is found that decides the matter (either
    # way), we'll break (info = good) or raise an exception
    # (info = bad).
    
    # Checks 3 most significant version numbers (if that many are
    # specified by the caller); deemed sufficient for our purposes.
    
    if atleast is not None:
        for version_ticker in range(0,3):
            if len(atleast) <= version_ticker:
                break # No further numbers specified; we're good
            if atleast[version_ticker] < system_version[version_ticker]:
                break 
            if atleast[version_ticker] > system_version[version_ticker]:
                raise CerebrumInstallationError("You need a newer version of Python. "
                                                + "You have %s and need at least %s" %
                                                (system_version, atleast))

    if atmost is not None:
        for version_ticker in range(0,3):
            if len(atmost) <= version_ticker:
                break
            if atmost[version_ticker] > system_version[version_ticker]:
                break
            if atmost[version_ticker] < system_version[version_ticker]:
                raise CerebrumInstallationError("You have too new a version of Python. "
                                                + "You have %s and can have at most %s" %
                                                (system_version, atmost))

    return True


def check_cerebrum_user(user=None, group=None):
    """Verfies that the Cerebrum user exists and is useable for our
    purposes. Also performs a sanity check that the user is part of
    the group specified.

    @param user: Username we wish to verify.
    @type user: String

    @param group: Groupname we wish to verify.
    @type group: String

    @return: True, if all goes well.

    @raise CerebrumInstallationError: If parameters are invalid or if
        user/group are invalid.

    """
    if user is None or group is None:
        raise CerebrumInstallationError("Need to specify both user and group")

    logging.debug("Verifying user '%s'" % user)
    try:
        pwdentry = pwd.getpwnam(user)
    except KeyError:
        raise CerebrumInstallationError("User '%s' does not exist on this system", user)

    logging.debug("Verifying group '%s'" % group)
    try:
        grpentry = grp.getgrnam(group)
    except KeyError:
        raise CerebrumInstallationError("Group '%s' does not exist on this system", group)

    logging.debug("Verifying user '%s's membership in group '%s'" % (user, group))
    groupmembers = grpentry[3]
    if not user in groupmembers and pwdentry[3] != grpentry[2]:
        raise CerebrumInstallationError("User '%s' not part of group '%s' on this system" % (user, group))

    return True


def copy_files(source=None, destination=None, owner="", group="",
               create_dirs=False, rename=None):
    """Copies files based on given parameters.

    The default for this function is to change the owner/group of the
    files to what has been defined as the Cerebrum user/group,
    i.e. that must be established earlier in the installation than the
    first use of this function without owner/group exclicitly defined.

    Note that owner/group must either both be specified or both be unspecified.

    @param source: Represents what is to be copied, either a directory or single file.
    @type source: String

    @param destination: Where to copy things to.
    @type destination: String

    @param owner: Which user that should own the files being copied.
        If unspecified, they will be owned by the defined cerebrum user.
        If None, they will be owned by the user running the installation.
    @type owner: String or int

    @param group: Which group that the files being copied should belong to
        If unspecified, they will belong to the defined cerebrum group.
        If None, they will belong to the group of the user running the installation.
    @type group: String or int

    @param create_dirs: Whether or not to create the destination
        directory if it doesn't exist.
    @type create_dirs: Boolean

    @raise CerebrumInstallationError: If something is wrong with
        the parameters or if something goes wrong while copying.

    @return: True is all goes well.

    """
    if source is None:
        raise CerebrumInstallationError("Sourcefile unspecified - unable to copy 'nothing'")

    data = CerebrumInstallationData()
    if owner == "":
        owner = data["CEREINSTALL_USER"]
    if owner is None:
        owner = os.getuid()
        
    if group == "":
        group = data["CEREINSTALL_GROUP"]
    if group is None:
        group = os.getgid()
        
    if not os.path.exists(destination):
        if not create_dirs:
            raise CerebrumInstallationError("Destination does not exist and you don't want to create it.")
        else:
            os.makedirs(destination)
    elif not os.path.isdir(destination):
        raise CerebrumInstallationError("Cannot copy to something that isn't a directory")

    logging.debug("Copying '%s' to '%s'" % (source, destination))
    if os.path.isdir(source):
        shutil.copytree(source, destination)
    else:
        shutil.copy(source, destination)

    # Owner/group given by name, we need numerics for os.chown-command
    # Force parameter into string context, since int doesn't have "isdigit"-method
    if str(owner).isdigit():
        uid = owner
    else:
        try:
            pwdentry = pwd.getpwnam(owner)
            uid = pwdentry[2]
        except KeyError:
            raise CerebrumInstallationError("User '%s' does not exist on this system" % owner)

    if str(group).isdigit():
        gid = group
    else:
        try:
            grpentry = grp.getgrnam(group)
            gid = grpentry[2]
        except KeyError:
            raise CerebrumInstallationError("Group '%s' does not exist on this system" % group)


    if os.path.isdir(source):
        change_target = destination
    else:
        change_target = os.path.join(destination, os.path.basename(source))

    logging.debug("Changing owner of '%s' to %s:%s (%i:%i)" % (change_target, owner, group, uid, gid))
    
    try:
        os.chown(change_target, uid, gid)
    except OSError, error:
        raise CerebrumInstallationError("Unable to chown: '%s'", error)

    if rename is not None:
        rename_target = os.path.join(os.path.dirname(change_target), rename)
        if os.path.exists(rename_target):
            raise CerebrumInstallationError("File '%s' already exists, cannot rename '%s' to it" %
                                            (rename_target, change_target))
        logging.debug("Renaming '%s' to '%s'" % (change_target, rename_target))
        os.rename(change_target, rename_target)

    return True


def create_directory(directory=None):
    """Creates directory. Will create parent directories too, as needed.

    Note that create_directory is unable to handle 'backstepping'
    directories a la '/dirA/dirB/../dirC', but there should be no
    need to create directories in that manner anyway.

    @param directory: Directory that is to be created
    @type directory: String

    @raise CerebrumInstallationError: If something goes wrong or
        if no parameter given.

    """
    if directory is None:
        raise CerebrumInstallationError("Directory unspecified - unable to create 'nothing'")

    try:
        os.makedirs(directory)
    except OSError, error:
        raise CerebrumInstallationError("Unable to create directory '%s': %s" % (directory, error))


def do_sql(sql_command=None, sql_file=None):
    """Runs SQL either based on given command or on given input file.

    Not implemented yet.

    """
    if sql_command is not None and sql_file is not None:
        raise CerebrumInstallationError("Cannot define an sql action based on both a given command and a file.")

    raise NotImplementedError("This function has not been implemented yet.")


def inform_user(message=""):
    """Dumps message to logs and to screen.

    @param message: Information that user should see.
    @type message: String

    """
    logging.info(message)
    max_width = 77
    while len(message) > max_width:
        # Break string into suitable width pieces
        last_space = message.rindex(" ", 0, max_width)
        print message[:last_space]
        message = message[last_space+1:] # +1 to strip 'space'
    print message
    

def job_runner_setup():
    """Sets up jobs for job runner.

    Not implemented yet.

    """
    raise NotImplementedError("This function has not been implemented yet.")


def update_config(info=None, directive=None, default=None, interactive=False):
    """Updates Cerebrum configuration

    Not implemented yet.

    """
    raise NotImplementedError("This function has not been implemented yet.")


def work_start(activity=""):
    """Informs user that an activity has started.

    Needs to be seen in concert with 'work_end', since 'work_start'
    will print an unreturned line to the screen, that 'work_end' will
    end with 'OK' and a carriage return. In other words, there should
    be no normal output to the screen between using 'work_start' and
    'work_end', and one should not be used without the other.

    @param activity: Description of what is taking place. Max 70
        characters.    
    @type activity: String

    """
    global current_activity
    current_activity = activity
    
    logging.debug("Starting '%s'" % current_activity)
    number_of_dots = 70 - len(activity)
    
    dot_string = "." * number_of_dots
    
    print activity + dot_string,


def work_end():
    """Informs user that an activity has ended.

    Needs to be seen in concert with 'work_start', since 'work_start'
    will print an unreturned line to the screen, that 'work_end' will
    end with 'OK' and a carriage return. In other words, there should
    be no normal output to the screen between using 'work_start' and
    'work_end', and one should not be used without the other.

    """
    logging.debug("Done with '%s'" % current_activity)
    print "OK"
