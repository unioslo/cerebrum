<?php

class TextTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        # TODO: include like this, relative to where the tests are put, or just 
        # include directly, hoping that include_path has it? The latter doesn't 
        # guarantee that we include the correct file.
        include_once(TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/Text.php');

        $dir = self::example_path();

        @mkdir($dir);
        touch($dir . 'txt.testinst.en.xml');
        touch($dir . 'txt.testinst.nn-no.xml');
        touch($dir . 'txt.inst2.en.xml');
        touch($dir . 'txt.inst2.dk.xml');
    }

    public static function tearDownAfterClass() {

        # remove the example dir
        $dir = self::example_path();
        $d = opendir($dir);
        while (($l = readdir($d)) !== false) {
            if ($l == '..' || $l == '.') continue;
            unlink($dir . $l);
        }
        rmdir($dir);
        
    }

    public function setUp() {
        Text::setLocation(self::example_path());
        Text::setInstitution('testinst');
        Text::setDefaultLanguage('en');
        Text::flushCache();
    }
    public function tearDown() {
    }

    /**
     * Helper function to generate the path to the example files.
     */
    public static function example_path() {
        return sprintf('/tmp/%s_PHPUnit_TestText_examples/', $_SERVER['USER']);
    }



    /// TESTING CONSTRUCTIONS AND SETTINGS

    public function testConstruct() {
        $t = new Text('en', 'testinst', self::example_path(), 'en');
        $t = new Text('nn-no', 'testinst', self::example_path(), 'en');
        $t = new Text('en', 'testinst', self::example_path(), 'nn-no');
        $t = new Text('nn-no', 'testinst', self::example_path(), 'nn-no');
    }

    /*
     * @expectedException TextDirException
     */
    public function testConstructWithNotExistingTextDir() {
        $this->setExpectedException('TextDirException');

        $dir = '/tmp/testtesttest';
        $nr = 0;
        while (file_exists($dir.$nr)) $nr++;

        $t = new Text('en', 'testinst', $dir.$nr, 'en');
    }

    /**
     * @expectedException PHPUnit_Framework_Error
     */
    public function testConstructWithNotExistingTextFile() {
        $this->setExpectedException('PHPUnit_Framework_Error');
        $t = new Text('se', __FUNCTION__, self::example_path(), 'en');
    }

    public function testSetInstitution() {
        # TODO: functionality around the institution should be removed, and the 
        #       files should be in subdirectories of txt/ instead.
        $this->assertTrue(Text::setInstitution('inst2'));
        $this->assertEquals('inst2', Text::getInstitution(), 'Institution not set correctly');
        $this->markTestIncomplete('institution-specific behaviour should be removed from Text');
    }
    /**
     * We have no checks on the name of institutions by today, so this will 
     * fail. Should be changed, though, at least avoid strings like '..'.
     */
    public function testSetBadInstitution() {
        $this->assertTrue(Text::setInstitution(__FUNCTION__));
        $this->assertEquals(__FUNCTION__, Text::getInstitution(), 'Institution not set correctly');
    }

    public function testSetOkLocation() {
        $this->assertTrue(Text::setLocation(self::example_path()));
        $this->assertEquals(self::example_path(), Text::getLocation(), 'Language location not set correctly');
    }

    /**
     * @expectedException TextDirException
     */
    public function testSetBadLocation() {
        $t = new Text('en', 'testinst', null, 'en');
        $this->assertFalse($t->setLocation('/tmpklajsdflkjasdfklasjf/kljaskdf', 'Language location set to an invalid directory'));
    }
    public function testLocationWithAndWithoutSlash() {

        # check if location can end with / and not, and still get text.
        
        $this->markTestIncomplete('Not implemented yet.');
    }

    public function testBadLangfile() { 

        # should check if we get a file outside of text directories.
        
        $this->markTestIncomplete('This test has not been implemented yet.');
    }

    public function testGeneratingPath() {
        $inst = __FUNCTION__;
        $lang = 'no';
        $dir  = self::example_path();
        Text::setInstitution($inst);
        Text::setLocation($dir);
        $this->assertEquals(Text::generate_file_path($lang),
                            $dir . "txt.$inst.$lang.xml",
                            'Path to language dir not correctly generated');
    }

    /**
     * @expectedException LanguageTagInvalidException
     */
    public function testGeneratingInvalidPath() {
        $inst = __FUNCTION__;
        $lang = 'nono-notexisting-nono-2#1';
        $dir  = self::example_path();
        Text::setInstitution($inst);
        Text::setLocation($dir);
        // This should throw an exception, as the language tag is not valid:
        Text::generate_file_path($lang);
    }


    public function testTextParser() {

        $this->markTestIncomplete('Not implemented yet.');

    }

    /// TESTING LANGUAGES AND LANGUAGE SETTINGS

    /**
     * Test if valid language tags are accepted.
     */
    public function testValidLang() {
        $valids = array('en',
            'no',
            'NO',       # case insensitive
            'nn-no',    # regions
            'en-gb',
            'en-GB',
            'EN-gb');
        foreach ($valids as $v) {
            $this->assertTrue(Text::is_valid_tag($v));
        }
    }

    /**
     * TODO: Test test test om phpunit oppgir dette!
     */
    public function testInvalidLangs() {
        foreach(array('tjalla', 'tj-tjalla', 'no-nn', 'nn-no-en', 'nn ', ' no', 
                      '#', 'en-', '') as $invalid) {
            $this->assertFalse(Text::is_valid_tag($invalid));              
        }
    }

    public function testSetLang() {
        $t = new Text('nn-no', 'testinst', self::example_path(), 'en');
        #$t = new Text('en', 'inst', self::$examplesdir);
        #$t = new Text('tjalla', 'inst', self::$examplesdir, 'en');
        #$t = new Text('tjalla');
        $this->markTestIncomplete('Not implemented yet.');
    }

    public function testDefaultOKLanguage() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'nn-no';
        touch($dir . "txt.$lang.$inst.xml");
        Text::setDefaultLanguage($lang);
    }
    public function testDefaultNotexistingLanguage() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'nn-no';
        Text::setDefaultLanguage($lang);
    }
    /**
     * @expectedException PHPUnit_Framework_Error
     */
    public function testDefaultBadParsedLanguage() {
        Text::setDefaultLanguage('tjallabing');
    }


    public function testAvailableLangs() {
        $dir = self::example_path();
        $inst = 'uninst_notexisting';
        Text::setLocation($dir);
        Text::setInstitution($inst);

        # create some random language files
        $langs = array_rand(Text::$languages, 5);
        foreach ($langs as $l) touch($dir . "txt.$inst.$l.xml");

        $retlangs = Text::getAvailableLanguages();
        $this->assertEquals(sizeof($langs), sizeof($retlangs),
            'Not correct number of available languages');
        foreach ($langs as $l) {
            # languages names should be returned as values
            $this->assertTrue(!empty($retlangs[$l]));
        }
    }

    /**
     * When language files are created, but the language is not defined as a 
     * language, a warning will be triggered, but the undefined language will 
     * still be returned as ok, even though it has no name.
     *
     * @expectedException PHPUnit_Framework_Error
     */
    public function testUndefinedLang() {
        $dir = self::example_path();
        $inst = 'uninst_notexisting2';
        Text::setLocation($dir);
        Text::setInstitution($inst);

        # create some random language files
        $langs = array('tjalla', 'hottentottsk');
        foreach ($langs as $l) touch($dir . "txt.$inst.$l.xml");

        # This should trigger an error:
        $retlangs = Text::getAvailableLanguages();
        $this->assertEquals(sizeof($retlangs), sizeof($langs));
        foreach ($langs as $l) {
            # values are NULL when lang is not defined
            $this->assertTrue(array_key_exists($l, $retlangs));
        }
    }


    /// PARSE OF ACCEPT-LANGUAGE

    public function testParseEmptyLang() {
        $lang = Text::parseAcceptLanguage('');
        $this->assertEquals(sizeof($lang), 0);
    }
    public function testParseOneLang() {
        $lang = Text::parseAcceptLanguage('no');
        $this->assertEquals(sizeof($lang), 1);
    }
    public function testParseBadLangs() {
        $lang = Text::parseAcceptLanguage('enruskjd,tjallabing,asadfas');
        $this->assertEquals(sizeof($lang), 0);
    }
    public function testParseOkLang() {
        $lang = Text::parseAcceptLanguage('se');
        $this->assertEquals(sizeof($lang), 1);
        $this->assertTrue(in_array('se', $lang));
    }
    public function testParseManyLangs() {
        $lang = Text::parseAcceptLanguage('ru,en,no,en-gb,en-us');
        $this->assertEquals(sizeof($lang), 5);
        $this->assertTrue(in_array('en-gb', $lang));
        $this->assertEquals('ru',       $lang[0]);
        $this->assertEquals('en',       $lang[1]);
        $this->assertEquals('no',       $lang[2]);
        $this->assertEquals('en-gb',    $lang[3]);
        $this->assertEquals('en-us',    $lang[4]);
    }
    public function testParseRegionLangs() {
        $lang = Text::parseAcceptLanguage('nn-no,en-gb,en-us');
        $this->assertEquals(sizeof($lang), 3);
        $this->assertEquals($lang[0], 'nn-no');
        $this->assertEquals($lang[1], 'en-gb');
        $this->assertEquals($lang[2], 'en-us');
    }
    /**
     * Test parsing language tags with quality addition 'q=N', and not sorted.
     */
    public function testParseLangsWithQuality() {
        $lang = Text::parseAcceptLanguage('nn-no,tlh;q=1,q=0.7,en-gb;q=0.498,'.
                                          'da;q=0.,nb;q=0,en-us;q=0.1,en');
        $this->assertEquals(sizeof($lang), 5);
        $this->assertEquals($lang[0], 'nn-no');
        $this->assertEquals($lang[1], 'tlh');
        $this->assertEquals($lang[2], 'en'); # since 'en' has q=1, it should be sorted forward
        $this->assertEquals($lang[3], 'en-gb');
        $this->assertEquals($lang[4], 'en-us');
    }
    public function testParseLangsWithSpaces() {
        $lang = Text::parseAcceptLanguage('nn-no;q=0.7, en-gb;q=0.2, en-us;q= 0.5,en');
        $this->assertEquals(sizeof($lang), 4);
        $this->assertEquals($lang[0], 'en');    # q 1
        $this->assertEquals($lang[1], 'nn-no'); # q 0.7
        $this->assertEquals($lang[2], 'en-us'); # q 0.5
        $this->assertEquals($lang[3], 'en-gb'); # q 0.2
    }
    public function testParseLangsWithWildcard() {
        $lang = Text::parseAcceptLanguage('nn-no;q=0.7,en-gb;q=0.2,en-us;q=0.5,*;q=0.1');
        $this->assertEquals(sizeof($lang), 4);
        $this->assertEquals($lang[0], 'nn-no'); # q 0.7
        $this->assertEquals($lang[1], 'en-us'); # q 0.5
        $this->assertEquals($lang[2], 'en-gb'); # q 0.2
        $this->assertEquals($lang[3], '*');     # q 0.1
    }
    public function testParseLangsWithWildcards() {
        # check wildcards inside tags, e.g. 'nn-*'

        $this->markTestIncomplete('This test has not been implemented yet.');
    }
    public function testParseGarbageLang() {
        $lang = Text::parseAcceptLanguage('afdsfsdafsdafasdf');
        $this->assertEquals(sizeof($lang), 0);
        $lang = Text::parseAcceptLanguage('"!#&"_G,153t1');
        $this->assertEquals(sizeof($lang), 0);
        $lang = Text::parseAcceptLanguage('12345');
        $this->assertEquals(sizeof($lang), 0);
    }




    /**
     * @expectedException PHPUnit_Framework_Error
     */
    public function testGetTextNotExistingFile() {
        $dir = self::example_path();
        $inst = __FUNCTION__;

        $t = new Text('no', $inst, $dir);
    }

    /**
     * Getting text from a valid, standard xml file.
     */
    public function testGetText() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'no';
        #Text::setInstitution($inst);
        $xml =  <<<EOF
<txt lang="$lang">

            <TEST_TITLE>Title</TEST_TITLE>
            <TEST_AUTHOR>University of Oslo</TEST_AUTHOR>

            </txt>
EOF;
        file_put_contents($dir."txt.$inst.$lang.xml", $xml);

        $t = new Text($lang, $inst, $dir);
        $this->assertTrue($t->exists('test_title', $lang));
        $this->assertEquals('Title', $t->get('test_title'));
    }


    public function testGetTextFromEmptyFile() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'no';
        Text::setDefaultLanguage($lang);
        touch($dir."txt.$inst.$lang.xml");

        $t = new Text($lang, $inst, $dir);
        $this->assertFalse($t->exists('test_title', $lang));
    }

    /**
     * This log an notice about notexisting text.
     * TODO: how to test if it _actually_ logs it?
     * @expectedException PHPUnit_Framework_Error
     */
    public function testGetTextFromDefault() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'no';
        $deflang = 'en';
        Text::setDefaultLanguage($deflang);

        touch($dir."txt.$inst.$lang.xml");

        $teststring = "Test 5 4 3 ... 1.";
        $xml =  "<txt lang=\"$lang\">" . 
                "<VarThis>$teststring </VarThis>" . 
                "</txt>";
        file_put_contents($dir."txt.$inst.$deflang.xml", $xml);
        $t = new Text($lang, $inst, $dir);

        $this->assertFalse($t->exists('varthis', $lang, true));
        $this->assertTrue($t->exists('varthis', $lang, false));
        $this->assertEquals($t->get('varthis'), $teststring, 
                            'Text not returned in default language');
    }

    public function testGetTextWhitespace() {
        $dir = self::example_path();
        $inst = __FUNCTION__;
        $lang = 'no';

        # lines and double spaces should be removed, in addition to trimming
        $teststring = "   Test 5 \n     4 3 ... 1.   ";

        $xml =  "<txt >" .
                "<variabl> $teststring </variabl>" . 
                "</txt>";
        file_put_contents($dir."txt.$inst.$lang.xml", $xml);
        $t = new Text($lang, $inst, $dir);
        $this->assertEquals(trim($teststring), $t->get('variabl'),
                            'Whitespace not fixed correctly');
    }


    /**
     * Need to test the getValue, but since it should be done in another way 
     * than before, we only test that it works in general by now.
     */
    public function testGetValue() {

        $this->markTestIncomplete('Need to check that values work correctly.');

    }

    public function testGetValueSetGet() {

        $this->markTestIncomplete('Need to check the functionality of setting' .
            ' and getting the values used in the text, but have to figure out' .
            ' how first...');

    }


    public function testChangeOf() {
        $this->markTestIncomplete('Need to check that values work correctly.');
    }

}
