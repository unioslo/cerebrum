<?php

/**
 * These tests does inclusion of classes, constants and defines autoloading, 
 * amongst others, and must therefore be run in separate processes to avoid 
 * settings being transfered between tests.
 *
 * @runTestsInSeparateProcesses
 */
class InitTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        # Code should be located as in the cerebrum-tree in the unittest 
        # environment, so we need to use the relative paths for including code 
        # files:
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/controller/InitBase.php');
        #if(@include_once(dirname(__FILE__) . '/../../../../../system/phplib/controller/InitBase.php')) {
        #    # Try the include_path as a fallback
        #    include_once('InitBase.php');
        #}
    }
    public static function tearDownAfterClass() { }

    public function setUp() {
        foreach(array('controller', 'model', 'view') as $d) {
            $dir = TEST_PREFIX_CEREBRUM . "/clients/web/phplib/$d";
            HelperInit::addAutoloadDir($dir);
        }
    
    
    }
    public function tearDown() { }


    public function testConstruction() {
        $init = new InitBase();
    }

    public function testAutoloadMethod() {
        $this->assertTrue(HelperInit::autoload('Text'),
            'Couldn\'t autoload class View');
        $this->assertFalse(HelperInit::autoload('vakjkajskdjfkasdfA_ASDFSDF__ASDF'),
            'InitBase::autoload claims to have loaded a nonexisting class');
    }

    public function testAutoloading() {
        $init = new InitBase();
        try {
            $t = new Text('invalidlanguagetag');
        } catch (LanguageTagInvalidException $e) {
            return true;
        }
    }

}

include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/controller/InitBase.php');

/**
 * Extending the InitBase class, to reach protected values.
 */
class HelperInit extends InitBase {
    public static function addAutoloadDir($dir) {
        self::$autoload_dirs[] = $dir;
    }
}
