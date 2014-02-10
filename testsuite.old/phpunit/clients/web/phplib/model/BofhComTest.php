<?php
# Copyright 2010 University of Oslo, Norway
# 
# This file is part of Cerebrum.
# 
# Cerebrum is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Cerebrum is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Cerebrum. If not, see <http://www.gnu.org/licenses/>.

class BofhComTest extends PHPUnit_Framework_TestCase
{

    public static function setUpBeforeClass()
    {
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/AuthenticateCom.php');
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/BofhCom.php');
    }

    public function setUp()
    {
        #$_SESSION = array();
    }
    public function tearDown()
    {
    }

    public function testConstruct()
    {
        $b = new BofhCom('https://localhost:12345');
    }

    public function testNotLoggedOn()
    {
        $b = new BofhCom('https://localhost:12345');
        $this->assertFalse($b->isLoggedOn());
    }

    /**
     * TODO: or should a NotAuthenticatedException be thrown instead?
     * @expectedException BofhdNotLoggedOnExpection
     */
    public function testBadCall()
    {
        $b = new BofhCom('https://localhost:12345');
        $b->test();
        
    }

    public function testAuthenticateComExceptions()
    {
        $b = new BofhCom('https://localhost:12345');
        $methods = array('getUsername', 'getName');
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
    public function testLogonConnectionExceptions()
    {
        $b = new BofhCom('https://localhost:12345');
        $b->logon('user', 'pass');
    }

    public function testMockupConnection()
    {
        $this->markTestIncomplete('Need to test the connection by mockup');
    }

    public function testConnection()
    {
        $this->markTestIncomplete('Need to test the connection through a running bofhd');
    }

    public function testBofhdToNative()
    {
        $this->markTestIncomplete();
    }
    public function testNativeToBofhd()
    {
        $this->markTestIncomplete();
    }

}

?>
