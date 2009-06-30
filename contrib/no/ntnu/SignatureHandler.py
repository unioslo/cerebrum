# -*- encoding: utf-8 -*-
import sha

import binascii
import base64
import time
import random

class SignatureHandler(object):

    OASIS_PREFIX='http://docs.oasis-open.org/wss/2004/01/oasis-200401'

    SEC_NS = OASIS_PREFIX + '-wss-wssecurity-secext-1.0.xsd'

    UTIL_NS = OASIS_PREFIX + '-wss-wssecurity-utility-1.0.xsd'

    PASSWORD_DIGEST_TYPE = OASIS_PREFIX + '-wss-username-token-profile-1.0#PasswordDigest'

    PASSWORD_PLAIN_TYPE = OASIS_PREFIX + '-wss-username-token-profile-1.0#PasswordText'

    def __init__(self, user, password, useDigest=False):
        self._user = user
        self._created=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time()))
        self._nonce = sha.new(str(random.random())).digest()
        if (useDigest):
            self._passwordType = self.PASSWORD_DIGEST_TYPE
            digest = sha.new(self._nonce + self._created + password).digest()

            # binascii.b2a_base64 adds a newline at the end
            self._password = binascii.b2a_base64(digest)[:-1]
        else:
            self._passwordType = self.PASSWORD_PLAIN_TYPE
            self._password = password

    def sign(self,soapWriter):

        # create element
        securityElem = soapWriter._header.createAppendElement('', 'wsse:Security')

        securityElem.node.setAttribute('xmlns:wsse', self.SEC_NS)
        securityElem.node.setAttribute('SOAP-ENV:mustunderstand', '1')

        # create element
        usernameTokenElem = securityElem.createAppendElement('',
            'wsse:UsernameToken')

        usernameTokenElem.node.setAttribute('xmlns:wsse', self.SEC_NS)
        usernameTokenElem.node.setAttribute('xmlns:wsu', self.UTIL_NS)

        # create element
        usernameElem = usernameTokenElem.createAppendElement('',
            'wsse:Username')
        ## usernameElem.node.setAttribute('xmlns:wsse', self.SEC_NS)

        # create element
        passwordElem = usernameTokenElem.createAppendElement('',
            'wsse:Password')
        passwordElem.node.setAttribute('xmlns:wsse', self.SEC_NS)
        passwordElem.node.setAttribute('Type', self._passwordType)

        # create element
        nonceElem = usernameTokenElem.createAppendElement('', 'wsse:Nonce')
        nonceElem.node.setAttribute('xmlns:wsse', self.SEC_NS)

        # create element
        createdElem = usernameTokenElem.createAppendElement('',
                                                            'wsse:Created')
        createdElem.node.setAttribute('xmlns:wsse', self.UTIL_NS)

        # put values in elements
        usernameElem.createAppendTextNode(self._user)
        passwordElem.createAppendTextNode(self._password)
        # binascii.b2a_base64 adds a newline at the end
        nonceElem.createAppendTextNode(binascii.b2a_base64(self._nonce)[:-1])
        createdElem.createAppendTextNode(self._created)

    def verify(self,soapWriter):
        pass

