#! /usr/bin/env python
# -*- encoding: latin-1 -*-
import sys
import os
import string
import getopt

# ZSI er soap-biblioteket
import ZSI
# WSIdm er generert fra wsdl2py -u <url til wsdl-fil> && mv Serve_services.py WSIdm.py
import WSIdm

# En locator hjelper oss sikkert med å finne WebService-serveren
locator = WSIdm.ServeLocator()

# Endrer Soap-envelope
ZSI.client._AuthHeader = """
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>%s</wsse:Username>
        <wsse:Password>%s</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
"""

# Konverter til å hente fra config-modulen?
user = 'JossiBjorling'
passwd = '3RT-syP0Z'
tracefile = None
ssl = 'yes' 

# Her lurer vi ZSI litt for å få bruke ZSI.client._AuthHeader
kw = {'tracefile': tracefile,'ssl': ssl,'auth':(ZSI.auth.AUTH.zsibasic,user,passwd)}

def main():
    global locator

    print "Type birthdate (6 digits):"
    birthdate = sys.stdin.readline()
    print "Type national identitynumber (5 digits):"
    ssn =  sys.stdin.readline()
    print "Type studentnumber:"
    snr = sys.stdin.readline()
    print "Type pinkode (4 digits)"
    pin = sys.stdin.readline()

    portType = locator.getServe(**kw)
    req = WSIdm.kjerneCheckIdRequestWrapper()

    # Set input-arguments
    req._studentId = int(snr.strip())
    req._ssn = int(ssn.strip())
    req._birthDate = int(str(birthdate.strip()))
    req._pin = str(pin.strip())

    # Call method after arguments has been set
    res = portType.kjerneCheckId(req)
    result = res._kjerneCheckIdReturn
    fnr = str(birthdate.strip())+str(ssn.strip())
    print "Retur fra WSIdm: %s" % str(result)
    if fnr == result:
        print "We even got a matching fnr in return"
    else:
        print "Input and output is differing."
        print "Input: %s. Output %s" % (fnr,result)

def checkIdentity(birthdate, ssn, studentnr, pin):
    portType = locator.getServe(**kw)
    req = WSIdm.kjerneCheckIdRequestWrapper()

    req._studentId = int(studentnr.strip())
    req._ssn = int(ssn.strip())
    req._birthDate = int(str(birthdate.strip()))
    req._pin = str(pin.strip())

    # Call method after arguments has been set
    res = portType.kjerneCheckId(req)
    result = res._kjerneCheckIdReturn
    return result

if __name__ == '__main__':
    main()
