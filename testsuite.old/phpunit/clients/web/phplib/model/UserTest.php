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

class UserTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/User.php');
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/AuthenticateCom.php');
    }

    public function setUp() {
        $_SESSION = array();
    }
    public function tearDown() {
    }

    /**
     * For sending errors out of the way, to avoid getting unwanted exceptions.
     */
    public function dev_null($errno, $errstr, $errfile=null, $errline=null, $errcontext=null) {
    }

    /**
     * @expectedException Exception
     */
    public function testConstructWithoutSession() {
        $comm = $this->getMock('AuthenticateCom');
        unset($_SESSION);
        $u = new User($comm);
    }
    public function testConstruct() {
        $u = new User($this->getMock('AuthenticateCom'));
    }

    public function testSession() {
        $u = new User($this->getMock('AuthenticateCom'));
        foreach($_SESSION as $key => $value) $_SESSION[$key]['test'] = 'bugg';
        unset($u);
        foreach($_SESSION as $key => $value) {
            $this->assertArrayNotHasKey('test', $value, 
                    "User session shouldn't be writable outside of object");
        }
    }
    public function testSessionMissing() {
        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(true));
        $u = new User($comm);
        @$u->logOn('bobby', 'secret');
        unset($_SESSION);
        unset($u);
        $this->assertType('array', $_SESSION);
        $this->assertGreaterThanOrEqual(1, sizeof($_SESSION));
    }

    public function testLoggedOut() {
        $u = new User($this->getMock('AuthenticateCom'));
        $this->assertFalse($u->isLoggedOn());
    }

    /**
     * Should be logged:
     * @expectedException PHPUnit_Framework_Error
     */
    public function testFailedLogOn() {
        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(false));

        $u = new User($comm);
        $this->assertFalse($u->logOn('username', 'password'),
                           "Logon didn't fail");
        $this->assertFalse($u->isLoggedOn(), 
                           "Logon didn't fail");
    }


    public function testLogOn() {

        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(true));

        $u = new User($comm);

        # an error is logged as the session id cant be regenerated, but don't 
        # want an exception from it:
        set_error_handler(array($this, 'dev_null'));
        $this->assertTrue($u->logOn('bobby', 'secret'),
                           "Logon failed, but should work");
        restore_error_handler();

        $this->assertTrue($u->isLoggedOn(), "Logon status not updated");
    }

    public function testLogOff() {

        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(true));
        $comm->expects($this->any())
             ->method('logoff')
             ->will($this->returnValue(true));

        $u = new User($comm);
        @$u->logOn('bobby', 'secret');
        $this->assertTrue($u->logoff());
        $this->assertFalse($u->isLoggedOn(), 
                           "User not logged out after calling logout");
    }

    public function testLogOffAuthenticationObject() {

        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->once())
             ->method('logon')
             ->will($this->returnValue(true));
        $comm->expects($this->once())
             ->method('logoff')
             ->will($this->returnValue(true));

        $u = new User($comm);
        @$u->logOn('bobby', 'secret');
        $u->logoff();
    }


    public function testLogOnTimeout() {
        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(true));
        $u = new User($comm);
        @$u->logOn('bobby', 'secret');
        // set timeout and change time somehow...
        #$this->assertFalse($u->isLoggedOn(), 'Not logged out after timeout');
        $this->markTestIncomplete('Need a way to change time to check timeout');
    }


    public function testSetMaxAttempts() {
        $this->assertTrue(User::setMaxAttempts(21));
        $this->assertEquals(21, User::getMaxAttempts());
    }

    public function testBadMaxAttempts() {
        $old = User::getMaxAttempts();
        foreach(array(' no int this', -12, true) as $attempts) {
            $this->assertFalse(User::setMaxAttempts($attempts),
                'Invalid max number of attempts accepted');
            $this->assertEquals($old, User::getMaxAttempts(),
                'Max number of attempts got changed after set to invalid');
        }
    }

    public function testMaxAttempts() {

        set_error_handler(array($this, 'dev_null'));

        $comm = $this->getMock('AuthenticateCom');
        $comm->expects($this->any())
             ->method('logon')
             ->will($this->returnValue(false));

        User::setMaxAttempts(3);
        $u = new User($comm);
        $u->logon('user', 'pass');
        $u->logon('user', 'pass');
        # two attempts done, third should throw exception:
        try {
            $u->logon('user', 'pass');
        } catch (UserBlockedException $e) {
            restore_error_handler();
            return true;
        }
        restore_error_handler();
        $this->fail('Should throw UserBlockedException when failed attempts reaches max');
    }

    public function testForward() {

        $comm = $this->getMock('AuthenticateCom');
        $u = new User($comm);

    }


    public function testMoreForwarding() {
        $this->markTestIncomplete('Forwards should not be done in the super class, but it should be tested somewhere');

    }
        

}

