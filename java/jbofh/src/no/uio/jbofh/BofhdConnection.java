/*
 * BofdConnection.java
 *
 * Created on November 19, 2002, 11:48 AM
 */

package no.uio.jbofh;
import org.apache.xmlrpc.XmlRpcException;
import org.apache.xmlrpc.XmlRpcClient;
import org.apache.xmlrpc.XmlRpc;
import org.apache.log4j.Category;
import java.util.Arrays;
import java.util.Vector;
import java.util.Hashtable;
import java.util.Enumeration;
import java.io.*;

import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

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
	/* This implementation is rather primitive in that we only
	 * allow a keychain length of one.
	 */
	if(cert.length != 1)
	    throw new CertificateException("Unexpected keychain length");

	if(! serverCert.getSubjectDN().equals(cert[0].getIssuerDN()))
	    throw new CertificateException("Incorrect issuer for server cert");

	try {
	    cert[0].verify(serverCert.getPublicKey());
	} catch (Exception e) {
	    throw new CertificateException("Bad server certificate: "+e);
	}
    }
    
    public X509Certificate[] getAcceptedIssuers() {
	X509Certificate[] ret = new X509Certificate[1];
	ret[0] = serverCert;
	return ret;
    }
}

/**
 *
 * @author  runefro
 */
public class BofhdConnection {
    Category logger;
    XmlRpcClient xmlrpc;
    String sessid;
    
    /** Creates a new instance of BofdConnection */
    public BofhdConnection(Category log) {
        this.logger = log;
    }

    void connect(String host_url) {
	//XmlRpc.setDebug(true);
	/*
	  The SecurityTool overrides the default key_store and
	  trust_store.  The latter is used by the client to validate
	  the server certificate.
	 */
	/*  This works, but requiers server-cert on local filesystem:
	SecurityTool st = new SecurityTool();
	st.setTrustStore("jbofh.truststore");
	try {
	    st.setup();
	} catch (Exception e) {
	    System.out.println("Error setting SecurityTool: "+e);
	    e.printStackTrace();
	}
	*/
	if(host_url.startsWith("https:")) {
	    try {
		InternalTrustManager tm = new InternalTrustManager();
		TrustManager []tma = {tm};
		SSLContext sc = SSLContext.getInstance("SSL");  // TLS?
		sc.init(null,tma, null);
		SSLSocketFactory sf1 = sc.getSocketFactory();
		HttpsURLConnection.setDefaultSSLSocketFactory(sf1);	
	    } catch (Exception e) {
		System.out.println("Error setting up SSL cert handling: "+e);
		e.printStackTrace();
		System.exit(0);
	    }
	}
        try {
            xmlrpc = new XmlRpcClient(host_url);
        } catch (java.net.MalformedURLException e) {
            System.out.println("Bad url '"+host_url+"', check your property file");
            System.exit(0);
        }
    }
    
    String login(String uname, String password) throws BofhdException {
        Vector args = new Vector();
        args.add(uname);
        args.add(password);
        String sessid = (String) sendRawCommand("login", args);
        logger.debug("Login ret: "+sessid);
        this.sessid = sessid;
        return sessid;
    }
    
    Hashtable getCommands() throws BofhdException {
        Vector args = new Vector();
        args.add(sessid);
        return (Hashtable) sendRawCommand("get_commands", args);
    }
    
    String getHelp(Vector args) throws BofhdException {
        args.add(0, sessid);
        return (String) sendRawCommand("help", args);
    }
    
    Object sendCommand(String cmd, Vector args) throws BofhdException {
        args.add(0, sessid);
        args.add(1, cmd);
        return sendRawCommand("run_command", args);
    }

    private String washSingleObject(String str) {
	if(str.startsWith(":")) {
	    str = str.substring(1);
	    if(str.equals("None")) return "<null>";
	    if(! (str.substring(0,1).equals(":"))) {
		System.err.println("Warning: unknown escape sequence: "+str);
	    }
	}
	return str;
    }

    Object washResponse(Object o) {
	if(o instanceof Vector) {
	    Vector ret = new Vector();
	    for (Enumeration e = ((Vector) o).elements() ; e.hasMoreElements() ;) {
		ret.add(washResponse(e.nextElement()));
	    }
 	    return ret;
	} else if(o instanceof String) {
	    return washSingleObject((String) o);
	} else if(o instanceof Hashtable) {
	    Hashtable ret = new Hashtable();
            for (Enumeration e = ((Hashtable) o).keys (); e.hasMoreElements (); ) {
		Object key = e.nextElement();
		ret.put(key, washResponse(((Hashtable) o).get(key)));
	    }
	    return ret;
	} else {
	    return o;
	}
    }

    Object sendRawCommand(String cmd, Vector args) throws BofhdException {
        try {
            if(cmd.equals("login")) {
                logger.debug("sendCommand("+cmd+", ********");
            } else {
                logger.debug("sendCommand("+cmd+", "+args);
            }
	    Object r = washResponse(xmlrpc.execute(cmd, args));
	    logger.debug("<-"+r);
            return r;
        } catch (XmlRpcException e) {
	    logger.debug("exception-message: "+e.getMessage());
	    String match = "server.bofhd_errors.CerebrumError:";
	    if(e.getMessage().startsWith(match)) {
		throw new BofhdException("User error: "+e.getMessage().substring(match.length()));
	    } else {
		logger.error("err: code="+e.code, e);
		throw new BofhdException("Error: "+e.getMessage());
	    }
        } catch (IOException e) {
            logger.error("IO", e);
            throw new BofhdException("Server error: "+e);
        }
    }

}
