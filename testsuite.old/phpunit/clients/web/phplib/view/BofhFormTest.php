<?php
// Copyright 2010 University of Oslo, Norway
// 
// This file is part of Cerebrum.
// 
// Cerebrum is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// Cerebrum is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with Cerebrum. If not, see <http://www.gnu.org/licenses/>.

class BofhFormTest extends PHPUnit_Framework_TestCase
{
    public static function setUpBeforeClass()
    {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/BofhForm.php';
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/BofhForm/reCaptcha.php';
    }
    public static function tearDownAfterClass() { }

    public function setUp()
    {
        // pretend that the session has started:
        $_SESSION = array();
    }
    public function tearDown()
    {
    }


    public function testConstruction()
    {
        $form = new BofhForm();
        $form = new BofhForm('name');
    }

    /**
     * @expectedException BofhFormSessionException
     */
    public function testWithoutSession()
    {
        // if no session is started, an error should be returned
        unset($_SESSION);
        $form = new BofhForm('teste');
    }

    public function testOutputName()
    {
        $form = new BofhForm('testForm');
        $out = (string) $form;
        $this->assertTrue(is_numeric(strpos($out, 'name="testForm"')), 
                            'Name is missing from form');
        $this->assertTrue(is_numeric(strpos($out, 'id="testForm"')),
                            'ID (name) is missing from form');
    }

    public function testPostMethod()
    {
        $form = new BofhForm('namn');
        // TODO: need to parse the html somehow to test it thorough. 
        $out = (string) $form;
        $this->assertTrue(is_numeric(stripos($out, 'method="post"')),
            'Forms should set method=POST as default, due to security. This does not!');
        $this->assertFalse(is_numeric(stripos($out, 'method="get"')),
            'Forms should set method=POST as default, due to security. This does not!');
    }

    public function testAddedElements()
    {
        $form = new BofhForm('name');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('text', 'textEleName', 'Label info:', 'attributes="2"');
        $form->addElement('textarea', 'textareaEleName', 'Label info:', 'attributes="2"');

        $this->markTestIncomplete('Not implemented yet.');
    }

    public function testValidation()
    {
        $this->markTestIncomplete('Need to test that elements validate correctly.');
    }
    public function testBadValidation()
    {
        $this->markTestIncomplete('Need to test that elements do not validate.');
    }
    public function testPostValidation()
    {
        $this->markTestIncomplete('Need to test that GET-data doesn\'t validate in a POST-form.');
    }

    public function testReturnValues()
    {
        $this->markTestIncomplete('Need to check that the returned values are correct.');
    }

    public function testReCaptchaKeys()
    {
        BofhForm_reCaptcha::setKeys('a-private-one', 'public-one');
        $this->assertEquals('public-one', BofhForm_reCaptcha::$public_key,
            'Public key not correctly set');
    }

    /**
     * @runInSeparateProcess
     */
    public function testReCaptchaWithoutKeys()
    {
        $form = new BofhForm('testForm');
        try {
            $form->addElement('recaptcha');
        } catch(PHPUnit_Framework_Error $e) {
            return;
        }
        $this->fail('reCaptcha should not work without defined keys');
    }


    public function testReCaptcha()
    {
        BofhForm_reCaptcha::setKeys('public-one', 'a-private-one');
        $form = new BofhForm('testForm');
        $form->addElement('recaptcha');
        $this->markTestIncomplete('Should test reCaptcha more thorough, as its not a part of HTML_QuickForm');
    }


    public function testOutputValidation()
    {
        // TODO: need to parse the html somehow to test it thorough. 
        $this->markTestIncomplete('Need to parse the html to test it for validation');
    }

    public function testHtmlValues()
    {
        $this->markTestIncomplete('Should test that if values contains html, this should be escaped in the output');

    }

    public function testTokenSetAtConstruct()
    {
        $form = $this->createTestForm('tokenTest');

        // TODO: retrievement should not be hardcoded, but saw no other way.
        $token = $form->getElement('qf_token_');
        $this->assertTrue((bool) $token->getValue(), 
            'Token should not be an empty string'
        );
    }

    public function testTokenValidates()
    {
        $form = $this->createTestForm(__FUNCTION__);
        // TODO: retrievement should not be hardcoded, but saw no other way.
        $token = $form->getElement('qf_token_');
        $_POST = array(
            'username'              => 'johndoe',
            'pass'                  => '12345',
            'qf_token_'             => $token->getValue(),
            '_qf__' . __FUNCTION__  => '');
        $_REQUEST = $_POST;

        $form = $this->createTestForm(__FUNCTION__);
        $this->assertTrue($form->validate(), 
            'Form should validate after being recreated, token is correct'
        );
    }

    public function testFormWhenMethodIsNull()
    {
        $form = new BofhForm(__FUNCTION__, null, '/logon.php');
        $form->addElement('text', 'username', 'Your username:');
        $form->addElement('password', 'pass', 'Your password:');
        $form->addElement('submit', null, 'Log on');
        $form->addRule('username', 'Username is required', 'reguired');

        // TODO: retrievement should not be hardcoded, but saw no other way.
        $token = $form->getElement('qf_token_');
        $this->assertTrue(is_a($token, 'HTML_Common'),
            'Token not created when method is null'
        );
        $_POST = array(
            'username'              => 'johndoe',
            'pass'                  => '12345',
            'qf_token_'             => $token->getValue(),
            '_qf__' . __FUNCTION__  => '');
        $_REQUEST = $_POST;

        $form = $this->createTestForm(__FUNCTION__);
        $this->assertTrue($form->validate(), 
            'Form should validate as post, when method is null'
        );
    }


    public function testTokenDifferentBetweenForms()
    {
        $form1 = $this->createTestForm('tokenUnique');
        $form2 = $this->createTestForm('tokenOther');
        $toke1 = $form1->getElement('qf_token_');
        $toke2 = $form2->getElement('qf_token_');
        $this->assertNotEquals($toke1->getValue(), $toke2->getValue(),
            'Tokens should be different between different forms'
        );
    }

    /**
     * @expectedException PHPUnit_Framework_Error
     */
    public function testTokenFail()
    {
        $form = $this->createTestForm(__FUNCTION__);
        $_POST = array(
            'username'              => 'johndoe',
            'pass'                  => '12345',
            'qf_token_'             => 'not-correct-token  ',
            '_qf__' . __FUNCTION__  => '');
        $_REQUEST = $_POST;

        $form = $this->createTestForm(__FUNCTION__);
        $this->assertFalse($form->validate(), 
            'Form should not validate with wrong token'
        );
    }

    public function testSecurityCallback()
    {
        $user = $this->getMock('TokenCallbackTester');
        $user->expects($this->once())
             ->method('logoff')
             ->will($this->returnValue(true));

        BofhForm::addSecurityCallback(array($user, 'logoff'));

        $form = $this->createTestForm(__FUNCTION__);
        $_POST = array(
            'username'              => 'johndoe',
            'pass'                  => '12345',
            'qf_token_'             => 'not-correct-token  ',
            '_qf__' . __FUNCTION__  => '');
        $_REQUEST = $_POST;
        $form = $this->createTestForm(__FUNCTION__);
        @$form->validate();
    }

    public function testSecurityCallbackWithParameters()
    {
        $user = $this->getMock('TokenCallbackTester');
        $user->expects($this->once())
             ->method('logoff')
             ->will($this->returnValue(true));
        $user->expects($this->once())
             ->method('dummy')
             ->will($this->returnValue(false));

        BofhForm::addSecurityCallback(array($user, 'logoff'));
        BofhForm::addSecurityCallback(array($user, 'dummy'), 'hei');

        $form = $this->createTestForm(__FUNCTION__);
        $_POST = array(
            'username'              => 'johndoe',
            'pass'                  => '12345',
            'qf_token_'             => 'not-correct-token  ',
            '_qf__' . __FUNCTION__  => '');
        $_REQUEST = $_POST;
        $form = $this->createTestForm(__FUNCTION__);
        @$form->validate();
        $this->markTestIncomplete('Have not tested if the parameters are actually used.');
    }

    /**
     * If no action site is given, PHP_SELF is used, but that may contain 
     * index.php, which should be removed from the url.
     */
    public function testNotIndexInAction()
    {

        // keys = urls, values = urls without index.php
        $urls = array(
            'logon.php' => 'logon.php',
            '/subdir/index.php' => '/subdir/',
            'https://example.com/index.php' => 'https://example.com/',
            'http://example.com/subdir/index.php' => 'http://example.com/subdir/',
            'http://index.php.example.com/index.php' => 'http://index.php.example.com/',
            '/subdir/index.php/logon.php' => '/subdir/index.php/logon.php',
            '/index.php' => '/',
            '/index.htm' => '/',
            '/index.html' => '/',
            'index.php' => '',
            'index.htm' => '',
        );
        foreach ($urls as $oldurl => $newurl) {
            $_SERVER['PHP_SELF'] = $oldurl;
            $form = new BofhForm();
            $action = $form->getAttribute('action');
            $this->assertEquals($newurl, $action, 'Action url not correctly parsed');
        }

    }


    /**
     * Creates a standard form for testing.
     */
    function createTestForm($name)
    {
        $form = new BofhForm($name);
        $form->addElement('text', 'username', 'Your username:');
        $form->addElement('password', 'pass', 'Your password:');
        $form->addElement('submit', null, 'Log on');

        $form->addRule('username', 'Username is required', 'reguired');
        return $form;
    }
}


/**
 * A dummy for getMock(), as it requires a class to exist before creating the 
 * mockup.
 */
class TokenCallbackTester
{
    public function logoff()
    {
        return true;
    }
    public function dummy($param1)
    {
        return $param1;
    }
}


?>
