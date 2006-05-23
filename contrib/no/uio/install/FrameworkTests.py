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

import os
import unittest
import shutil

from Framework import *

__doc__ = """Contains all tests for the installation framework.

Can be run both from the commandline and as part of a larger test
framework.

Make sure that any new methods defining tests have names starting with
'test', so that they automagically are included in the testsuites
being put together and used.

"""

__version__ = "$Revision$"
# $Source$


class CerebrumInstallationDataTestCase(unittest.TestCase):

    """All tests for the CerebrumInstallationData class.

    Note that due to the Borg nature of CerebrumInstallationData, the
    system seems to retain statest between tests.

    """


    def test_simple_data_retrieval(self):
        """Cerebrum installation data - simple data retrieval."""
        data = CerebrumInstallationData()
        data["test"] = "Teststring"
        self.assertEqual(data["test"], "Teststring",
                         "Retrieved data does not match data input")


    def test_data_retrieval_across_objects(self):
        """Cerebrum installation data - data retrieval across objects."""
        data1 = CerebrumInstallationData()
        data2 = CerebrumInstallationData()
        data1["test"] = "Teststring"
        self.assertEqual(data2["test"], "Teststring",
                         "Retrieved data does not match data input")


    def test_new_object_does_not_nuke_old_data(self):
        """Cerebrum installation data - New object doesn't wipe old data"""
        data1 = CerebrumInstallationData()
        data1["test"] = "Teststring"
        data2 = CerebrumInstallationData()
        self.assertEqual(data2["test"], "Teststring",
                         "New object wiped previous data")


    def test_implements_contain_properlys(self):
        """Cerebrum installation data - 'thingy in data' implemented properly."""
        data = CerebrumInstallationData()
        data["test"] = "Teststring"
        self.assertEqual("test" in data, True,
                         "Does not implement '__contains__' properly.")


    def test_returns_none_on_nonexisting_key(self):
        """Cerebrum installation data - returns 'None' for non-existing keys."""
        data = CerebrumInstallationData()
        self.assertEqual(data["blatti"], None,
                         "Incorrect return-value for non-existing key.")


    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CerebrumInstallationDataTestCase, "test")
    suite = staticmethod(suite)
    


class CheckPythonModuleTestCase(unittest.TestCase):

    """All tests for the 'check_python_library'-function."""


    def test_imports_that_work(self):
        """Check Python module - imports that should work."""
        # Check module (only)
        self.assertEqual(check_python_library(module="os"), True)
        # Check module and specific component
        self.assertEqual(check_python_library(module="os", component="path"), True)
        # Check module and generic component
        self.assertEqual(check_python_library(module="os", component="*"), True)
        # Check module and comma-seperated component
        self.assertEqual(check_python_library(module="os", component="chown,link,listdir"), True)
        # Check 'deeper' module
        self.assertEqual(check_python_library(module="os.path"), True)
        # Check 'deeper' module with component
        self.assertEqual(check_python_library(module="distutils.command", component="build_scripts"), True)
        # Check local stuff
        self.assertEqual(check_python_library(module="Framework", component="check_python_version"), True)


    def test_imports_that_dont_work(self):
        """Check Python module - imports that should fail."""
        # Cannot call method withod specifying a module
        self.assertRaises(CerebrumInstallationError, check_python_library)
        # ... not even when (only) component is specified
        self.assertRaises(CerebrumInstallationError, check_python_library, component="path")
        # Bogus module
        self.assertRaises(CerebrumInstallationError, check_python_library, module="fnattiblatti")
        # Real module, bogus component
        self.assertRaises(CerebrumInstallationError, check_python_library, module="sys", component="fnattiblatti")
        # Real module, component both real and bogus
        self.assertRaises(CerebrumInstallationError, check_python_library, module="sys", component="path,fnattiblatti")
        # Real module, deep component
        self.assertRaises(CerebrumInstallationError, check_python_library, module="distutils", component="command.build_scripts")


    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CheckPythonModuleTestCase, "test")
    suite = staticmethod(suite)
        


class CopyFilesTestCase(unittest.TestCase):

    """All tests for the 'copy_files'-function."""


    def setUp(self):
        """Basic setup needed for tests."""

        self.input_dir = "input/copy_files"
        self.output_dir = "output/copy_files"
        os.mkdir(self.output_dir)

        data = CerebrumInstallationData()
        data["CEREINSTALL_USER"] = os.getuid()
        data["CEREINSTALL_GROUP"] = os.getgid()


    def test_no_source_file(self):
        """Copy files - fail on source-file not specifed"""
        self.assertRaises(CerebrumInstallationError, copy_files)
    

    def test_copy_single_file(self):
        """Copy files - single file"""
        self.assertEquals(copy_files(source=self.input_dir + "/single_file/single_file.py",
                                     destination=self.output_dir),
                          True)
        filesize = 12961
        self.assertEquals(os.path.getsize(self.output_dir + "/single_file.py"), filesize,
                          "Filesize of copied file is incorrect (it isn't %i bytes )" % filesize)
    

    def test_destination_doesnt_exist_nocreate(self):
        """Copy files - fail on destination doesn't exist, nocreate"""
        self.assertRaises(CerebrumInstallationError, copy_files,
                          source=self.input_dir + "/no_destination/file.py",
                          destination=self.output_dir + "/nodir")
    

    def test_destination_doesnt_exist_create(self):
        """Copy files - destination doesn't exist, create"""
        self.assertEquals(copy_files(source=self.input_dir + "/no_destination/file.py",
                                     destination=self.output_dir + "/newdir",
                                     create_dirs=True),
                          True)
        filesize = 12961
        self.assertEquals(os.path.getsize(self.output_dir + "/newdir/file.py"), filesize,
                          "Filesize of copied file is incorrect (it isn't %i bytes )" % filesize)
    

    def test_destination_doesnt_exist_create_deep(self):
        """Copy files - deep destination doesn't exist, create"""
        self.assertEquals(copy_files(source=self.input_dir + "/no_destination/file.py",
                                     destination=self.output_dir + "/newdir/a/b/c/d/e",
                                     create_dirs=True),
                          True)
        filesize = 12961
        self.assertEquals(os.path.getsize(self.output_dir + "/newdir/a/b/c/d/e/file.py"), filesize,
                          "Filesize of copied file is incorrect (it isn't %i bytes )" % filesize)
    

    def test_change_owner_not_allowed(self):
        """Copy files - fail on 'change owner' not allowed"""
        self.assertRaises(CerebrumInstallationError, copy_files,
                          source=self.input_dir + "/single_file/single_file.py",
                          destination=self.output_dir,
                          owner="root")
    

    def test_change_owner_user_not_exist(self):
        """Copy files - fail on 'change owner' user doesn't exist"""
        # For test to work properly, it is required to have a user 'nobody' on the system
        self.assertRaises(CerebrumInstallationError, copy_files,
                          source=self.input_dir + "/single_file/single_file.py",
                          destination=self.output_dir,
                          owner="barglfargl")
    

    def tearDown(self):
        """Cleanup after tests."""
        shutil.rmtree(self.output_dir)
    

    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CopyFilesTestCase, "test")
    suite = staticmethod(suite)
        


class CreateDirectoryTestCase(unittest.TestCase):

    """All tests for the 'create_directory'-function."""


    def setUp(self):
        """Basic setup needed for tests."""
        self.output_dir = "output/create_directory"


    def test_create_normal_directory(self):
        """Create directory - normal directory"""
        target = self.output_dir + "/test"
        create_directory(target)
        self.assertEquals(os.path.isdir(target), True)


    def test_create_deep_directory(self):
        """Create directory - deep directory"""
        target = self.output_dir + "/test/a/b/c/d/d/e/f/g"
        create_directory(target)
        self.assertEquals(os.path.isdir(target), True)


    def test_create_backstepping_directory(self):
        """Create directory - fails on backstepping"""
        target = self.output_dir + "/test/test2/../test3"
        self.assertRaises(CerebrumInstallationError, create_directory, target)


    def tearDown(self):
        """Cleanup after tests."""
        shutil.rmtree(self.output_dir)
    

    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CreateDirectoryTestCase, "test")
    suite = staticmethod(suite)



class CheckCerebrumUserTestCase(unittest.TestCase):

    """All tests for the 'check_cerebrum_user'-function."""


    def test_fail_on_no_parameters(self):
        """Check cerebrum user - Fail on no parameters."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user)
    

    def test_fail_on_no_group(self):
        """Check cerebrum user - Fail when group unspecified."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user, user="root")
    

    def test_fail_on_no_user(self):
        """Check cerebrum user - Fail when user unspecified."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user, group="sys")
    

    def test_user_and_group_correct_explicit(self):
        """Check cerebrum user - User and group exist; user part of group explicitly."""
        self.assertEquals(check_cerebrum_user(user="root", group="sys"), True,
                          "root/sys should be a valid user/group, but unable to determine so.")
    

    def test_user_and_group_correct_implicit(self):
        """Check cerebrum user - User and group exist; user part of group, implicitly"""
        self.assertEquals(check_cerebrum_user(user="nobody", group="nobody"), True,
                          "root/sys should be a valid user/group, but unable to determine so.")
    

    def test_user_not_part_of_group(self):
        """Check cerebrum user - User and group exist; fail on user not part of group."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user,
                          user="nobody", group="sys")
    

    def test_user_does_not_exist(self):
        """Check cerebrum user - Fail on user does not exist."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user,
                          user="fnarglbargl", group="sys")
    

    def test_group_does_not_exist(self):
        """Check cerebrum user - Fail on group does not exist."""
        self.assertRaises(CerebrumInstallationError, check_cerebrum_user,
                          user="root", group="fnarglbargl")
    

    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CheckCerebrumUserTestCase, "test")
    suite = staticmethod(suite)



class CheckPythonVersionTestCase(unittest.TestCase):

    """All tests for the 'check_python_version'-function."""


    def test_parameters_are_not_none(self):
        """Check Python version - have at least one parameter."""
        self.assertRaises(CerebrumInstallationError, check_python_version)


    def test_parameters_that_should_work(self):
        """Check Python version - parameters that work."""
        # "atleast"-checks
        self.assertEqual(check_python_version(atleast=(2,)), True)
        self.assertEqual(check_python_version(atleast=(2,0,9)), True)
        # "atmost"-checks
        self.assertEqual(check_python_version(atmost=(5,)), True)
        self.assertEqual(check_python_version(atmost=(5,5,9)), True)
        
        
    def test_parameters_that_should_not_work(self):
        """Check Python version - parameters that fail"""
        # "atleast"-checks
        self.assertRaises(CerebrumInstallationError, check_python_version, atleast=(5,))
        self.assertRaises(CerebrumInstallationError, check_python_version, atleast=(5,2,3))
        # "atmost"-checks
        self.assertRaises(CerebrumInstallationError, check_python_version, atmost=(1,))
        self.assertRaises(CerebrumInstallationError, check_python_version, atmost=(2,1,3))
        # Calling with wrong type of parameters
        self.assertRaises(TypeError, check_python_version, atleast="1.2.3")
        self.assertRaises(TypeError, check_python_version, atmost="5.5")
        

    def suite():
        """Returns a suite containing all the test cases in this class."""
        return unittest.makeSuite(CheckPythonVersionTestCase, "test")
    suite = staticmethod(suite)



def suite():
    """Returns a suite containing all the test cases in this module."""
    return unittest.TestSuite((CerebrumInstallationDataTestCase.suite(),
                               CheckPythonModuleTestCase.suite(),
                               CopyFilesTestCase.suite(),
                               CreateDirectoryTestCase.suite(),
                               CheckCerebrumUserTestCase.suite(),
                               CheckPythonVersionTestCase.suite()))



if __name__ == "__main__":
    unittest.main(defaultTest='suite')
