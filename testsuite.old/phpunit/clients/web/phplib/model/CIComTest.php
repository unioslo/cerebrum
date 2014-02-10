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


class CIComTest extends PHPUnit_Framework_TestCase
{

    public static function setUpBeforeClass()
    {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/CerebrumCommunication.php';
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/CICom.php';

        # Disables the caching:
        ini_set('soap.wsdl_cache_enabled', '0');
    }

    public function setUp() {}


    public function testBadUrl()
    {
        // TODO: throw CerebrumConnectionException right away?
        $soap = new CICom('htp:// bad url ... :899x999');
    }

    /**
     * @expectedException CerebrumConnectionException
     */
    public function testNotConnectedCall()
    {
        $soap = new CICom('htp:// bad url ... :899x999');
        $soap->callThis();
    }


    public function testConstruct()
    {

        //$soap = new CICom('http://localhost:8999'); $this->markTestIncomplete('Not done yet');
        $this->markTestIncomplete();

    }

    public function testBadFunctionCall()
    {
        $soap = new CICom('this_url_should_be_ok');
        $ret = $soap->this1method_doenstexist();
        $this->markTestIncomplete();
    }

    public function testWebService()
    {
        $this->markTestIncomplete();

    }



}

?>
