#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
""" Tests for the Ephorte WS client - Cerebrum/modules/no/uio/EphorteWS.py."""

import unittest2 as unittest

import os

# Avoid getting flooded by suds log messages
import logging
logging.getLogger('suds').setLevel(logging.ERROR)

from Cerebrum.modules.no.uio import EphorteWS


class EphorteWSTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """ Set up this TestCase module.

        This setup code sets up shared objects between each tests. This is done
        *once* before running any of the tests within this class.

        """
        wsdl = os.getenv('CONFIG_EWS_WSDL')
        if not wsdl:
            raise unittest.SkipTest('EWS WSDL file not defined: %s' % wsdl)
        elif not os.path.exists(wsdl):
            raise unittest.SkipTest('EWS WSDL file does not exist: %s' % wsdl)

        cls._c = EphorteWS.Cerebrum2EphorteClient(
            'file://%s' % wsdl, 'customer_id', 'database', timeout=None)

    def test_get_user_details(self):
        """Test the return of the get_user_details call.

        This is done by simulating the actual call."""

        # Test actual call that should be sucessfull.
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
   <s:Body>
      <GetUserDetailsResponse xmlns="http://Cerebrum2Ephorte/Service">
         <GetUserDetailsResult
                xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
            <ErrorMessage/>
            <HasError>false</HasError>
            <OccurencesFound i:nil="true"/>
            <User>
               <City>OSLO</City>
               <EmailAddress>jo.sama@usit.uio.no</EmailAddress>
               <FirstName>Jo</FirstName>
               <FullName>Jo Sama</FullName>
               <Initials>jsama</Initials>
               <LastName>Sama</LastName>
               <MiddelName i:nil="true"/>
               <Mobile i:nil="true"/>
               <StreetAddress>Gaustadalleen 23 A
Kristen Nygaards hus</StreetAddress>
               <Telephone>+4722852707</Telephone>
               <UserId>JSAMA@UIO.NO</UserId>
               <ZipCode>0373</ZipCode>
            </User>
            <UserAuthorizations>
               <EphorteUserAuthorization>
                  <AccessCodeId>AR</AccessCodeId>
                  <IsAutorizedForAllOrgUnits>false</IsAutorizedForAllOrgUnits>
                  <OrgId i:nil="true"/>
               </EphorteUserAuthorization>
               <EphorteUserAuthorization>
                  <AccessCodeId>UA</AccessCodeId>
                  <IsAutorizedForAllOrgUnits>false</IsAutorizedForAllOrgUnits>
                  <OrgId i:nil="true"/>
               </EphorteUserAuthorization>
            </UserAuthorizations>
            <UserRoles/>
         </GetUserDetailsResult>
      </GetUserDetailsResponse>
   </s:Body>
</s:Envelope>"""
        self._c._clear_injections()
        self._c._set_injection_reply(response)
        r = self._c.get_user_details('jsama@uio.no')

        # Check that the data structure returned from the EphorteWS-client is
        # equal to what we expect.
        self.assertEqual(
            r, ({'City': u'OSLO',
                 'StreetAddress': u'Gaustadalleen 23 A\nKristen Nygaards hus',
                 'FirstName': u'Jo',
                 'Mobile': None,
                 'LastName': u'Sama',
                 'UserId': u'JSAMA@UIO.NO',
                 'ZipCode': u'0373',
                 'Telephone': u'+4722852707',
                 'MiddelName': None,
                 'EmailAddress': u'jo.sama@usit.uio.no',
                 'FullName': u'Jo Sama',
                 'Initials': u'jsama'},
                [{'AccessCodeId': u'AR',
                  'IsAutorizedForAllOrgUnits': False,
                  'OrgId': None},
                 {'AccessCodeId': u'UA',
                  'IsAutorizedForAllOrgUnits': False,
                  'OrgId': None}],
                []),
            "User details returned by get_user_details not as expected")

        # Test nonexistent user fault.
        response = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
    <s:Body>
        <GetUserDetailsResponse xmlns="http://Cerebrum2Ephorte/Service">
            <GetUserDetailsResult
                    xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
                <ErrorMessage>Error Cerebrum2Ephorte Web Service method """ + \
                   """GetUserDetails()! Message: UserId not found in """ + \
                   """Ephorte: js@uio.no</ErrorMessage>
                <HasError>true</HasError>
                <OccurencesFound i:nil="true"/>
                <User i:nil="true"/>
                <UserAuthorizations i:nil="true"/>
                <UserRoles i:nil="true"/>
            </GetUserDetailsResult>
        </GetUserDetailsResponse>
    </s:Body>
</s:Envelope>"""

        self._c._clear_injections()
        self._c._set_injection_reply(response)

        try:
            self._c.get_user_details('js@uio.no')
        except EphorteWS.EphorteWSError:
            # TODO: Should we actually verify how the exception message looks?
            pass
        else:
            self.fail("get_user_details: Nonexistent user "
                      "does not result in exception.")
