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
 *
 * @author  runefro
 */
public class BofhdConnection {
    Category logger;
    XmlRpcClient xmlrpc;
    String sessid;
    Hashtable commands;
    JBofh jbofh;
    
    /** Creates a new instance of BofdConnection */
    public BofhdConnection(Category log, JBofh jbofh) {
        this.logger = log;
        this.jbofh = jbofh;
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
            // XmlRpc.setDebug(true);
        } catch (java.net.MalformedURLException e) {
            System.out.println("Bad url '"+host_url+"', check your property file");
            System.exit(0);
        }
    }
    
    String login(String uname, String password) throws BofhdException {
        Vector args = new Vector();
        args.add(uname);
        args.add(password);
        String newsessid = (String) sendRawCommand("login", args, -1);
        logger.debug("Login ret: "+newsessid);
        this.sessid = newsessid;
        return newsessid;
    }

    String getMotd(String version) throws BofhdException {
        Vector args = new Vector();
        args.add("jbofh");
        args.add(version);
        String msg = (String) sendRawCommand("get_motd", args, -1);
        return msg;
    }
    
    String logout() throws BofhdException {
        Vector args = new Vector();
        args.add(sessid);
        return (String) sendRawCommand("logout", args, 0);
    }

    void updateCommands() throws BofhdException {
        Vector args = new Vector();
        args.add(sessid);
        commands = (Hashtable) sendRawCommand("get_commands", args, 0);
    }
    
    String getHelp(Vector args) throws BofhdException {
        args.add(0, sessid);
        return (String) sendRawCommand("help", args, 0);
    }
    
    Object sendCommand(String cmd, Vector args) throws BofhdException {
        args.add(0, sessid);
        args.add(1, cmd);
        return sendRawCommand("run_command", args, 0);
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

    /**
     * We have extended XML-rpc by allowing NULL values to be
     * returned.  <code>washResponse</code> handles this.
     *
     * @param o the object to wash
     * @return the washed object
     */
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

    Object sendRawCommand(String cmd, Vector args, int sessid_loc) throws BofhdException {
        return sendRawCommand(cmd, args, false, sessid_loc);
    }

    private void checkSafeString(String s) throws BofhdException {
        /* http://www.w3.org/TR/2004/REC-xml-20040204/#NT-Char
           #x9 | #xA | #xD | [#x20-#xD7FF] */
        char chars[] = s.toCharArray();
        for (int i = 0; i < chars.length; i++) {
            int c = chars[i];
            if (c >= 0x20){ continue; }
            if (c == 0x9 || c == 0xa || c == 0xd){ continue; }
            throw new BofhdException("You entered an illegal charcter:"+c);
        }
    }
    /**
     * Handle bofhds extensions to XML-RPC by pre-prosessing the
     * arguments.  Since we only send String (or Vector with
     * String), we don't support the other extensions.
     *
     * @param args a <code>Vector</code> representing the arguments
     */
    void washCommandArgs(Vector args) throws BofhdException {
        for (int i = args.size()-1; i >= 0; i--) {
            Object tmp = args.get(i);
            if (tmp instanceof String) {
                if (((String) tmp).length() > 0 && ((String) tmp).charAt(0) == ':') {
                    tmp = ":"+((String) tmp);
                    args.setElementAt(tmp, i);
                }
                checkSafeString((String) tmp);
            } else if (tmp instanceof Vector) {
                Vector v = (Vector) tmp;
                for (int j = v.size()-1; j >= 0; j--) {
                    tmp = v.get(j);
                    if ((tmp instanceof String) && (((String) tmp).charAt(0) == ':')) {
                        tmp = ":"+((String) tmp);
                        v.setElementAt(tmp, j);
                    }
                    checkSafeString((String) tmp);
                }
            }
        }
    }

    /**
     * Sends a raw command to the server.
     *
     * @param cmd a <code>String</code> with the name of the command
     * @param args a <code>Vector</code> of arguments
     * @param sessid_loc an <code>int</code> the location of the
     * sessionid.  Needed if the command triggers a re-authentication
     * @return an XML-rpc <code>Object</code>
     * @exception BofhdException if an error occurs
     */
    Object sendRawCommand(String cmd, Vector args, boolean gotRestart,
        int sessid_loc) throws BofhdException {
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
            washCommandArgs(args);
            Object r = washResponse(xmlrpc.execute(cmd, args));
            logger.debug("<-"+r);
            return r;
        } catch (XmlRpcException e) {
            logger.debug("exception-message: "+e.getMessage());
            String match = "Cerebrum.modules.bofhd.errors.";
            if(! gotRestart && 
                e.getMessage().startsWith(match+"ServerRestartedError")) {
                jbofh.initCommands();
                return sendRawCommand(cmd, args, true, sessid_loc);
            } else if (e.getMessage().startsWith(match+"SessionExpiredError")) {
                jbofh.showMessage("Session expired, you must re-authenticate", true);
                jbofh.login(jbofh.uname, null);
                if (sessid_loc != -1) args.set(sessid_loc, sessid);
                return sendRawCommand(cmd, args, true, sessid_loc);
            } else if(e.getMessage().startsWith(match)) {
                String msg = e.getMessage().substring(e.getMessage().indexOf(":")+1);
                if(msg.startsWith("CerebrumError: ")) msg = msg.substring(msg.indexOf(":")+2);
                throw new BofhdException("Error: "+msg);
            } else {
                logger.debug("err: code="+e.code, e);
                throw new BofhdException("Error: "+e.getMessage());
            }
        } catch (IOException e) {
            throw new BofhdException("IOError talking to bofhd server: "+e.getMessage());
        }
    }

}

// arch-tag: e689905d-cdab-4978-9ea4-28e1647b512e
