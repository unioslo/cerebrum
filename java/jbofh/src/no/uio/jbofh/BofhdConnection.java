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
import java.util.Date;
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

/**
 *
 * @author  runefro
 */
public class BofhdConnection {
    Category logger;
    XmlRpcClient xmlrpc;
    String sessid;
    Hashtable commands;
    
    /** Creates a new instance of BofdConnection */
    public BofhdConnection(Category log) {
        this.logger = log;
        // The xmlrpc-1.1 driver doesn't handle character encoding correctly
        System.setProperty("sax.driver", "com.jclark.xml.sax.Driver");
    }

    void connect(String host_url, boolean use_int_trust) {
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
	if(use_int_trust && host_url.startsWith("https:")) {
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

    String getMotd(String version) throws BofhdException {
        Vector args = new Vector();
        args.add("jbofh");
        args.add(version);
        String msg = (String) sendRawCommand("get_motd", args);
        return msg;
    }
    
    String logout() throws BofhdException {
        Vector args = new Vector();
        args.add(sessid);
        return (String) sendRawCommand("logout", args);
    }

    void updateCommands() throws BofhdException {
        Vector args = new Vector();
        args.add(sessid);
        commands = (Hashtable) sendRawCommand("get_commands", args);
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
	    if(str.equals("None")) return "<not set>";
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
            } else if(cmd.equals("run_command")){
		Vector cmdDef = (Vector) commands.get(args.get(1));
		if(cmdDef.size() == 1 || (! (cmdDef.get(1) instanceof Vector))) {
		    logger.debug("sendCommand("+cmd+", "+args);
		} else {
		    Vector protoArgs = (Vector) cmdDef.get(1);
		    Vector logArgs = new Vector();
		    logArgs.add(args.get(0));
		    logArgs.add(args.get(1));
		    int i = 2;
		    for (Enumeration e = protoArgs.elements() ; e.hasMoreElements() ;) {
			if(i >= args.size()) break;
			Hashtable h = (Hashtable) e.nextElement();
			String type = (String) h.get("type");
			if (type != null && type.equals("accountPassword")) {
			    logArgs.add("********");
			} else {
			    logArgs.add(args.get(i));
			}
			i++;
		    }
		    logger.debug("sendCommand("+cmd+", "+logArgs);
		}
	    } else {
		logger.debug("sendCommand("+cmd+", "+args);
	    }
	    Object r = washResponse(xmlrpc.execute(cmd, args));
	    logger.debug("<-"+r);
            return r;
        } catch (XmlRpcException e) {
	    logger.debug("exception-message: "+e.getMessage());
	    String match = "Cerebrum.modules.bofhd.errors.";
	    if(e.getMessage().startsWith(match)) {
		throw new BofhdException("User error: "+e.getMessage().substring(e.getMessage().indexOf(":")+1));
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
