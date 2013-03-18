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


/**
 * Class for testing the Text functionality that is specific to Brukerinfo.
 */
class BrukerinfoTextTest extends PHPUnit_Framework_TestCase
{

    public static function setUpBeforeClass()
    {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/view/Text.php';
        //define('HTTPS', 'on');

    }

    public function setUp()
    {
        Text::setLocation(TEST_PREFIX_CEREBRUM . '/clients/brukerinfo/data/txt/uio');
    }

    public function testAvailableLanguages()
    {
        $should_be_defined = array('en', 'nb');

        $available = Text::getAvailableLanguages();
        foreach ($should_be_defined as $lang) {
            $this->assertArrayHasKey($lang, $available,
                "Language '$lang' should be available"
            );
        }
    }

    public function testDefaultLanguage()
    {
        new Text(Text::getDefaultLanguage());
        $this->markTestIncomplete('Need to retrieve what the config define as the default language, but how to include the config file? A link constant?');
    }

    public function testConstructAllLanguages()
    {
        foreach (Text::getAvailableLanguages() as $lang => $desc) {
            $txt = new Text($lang);
        }
    }

    public function testAllKeysDefined()
    {
        $txt = new Text(Text::getDefaultLanguage());
        $def_keys = array_keys($txt->getAllText());
        sort($def_keys);

        foreach (Text::getAvailableLanguages() as $lang => $desc) {
            $txt = new Text($lang);
            $keys = array_keys($txt->getAllText());

            foreach ($def_keys as $k) {
                $pos = array_search($k, $keys, true);
                $this->assertTrue($pos !== false,
                    "Key '$k' not found in language '$lang'"
                );
                unset($keys[$pos]);
            }
            $this->assertEquals(array(), $keys,
                sprintf("Found keys not defined in lang '%s'",
                    Text::getDefaultLanguage()
                )
            );
        }
    }


    public function testXmlFiles()
    {
        $this->markTestIncomplete('Parse and check the validity');
    }
}
