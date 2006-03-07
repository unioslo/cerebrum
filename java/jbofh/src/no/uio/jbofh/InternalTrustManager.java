/*
 * Copyright 2002, 2003, 2004 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

/*
 * BofdConnection.java
 *
 * Created on November 19, 2002, 11:48 AM
 */

package no.uio.jbofh;

import java.io.IOException;
import java.io.InputStream;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.Date;
import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Vector;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

import org.apache.log4j.Category;
import org.apache.xmlrpc.XmlRpcClient;
import org.apache.xmlrpc.XmlRpcException;

/**
 * Specialized TrustManager called by the SSLSocket framework when
 * validating server certificate.
 */
class InternalTrustManager implements X509TrustManager {
    static X509Certificate serverCert = null;

    InternalTrustManager() throws IOException, CertificateException {
        readServerCert();
    }

    private void readServerCert() throws IOException, CertificateException {
        InputStream inStream = ResourceLocator.getResource(this, "/cacert.pem").openStream();
        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        X509Certificate cert = (X509Certificate)cf.generateCertificate(inStream);
        inStream.close();
        serverCert = cert;
    }

    public void checkClientTrusted( X509Certificate[] cert, String str) {
        // Not implemented (not called by framework for this client)
    }
    
    public void checkServerTrusted( X509Certificate[] cert, String str) 
        throws CertificateException {
        Date date = new Date();
        if(cert == null || cert.length == 0)
            throw new IllegalArgumentException("null or zero-length certificate chain");
        if(str == null || str.length() == 0)
            throw new IllegalArgumentException("null or zero-length authentication type");
        for(int i = 0; i < cert.length; i++) {
            X509Certificate parent;
            if(i + 1 >= cert.length) {
                parent = cert[i];
            } else {
                parent = cert[i+1];
            }

            if(! parent.getSubjectDN().equals(cert[i].getIssuerDN())) {
                throw new CertificateException("Incorrect issuer for server cert");
            }
            cert[i].checkValidity(date);
            parent.checkValidity(date);
            try {
                cert[i].verify(parent.getPublicKey());
            } catch (Exception e) {
                throw new CertificateException("Bad server certificate: "+e);
            }
            if(cert[i].getIssuerDN().equals(serverCert.getSubjectDN())) {
                // Issuer is trusted
                try {
                    cert[i].verify(serverCert.getPublicKey());
                    serverCert.checkValidity(date);
                } catch (Exception e) {
                    System.out.println("bas");
                    throw new CertificateException("Bad server certificate: "+e);
                }
                return;
            }
        }
    }
    
    public X509Certificate[] getAcceptedIssuers() {
        X509Certificate[] ret = new X509Certificate[1];
        ret[0] = serverCert;
        return ret;
    }
}

// arch-tag: e689905d-cdab-4978-9ea4-28e1647b512e
