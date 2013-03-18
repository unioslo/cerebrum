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
        $init = new HelperInit();
    }

    public function testAutoloadMethod() {
        $this->assertTrue(HelperInit::autoload('Text'),
            'Couldn\'t autoload class Text');
        $this->assertFalse(HelperInit::autoload('vakjkajskdjfkasdfA_ASDFSDF__ASDF'),
            'InitBase::autoload claims to have loaded a nonexisting class');
    }

    public function testAutoloading() {
        $init = new HelperInit();
        try {
            Text::setLocation('/');
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

    public static function getView() {}
    public static function getUser() {}

}
