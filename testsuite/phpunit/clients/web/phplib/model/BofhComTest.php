<?php

class BofhComTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/AuthenticateCom.php');
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/BofhCom.php');
    }

    public function setUp() {
        #$_SESSION = array();
    }
    public function tearDown() { }

    public function testConstruct() {
        $b = new BofhCom('https://localhost:12345');
    }

    public function testNotLoggedOn() {
        $b = new BofhCom('https://localhost:12345');
        $this->assertFalse($b->is_logged_on());
    }

    /**
     * @expectedException BofhdNotLoggedOnExpection
     */
    public function testBadCall() {
        $b = new BofhCom('https://localhost:12345');
        $b->test();

    }

    public function testAuthenticateComExceptions() {
        $b = new BofhCom('https://localhost:12345');
        $methods = array('get_username', 'get_name');
        foreach($methods as $method) {
            try {
                $b->$method();
            } catch (NotAuthenticatedException $e) {
                continue;
            }
            $this->fail("BofhComs method $method did not throw " . 
                        "NotAuthenticatedException");
        }
    }

    /**
     * @expectedException AuthenticateConnectionException
     */
    public function testLogonConnectionExceptions() {
        $b = new BofhCom('https://localhost:12345');
        $b->logon('user', 'pass');
    }

    public function testMockupConnection() {
        $this->markTestIncomplete('Need to test the connection by mockup');
    }

    public function testConnection() {
        $this->markTestIncomplete('Need to test the connection through a running bofhd');
    }

    public function testBofhdToNative() {
        $this->markTestIncomplete();
    }
    public function testNativeToBofhd() {
        $this->markTestIncomplete();
    }

}
