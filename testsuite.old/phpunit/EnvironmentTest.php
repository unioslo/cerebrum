<?php
#require_once 'My/Fleet.php';
 
# TODOS:
# - cli does not change the cwd to the running script - the code needs to 
#      handle this, probably through absolute paths with SYSTEM_DIR etc.
# - how to check if the script is run through cli? is checking for 
#      $_SERVER['argv'] good enough?
# - how to set up the environment? easy to include the config directory, but 
#      how about the rest, e.g. autoloading of classes?
#
#      Shouldn't include the config (constants), but clean up the code instead.  
#      Constants should not be used in generic classes.


/**
 * Testing that the environment is working as it should.
 */
class EnvironmentTest extends PHPUnit_Framework_TestCase {

    public function setUp() { }

    /**
     * Check if PHP settings are as the tests wants them to be.
     * Some of the settings are set in test/phpunit/phpunit.xml, others might 
     * need a bootstrap file to be set correctly.
     */
    public function testErrorLogging() {

        $this->assertEquals('1', ini_get('display_errors'), 'The errors should'.
            ' be displayed in the test environment. Set "display_errors" to 1 '.
            'in your php.ini.');
        $this->assertEquals('1', ini_get('display_startup_errors'), 
            'The startup errors should be displayed in the test environment. ' .
            'Set "display_startup_errors" to 1 in your php.ini.');

        $error_reports = (int) sprintf('%u', ini_get('error_reporting'));
        # converted the 'error_reporting' bytes to _unsigned_ int, so it could 
        # easier be checked:
        $this->assertGreaterThanOrEqual(E_ALL, $error_reports,
            'Not all errors are logged, need at least E_ALL (not ' .
            'necessarily E_STRICT). Change "error_reporting" to at least ' .
            'E_ALL in your php config.');
        # E_ALL is all but E_STRICT
        # More info about the error constants: 
        # php.net/manual/en/errorfunc.constants.php
    }

    public function testIniSet() {
    
        $this->assertNotContains('ini_set', ini_get('disable_functions'), 
            'Function ini_set() is disabled, which troubles the setup of the ' .
            'test environment. Please remove ini_set from "disable_functions"' .
            ' in your php.ini.');
    }

    public function testSessionPath() {

        $path = ini_get('session.save_path');

        $this->assertTrue(is_dir($path), "Sesssions save path '$path' doesn't ".
            "exist. Either create it or change 'session.save_path' in your ".
            "php.ini.");
        $this->assertTrue(is_writable($path), "Session save path '$path' is " .
            "not writable by you. Either chmod the dir or change " .
            "'session.save_path' in your php.ini.");

    }

}
