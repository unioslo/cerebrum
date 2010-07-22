<?php

include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/View.php');

class ViewTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/Text.php');
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/View.php');

    }

    public static function path() {
        return sprintf('/tmp/%s_PHPUnit_TestView_Text', $_SERVER['USER']);
    }

    public function setUp() {
        $dir = $this->path();

        @mkdir($dir);
        touch($dir . '/en.xml');
        Text::setLocation($dir);
        Text::setDefaultLanguage('en');

    }
    public function tearDown() {

    }


    /**
     * @runInSeparateProcess
     */
    public function testConstruct() {
        $v = new TestView(null, 'https://uio.no/');
        $this->assertFalse($v->isStarted(), 'View should not have started');
    }

    /**
     * @outputBuffering enabled
     * @runInSeparateProcess
     */
    public function testStart() {
        View::setBaseUrl('https://uio.no/');
        $v = new TestView();
        $v->start();
        $this->assertTrue($v->isStarted(), 'View should have been started now');
    }

    /**
     * @runInSeparateProcess
     */
    public function testNoOutputBeforeStart() {
        View::setBaseUrl('https://uio.no/');
        ob_start();
        $v = new TestView();
        $out = ob_get_clean();
        $this->assertFalse((bool) $out, 'View should not send output before ' .
            "start() is called, got '$out'");
    }

    /**
     * @runInSeparateProcess
     */
    public function testNoOutputWithoutStart() {
        $v = new TestView(null, 'https://uio.no/');
        ob_start();
        $v->end();
        $out = ob_get_clean();
        $this->assertFalse((bool) $out, 'View->end() should not send output ' .
            "before start() is called, got '$out'");
    }

    /**
     * @runInSeparateProcess
     */
    public function testSeveralStarts()  {
        $v = new TestView(null, 'https://uio.no/');

        ob_start();
        $v->start();
        ob_clean();

        $v->start();
        $out = ob_get_contents();
        unset($v);
        ob_end_clean();

        $this->assertFalse((bool) $out, 'View->start() should not send output ' .
            "more than once, got '$out' when called a second time.");
    }

    public function testForward() {
        $this->markTestIncomplete('Do not know how to test header functionality yet');
    }

    /**
     * @runInSeparateProcess
     * @outputBuffering enabled
     *
     * @expectedException BaseUrlException
     */
    public function testForwardWithoutBaseUrl() {
        View::forward('test/', null, null, false);
    }

    public function testMessages() {
        View::addMessage('Test');
        View::addMessage('test number 2', View::MSG_WARNING);

        $exptected = array(
            array('Test', View::MSG_STANDARD),
            array('test number 2', View::MSG_WARNING));

        $this->assertEquals($exptected, View::getMessages());
    }

    public function testFlushMessages() {
        View::addMessage('Test');
        View::flushMessages();
        $this->assertFalse((bool) View::getMessages(), 
            'Messages should be flushed');
    }

    /**
     * @outputBuffering enabled
     */
    public function testMessageSentAndFlushedAfterOutput() {
        View::addMessage('test');
        $v = new TestView(null, 'https://uio.no/');
        @$v->start();
        unset($v);
        $this->assertFalse((bool) View::getMessages(),
            'Old messages should be flushed after output');
    }

    /**
     * @outputBuffering enabled
     */
    public function testMessagesStoredAtForward() {
        View::addMessage('test');
        @View::forward('test/', null, null, false);
        $this->assertTrue((bool) View::getMessages(), 
            'Messages should be stored when forwarding');
    }

    /**
     * @outputBuffering enabled
     */
    public function testMessagesAtForward() {
        View::addMessage('test');
        $v = new TestView();
        @View::forward('test/', null, null, false);
        unset($v);
        $w = new TestView();
        $this->assertTrue((bool) View::getMessages(), 
            'Messages should be stored when forwarding');
    }









    public function testTheRest() {
        $this->markTestIncomplete('Need to test the rest of Views ' .
            'functionality, but the api needs to be changed as well');
    }




    /// BASE URL


    public function testGoodBaseUrls() {
        $goods = array(
            'https://uio.no/brukerinfo/',
            'https://brukerinfo.uio.no/',
            'https://brukerinfo.uio.no/',
            'https://cerebrum-test01.uio.no/',
            'https://brukerinfo.uio.no/www_docs',
            'https://uio.no/many/sub/dirs/',
            'https://uio.no:8080/many/sub/dirs/',
            'http://cerebrum@uio.no:8080/',
            # TODO: more types of valid urls?
        );
        foreach ($goods as $url) {
            $this->assertTrue(View::is_valid_baseurl($url),
                "Good base url '$url' wasn't accepted");
        }
    }

    public function testBadBaseUrls() {
        $bads = array(
            '',
            'https://brukerinfo uio.no/',       # whitespace
            "https://uio.no/dir\n",             # newlines
            'http://uio.no',                    # no path
            'brukerinfo.uio.no/',               # no protocol
            'https://brukerinfo.uio.no/?test',  # queries not allowed
            'https://uio.no/#title',            # no hashmark
            'https://uio.no/#',                 # no hashmark
            'https://uio.no/?',                 # no query
            "https://uio.no\0/dir",             # null byte
            "https://uio.no/\0/dir",             # null byte
            # TODO: more that should be tested?
        );
        foreach ($bads as $url) {
            $this->assertFalse(View::is_valid_baseurl($url),
                "Bad base url '$url' got accepted");
        }
    }

    public function testBaseUrlWithoutLastSlash() {
        View::setBaseUrl('https://uio.no/dir/');
        $this->assertEquals('https://uio.no/dir', View::getBaseUrl());
        View::setBaseUrl('https://uio.no/');
        $this->assertEquals('https://uio.no/', View::getBaseUrl());
    }











    // test these later, when got time:

    public function testChangeOfLanguage() {
        $this->markTestIncomplete('Need to check if language is changed correctly, both in View _and_ Text!');
    }
}


/**
 * Class for testing the View class, as View is abstract and has to be
 * subclassed.
 *
 * TODO: should change this a mockup, or rather use a real subclass of View, e.g 
 * View_uio.
 */
class TestView extends View {

    public function start() {
        if ($this->started) return;

        parent::start();
        echo "<html>\n";
    }

    public function end() {

        if ($this->ended) return;
        if (!$this->started) return;
        parent::end();
        echo "</html>\n";
    }

    /** For checking status of $this->started */
    public function isStarted() { return $this->started; }
    /** For checking status of $this->ended */
    public function isEnded()   { return $this->ended; }


}


?>
