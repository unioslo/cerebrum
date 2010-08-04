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

class BofhFormTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/BofhForm.php';
    }
    public static function tearDownAfterClass() {
    }

    public function setUp() {
        # pretend that the session has started:
        $_SESSION = array();
    }
    public function tearDown() {
    }


    public function testConstruction() {
        $form = new BofhForm();
        $form = new BofhForm('namn');
    }

    public function testWithoutSession() {
        # if no session is started, an error should be returned
        unset($_SESSION);
        try {
            $form = new BofhForm('teste');
        } catch (Exception $e) {
            return true;
        }
        $this->fail('BofhForm should fail if session is not started');
    }
    public function testOutputName() {
        $form = new BofhForm('testForm');
        $out = (string) $form;
        $this->assertTrue(is_numeric(strpos($out, 'name="testForm"')), 
                            'Name is missing from form');
        $this->assertTrue(is_numeric(strpos($out, 'id="testForm"')),
                            'ID (name) is missing from form');
    }
    public function testPostMethod() {
        $form = new BofhForm('namn');
        # TODO: need to parse the html somehow to test it thorough. 
        $out = (string) $form;
        $this->assertTrue(is_numeric(stripos($out, 'method="post"')),
            'Forms should set method=POST as default, due to security. This does not!');
        $this->assertFalse(is_numeric(stripos($out, 'method="get"')),
            'Forms should set method=POST as default, due to security. This does not!');
    }
    public function testElements() {
        $form = new BofhForm('namn');
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

    public function testValidation() {
        $this->markTestIncomplete('Need to test that elements validate correctly.');
    }
    public function testBadValidation() {
        $this->markTestIncomplete('Need to test that elements do not validate.');
    }
    public function testPostValidation() {
        $this->markTestIncomplete('Need to test that GET-data doesn\'t validate in a POST-form.');
    }

    public function testReturnValues() {
        $this->markTestIncomplete('Need to check that the returned values are correct.');
    }

    public function testReCaptcha() {
        $form = new BofhForm('testForm');
        $form->addElement('recaptcha');
        $this->markTestIncomplete('Should test reCaptcha more thorough, as its not a part of HTML_QuickForm');
    }


    public function testOutputValidation() {
        # TODO: need to parse the html somehow to test it thorough. 
        $this->markTestIncomplete('Need to parse the html to test it for validation');
    }

    public function testHtmlValues() {
        $this->markTestIncomplete('Should test that if values contains html, this should be escaped in the output');

    }

    public function testToken() {

        function createForm() {
            $form = new BofhForm('tokenTest');
            $form->addElement('text', 'username', 'Your username:');
            $form->addElement('password', 'pass', 'Your password:');
            $form->addElement('submit', null, 'Log on');

            $form->addRule('username', 'Username is required', 'reguired');
            return $form;
        }

        ### Get form:
        $form = createForm();

        ### Get secret token

        // TODO: retrievement should not be hardcoded:
        $token = $form->getElement('qf_token_');
        $this->assertTrue((bool) $token->getValue(), 
            'Token seems to be an empty string');

        ### Send data

        $_POST = array(
            'username'          => 'johndoe',
            'pass'              => '12345',
            'qf_token_'         => $token->getValue(),
            '_qf__tokenTest'    => '');
        $_REQUEST = $_POST;

        ### Retrieve data
        $form = createForm();
        $this->assertTrue($form->validate(),
            'Form should validate, token is correct');

    }

    public function testTokenFail() {
        $this->markTestIncomplete('Should test that that submitting data with '.
            'jibberish tokens fails. This includes communicating with User as '.
            'well (or, a mockup of User).');
    }

    /**
     * If no action site is given, PHP_SELF is used, but that may contain 
     * index.php, which should be removed from the url.
     */
    public function testNotIndexInAction() {

        # keys = urls, values = urls without index.php
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
            #'index.php' => '', # this creates problems...
        );
        foreach ($urls as $oldurl => $newurl) {
            $_SERVER['PHP_SELF'] = $oldurl;
            $form = new BofhForm();
            $action = $form->getAttribute('action');
            $this->assertEquals($newurl, $action, 'Action url not correctly parsed');
        }

    }


    public function testSecurityCallback() {

        $this->called_back = false;
        BofhForm::addSecurityCallback(array($this, 'callbackTester'));
        $this->markTestIncomplete('more to do');

    }
    public function callbackTester() {
        $this->called_back = true;

    }

}
?>
