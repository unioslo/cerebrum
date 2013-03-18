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


class TextTest extends PHPUnit_Framework_TestCase
{

    public static function setUpBeforeClass()
    {
        # TODO: include like this, relative to where the tests are put, or just 
        # include directly, hoping that include_path has it? The latter doesn't 
        # guarantee that we include the correct file.
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/Text.php';
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/controller/InitBase.php';

        # create directory for the test language files 
        @mkdir(self::example_path());
    }

    public static function tearDownAfterClass()
    {
        # remove the text examples dir
        self::help_rmdir(self::example_path());
        
    }

    public function setUp()
    {
        Text::flushCache();
        $dir = self::example_path();
        @mkdir($dir . '/testinst');
        touch($dir . '/testinst/en.xml');
        touch($dir . '/testinst/nn-no.xml');

        @mkdir($dir . '/inst2');
        touch($dir . '/inst2/en.xml');
        touch($dir . '/inst2/dk.xml');

        @mkdir($dir . '/empty');
    }
    public function tearDown()
    {
        $dir = self::example_path();
        self::help_rmdir($dir . '/testinst');
        self::help_rmdir($dir . '/inst2');
    }

    /**
     * Helper function to remove a directory recursive. Use with caution, and 
     * only for files that has been created by the test environment!
     */
    public static function help_rmdir($dir)
    {
        $d = opendir($dir);
        while (($l = readdir($d)) !== false) {
            if ($l == '..' || $l == '.') continue;
            if (is_dir("$dir/$l")) self::help_rmdir("$dir/$l");
            else unlink("$dir/$l");
        }
        rmdir($dir);
    }

    /**
     * Helper function to generate the path to the example files.
     */
    public static function example_path()
    {
        return sprintf('/tmp/%s_PHPUnit_TestText_examples', $_SERVER['USER']);
    }






    /// TESTING CONSTRUCTOR AND STATIC SETTINGS ///
    ///////////////////////////////////////////////

    public function testConstruct()
    {
        $dir = self::example_path() . '/testinst';

        $t = new Text('en',     $dir);
        $t = new Text('nn-no',  $dir);
        $t = new Text('en',     $dir);
        $t = new Text('nn-no',  $dir);
    }

    /**
     * Should throw error:
     * @expectedException TextDirException
     */
    public function testConstructWithNotExistingTextDir()
    {
        $dir = self::example_path() . '/notexisting_test';

        $t = new Text('en', $dir);
    }

    /**
     * @expectedException TextFileException
     */
    public function testConstructWithNotExistingTextFile()
    {
        $dir = self::example_path() . '/testinst';

        Text::setLocation($dir);
        $t = new Text('cs', $dir);
    }

    public function testConstructWithNotExistingDefaultTextFile()
    {
        $dir = self::example_path() . '/testinst';

        Text::setLocation($dir);
        $t = new Text('en', $dir); # first one that works, as 'en' exists
        try {
            $t = new Text('en', $dir, 'cs');
        } catch(TextFileException $e) {
            return true;
        }
        $this->fail('Construct should fail if default language file doesn\'t exist');
    }

    public function testNoDefaultLanguage()
    {
        $this->assertTrue((bool) Text::getDefaultLanguage(),
                    'Default language should not be empty');
    }

    /// SET/GET LOCATION

    public function testSetOkLocation()
    {
        $this->assertTrue(Text::setLocation(self::example_path() . '/inst2'));
        $this->assertEquals(self::example_path().'/inst2', Text::getLocation(),
            'Language location not set correctly');
    }

    /**
     * @expectedException TextDirException
     */
    public function testSetBadLocation()
    {
        Text::setLocation(self::example_path().'/tmpklajsdflkjasdfklasjf/kljaskdf');
    }

    public function testSetBadLocationNotChanging()
    {
        $dir = self::example_path() . '/inst2';
        Text::setLocation($dir);
        try {
            Text::setLocation(self::example_path().'/tmpklajsdflkjasdfklasjf/kljaskdf');
        } catch(TextDirException $e) {
            $this->assertEquals($dir, Text::getLocation(),
                'Language location has changed, should not happen.');
            return true;
        }
        $this->fail('Setting nonexisting location didn\'t throw TextDirException.');
    }

    public function testLocationWithoutSlashLast()
    {
        $dir = self::example_path() . '/' . __FUNCTION__ . 'test1';
        mkdir($dir);
        Text::setLocation($dir);
        $this->assertEquals($dir, Text::getLocation(), 
            'Location not set correctly');
    }
    public function testLocationWithSlashLast()
    {
        $dir = self::example_path() . '/' . __FUNCTION__ . 'test1';
        mkdir($dir);
        Text::setLocation($dir . '/');
        $this->assertEquals($dir, Text::getLocation(), 
            'Location path should not end with /');
    }


    /// GENERATE_FILE_PATH


    public function testGeneratingPath()
    {
        $dir  = self::example_path() . '/inst2';
        $lang = 'no';
        Text::setLocation($dir);
        $this->assertEquals("$dir/$lang.xml", Text::generate_file_path($lang), 
                            'Path to language wasn\'t correctly generated');
    }

    /**
     * It's not possible to generate a valid path as long as setting the path 
     * throws an exception.
     */
    public function testGeneratingInvalidPath()
    {
        $dir  = self::example_path() . '/' . __FUNCTION__;
        # directory not created
        $lang = 'no';

        try {
            Text::setLocation($dir);
        } catch(TextDirException $e) {
            return true;
        }
        $p = Text::generate_file_path($lang);
        $this->fail('Setting location to a nonexisting dir didn\'t throw an ' .
                    "LanguageTagInvalidException, path generated to '$p'");
    }




    /// LANGUAGE TAGS

    /**
     * Test if valid language tags are accepted.
     */
    public function testValidLanguageTags()
    {
        $valids = array('en', 'no', 'NO', 'nn-no', 'en-gb', 'en-GB', 'EN-gb');
        foreach ($valids as $v) $this->assertTrue(Text::isValidTag($v));
    }

    public function testInvalidLanguageTags()
    {
        foreach(array('tjalla', 'tj-tjalla', 'no-nn', 'nn-no-en', 'nn ', ' no', 
                 '*', '#', 'en-', '', '..', '../', '/..', '/../') as $invalid) {
            $this->assertFalse(Text::isValidTag($invalid));              
        }
    }


    /// SET/GET LANGUAGE
    
    public function testSetOkLanguage()
    {
        $t = new Text('nn-no', self::example_path() . '/testinst');
        $t->setLang('en');
        $t->setLang('nn-no');
    }

    /**
     * @expectedException LanguageTagInvalidException
     */
    public function testSetBadLanguage()
    {
        $t = new Text('nn-no', self::example_path() . '/testinst');
        $t->setLang('tjalla');
        $this->fail('Setting bad language tags should throw LanguageTagInvalidException');
    }

    /**
     * @expectedException TextFileException
     */
    public function testSetLanguageWithoutFile()
    {
        $t = new Text('nn-no', self::example_path() . '/testinst');
        $t->setLang('sk');
        $this->fail('Setting language with nonexisting file should throw TextFileException');
    }

    /// SET/GET DEFAULT LANGUAGE

    public function testDefaultLanguage()
    {
        $dir = self::example_path() . '/testinst';
        Text::setLocation($dir);
        Text::setDefaultLanguage('nn-no');
    }

    /**
     * @expectedException LanguageTagInvalidException
     */
    public function testDefaultBadParsedLanguage()
    {
        Text::setDefaultLanguage('tjallabing');
    }

    public function testSetDefaultBadLanguageNotChanged()
    {
        Text::setDefaultLanguage('nn-no');
        try {
            Text::setDefaultLanguage('tjallabingo');
        } catch (LanguageTagInvalidException $e) {
            $this->assertEquals('nn-no', Text::getDefaultLanguage(),
                'Default language has changed, which it should not');
            return true;
        }
        $this->fail('Setting bad default language tag should throw LanguageTagInvalidException');
    }

    public function testSetDefaultBadLanguageByConstruct()
    {
        $dir = self::example_path() . '/testinst';
        Text::setLocation($dir);
        Text::setDefaultLanguage('en');
        try {
            $t = new Text('nn-no', $dir, 'nnnonon');
        } catch (LanguageTagInvalidException $e) {
            $this->assertEquals('en', Text::getDefaultLanguage(),
                'Default language has changed, which it should not have');
            return true;
        }
        $this->fail('Setting bad language tags should throw LanguageTagInvalidException');
    }

    /**
     * @expectedException TextFileException
     */
    public function testDefaultLanguageWithoutFile()
    {
        $dir = self::example_path() . '/testinst';
        Text::setLocation($dir);
        Text::setDefaultLanguage('se');
        $this->fail('Setting default language with nonexisting file should throw TextFileException');
    }

    public function testDefaultLanguageWithoutFileNotChanged()
    {
        $dir = self::example_path() . '/testinst';
        Text::setLocation($dir);
        Text::setDefaultLanguage('nn-no');
        try {
            Text::setDefaultLanguage('se');
        } catch (TextFileException $e) {
            $this->assertEquals('nn-no', Text::getDefaultLanguage(), 
                'Default language has changed, which it should not have');
            return true;
        }
        $this->fail('Setting default language with nonexisting file should throw TextFileException');
    }



    /// AVAILALBLE LANGUAGES

    public function testAvailableLangs()
    {
        $dir = self::example_path() . '/new';
        mkdir($dir);
        Text::setLocation($dir);

        # create some random language files
        $langs = array_rand(Text::$languages, 5);
        foreach ($langs as $l) touch($dir . "/$l.xml");

        $retlangs = Text::getAvailableLanguages();
        $this->assertEquals(sizeof($langs), sizeof($retlangs),
            'Not correct number of available languages returned');
        foreach ($langs as $l) {
            $this->assertTrue(!empty($retlangs[$l]), 
                'Available language wasn\'t returned from getAvailableLanguages');
        }
    }

    public function testNotAvailableLangs()
    {
        Text::setLocation(self::example_path() . '/empty');
        $langs = Text::getAvailableLanguages();
        $this->assertEquals(0, sizeof($langs));
    }

    /**
     * When language files exists, but the language is not a valid language tag,
     * a warning will be triggered, but it will still be returned as ok. It has 
     * no defined name, though, so the tag is returned.
     *
     * @expectedException PHPUnit_Framework_Error
     */
    public function testUndefinedLang()
    {
        $dir = self::example_path() . '/empty';
        Text::setLocation($dir);
        # create some random language files
        $langs = array('tjalla', 'hottentottsk');
        foreach ($langs as $l) touch($dir . "/$l.xml");

        $retlangs = Text::getAvailableLanguages();
        echo "\nLogged now? Or has the exception occured yet?\n\n";

        $this->assertEquals(sizeof($retlangs), sizeof($langs));
        foreach ($langs as $l) {
            # values are NULL when lang is not defined
            $this->assertTrue(array_key_exists($l, $retlangs),
                'Undefined, but existing, languages should be returned by getAvailableLanguages');
            $this->assertEquals($l, $retlangs[$l],
                'For undefined languages, the tag should be returned as the name');
        }
    }


    /// PARSE OF ACCEPT-LANGUAGE

    public function testParseEmptyLang()
    {
        $lang = Text::parseAcceptLanguage('');
        $this->assertEquals(0, sizeof($lang));
    }
    public function testParseOneLang()
    {
        $lang = Text::parseAcceptLanguage('no');
        $this->assertEquals(1, sizeof($lang));
        $this->assertEquals('no', $lang[0]);
    }
    public function testParseBadLangs()
    {
        $lang = Text::parseAcceptLanguage('enruskjd,tjallabing,asadfas');
        $this->assertEquals(0, sizeof($lang));
    }
    public function testParseManyLangs()
    {
        $lang = Text::parseAcceptLanguage('ru,en,no,en-gb,en-us');
        $this->assertEquals(5, sizeof($lang), 'Languages not parsed correctly');
        $this->assertEquals('ru',       $lang[0]);
        $this->assertEquals('en',       $lang[1]);
        $this->assertEquals('no',       $lang[2]);
        $this->assertEquals('en-gb',    $lang[3]);
        $this->assertEquals('en-us',    $lang[4]);
    }

    public function testParseLangsWithQuality()
    {
        $lang = Text::parseAcceptLanguage('tlh;q=1,no;q=0.7,en-gb;q=0.498,'.
                                          'nb;q=0.01,en-us;q=0.');
        $this->assertEquals(4, sizeof($lang), 
                        'Not correct number of languages returned');
        $this->assertEquals('tlh',      $lang[0]);
        $this->assertEquals('no',       $lang[1]);
        $this->assertEquals('en-gb',    $lang[2]);
        $this->assertEquals('nb',       $lang[3]);
    }

    /**
     * Test parsing language tags with quality addition 'q=N', and which needs 
     * to be sorted.
     */
    public function testParseLangsWithQualityUnsorted()
    {
        $lang = Text::parseAcceptLanguage('nn-no,tlh;q=1,q=0.7,en-gb;q=0.498,'.
                                          'da;q=0.,nb;q=0,en-us;q=0.1,en');
        $this->assertEquals(5, sizeof($lang));
        $this->assertEquals('nn-no',    $lang[0]);
        $this->assertEquals('tlh',      $lang[1]);
        $this->assertEquals('en',       $lang[2]);
        $this->assertEquals('en-gb',    $lang[3]);
        $this->assertEquals('en-us',    $lang[4]);
    }
    public function testParseLangsWithSpaces()
    {
        $lang = Text::parseAcceptLanguage('nn-no;q=0.7, en-gb;q=0.2, en-us;q= 0.5,en');
        $this->assertEquals(4, sizeof($lang));
        $this->assertEquals('en',       $lang[0]); # q 1
        $this->assertEquals('nn-no',    $lang[1]); # q 0.7
        $this->assertEquals('en-us',    $lang[2]); # q 0.5
        $this->assertEquals('en-gb',    $lang[3]); # q 0.2
    }
    public function testParseLangsWithWildcard()
    {
        $lang = Text::parseAcceptLanguage('nn-no;q=0.7,en-gb;q=0.2,en-us;q=0.5,*;q=0.1');
        $this->assertEquals(4, sizeof($lang));
        $this->assertEquals('nn-no',    $lang[0]); # q 0.7
        $this->assertEquals('en-us',    $lang[1]); # q 0.5
        $this->assertEquals('en-gb',    $lang[2]); # q 0.2
        $this->assertEquals('*',        $lang[3]); # q 0.1
    }
    public function testParseLangsWithWildcards()
    {
        $lang = Text::parseAcceptLanguage('nn-no,en-*;q=0.2,no;q=0.1');
        $this->assertEquals(3, sizeof($lang));
        $this->assertEquals('nn-no',    $lang[0]); # q 1.0
        $this->assertEquals('en-*',     $lang[1]); # q 0.2
        $this->assertEquals('no',       $lang[2]); # q 0.1
    }
    public function testParseGarbageLang()
    {
        $lang = Text::parseAcceptLanguage('afdsfsdafsdafasdf');
        $this->assertEquals(sizeof($lang), 0);
        $lang = Text::parseAcceptLanguage('"!#&"_G,153t1');
        $this->assertEquals(sizeof($lang), 0);
        $lang = Text::parseAcceptLanguage('12345,asdfasdfas');
        $this->assertEquals(sizeof($lang), 0);
    }


    /**
     * Getting text from a valid, standard xml file.
     */
    public function testGetText()
    {
        $dir = self::example_path() . '/empty';
        $lang = 'no';
        $xml =  <<<EOF
            <txt lang="$lang">

            <TEST_TITLE>Title</TEST_TITLE>
            <TEST_AUTHOR>University of 
Oslo</TEST_AUTHOR>

            </txt>
EOF;
        file_put_contents($dir."/$lang.xml", $xml);

        $t = new Text($lang, $dir);
        $this->assertTrue($t->exists('test_title', $lang),
            'Text from xml file wasn\'t returned');

        $this->assertEquals('Title', $t->get('test_title'),
            'Returned text is not equal with what is defined in the xml');

        $this->assertEquals("University of \nOslo", $t->get('test_author'),
            'Returned text is not equal with what is defined in the xml');

        $this->assertFalse($t->exists('test_notexissting', $lang));
    }


    public function testGetTextFromEmptyFile()
    {
        $dir = self::example_path() . '/empty';
        $lang = 'no';
        touch($dir."/$lang.xml");
        Text::setDefaultLanguage($lang);
        $t = new Text($lang, $dir);
        $this->assertEquals(false, $t->exists('test', $lang));
    }

    /**
     * This logs a notice about notexisting text.
     *
     * TODO: how to test if it _actually_ logs it?
     * @expectedException PHPUnit_Framework_Error
     */
    public function testGetTextFromDefault()
    {
        $dir = self::example_path() . '/empty';
        $lang = 'no';
        $deflang = 'en';
        touch($dir."/$lang.xml");

        $teststring = "Test 5 4 3 ... 1.";
        $xml =  "<txt lang=\"$lang\">" . 
                "<VarThis>$teststring </VarThis>" . 
                "</txt>";
        file_put_contents($dir."/$deflang.xml", $xml);

        $t = new Text($lang, $dir, $deflang);

        $this->assertFalse($t->exists('varthis', $lang, true),
            'Text should not be returned when only searching in set language file');
        $this->assertTrue($t->exists('varthis', $lang, false),
            'Text should be returned when using default language as backup');
        $this->assertEquals($teststring, $t->get('varthis'),
            'Text not correctly returned from default language');
    }

    public function testGetTextTrimmed()
    {
        $dir = self::example_path() . '/' . __FUNCTION__;
        mkdir($dir);
        $lang = 'no';

        $teststring = "   Test 5 \n     4 3 ... 1.   ";

        $xml =  "<txt >" .
                "<variabl> $teststring </variabl>" . 
                "</txt>";
        file_put_contents($dir."/$lang.xml", $xml);
        $t = new Text($lang, $dir);
        $this->assertEquals(trim($teststring), $t->get('variabl'),
                            'Text not trimmed correctly');
    }

    public function testTextParser()
    {

        $this->markTestIncomplete('Not implemented yet.');

    }


    /**
     * Need to test the getValue, but since it should be done in another way 
     * than before, we only test that it works in general by now.
     */
    public function testGetValue()
    {

        $this->markTestIncomplete('Need to check that values work correctly.');

    }

    public function testGetValueSetGet()
    {

        $this->markTestIncomplete('Need to check the functionality of setting' .
            ' and getting the values used in the text, but have to figure out' .
            ' how first...');

    }


    public function testChangeOf()
    {
        $this->markTestIncomplete('Need to check that values work correctly.');
    }

}
