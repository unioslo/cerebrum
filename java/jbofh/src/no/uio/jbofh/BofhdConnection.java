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
    
    String login(String uname, String password) {
        Vector args = new Vector();
        args.add(uname);
        args.add(password);
        String sessid = (String) sendRawCommand("login", args);
        logger.debug("Login ret: "+sessid);
        this.sessid = sessid;
        return sessid;
    }
    
    Hashtable getCommands() {
        Vector args = new Vector();
        args.add(sessid);
        return (Hashtable) sendRawCommand("get_commands", args);
    }
    
    String getHelp(Vector args) {
        return (String) sendRawCommand("help", args);
    }
    
    Object sendCommand(String cmd, Vector args) {
        args.add(0, sessid);
        args.add(1, cmd);
        return sendRawCommand("run_command", args);
    }

    Object sendRawCommand(String cmd, Vector args) {
        try {
            logger.debug("sendCommand("+cmd+", "+args);
            return xmlrpc.execute(cmd, args);
        } catch (XmlRpcException e) {
            logger.error("err:", e);
            System.out.println("Error: "+e.getMessage());
            return null;
        } catch (IOException e) {
            logger.error("IO", e);
            System.out.println("Server error: "+e);
            return null;
        }
    }

}
