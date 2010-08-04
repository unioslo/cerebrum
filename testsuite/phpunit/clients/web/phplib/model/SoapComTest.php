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


class SoapComTest extends PHPUnit_Framework_TestCase {

    public static function setUpBeforeClass() {
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/CerebrumCommunication.php';
        include_once TEST_PREFIX_CEREBRUM . '/clients/web/phplib/model/SoapCom.php';
    }

    public function setUp() {}


    public function testConstruct() {

        $soap = new SoapCom('url to wsdl file');
        $this->markTestIncomplete('Not done yet');

    }

    public function testWebService() {
        $this->markTestIncomplete('Not done yet');

    }


}

?>
