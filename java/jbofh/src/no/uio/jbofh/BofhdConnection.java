/*
 * BofdConnection.java
 *
 * Created on November 19, 2002, 11:48 AM
 */

package no.uio.jbofh;
import org.apache.xmlrpc.XmlRpcException;
import org.apache.xmlrpc.XmlRpcClient;
import org.apache.log4j.Category;
import java.util.Arrays;
import java.util.Vector;
import java.util.Hashtable;
import java.util.Enumeration;
import java.io.*;

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
	    if(str.equals("None")) return null;
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
