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
        String cmd[] = {uname, password};
        String sessid = (String) sendRawCommand("login", cmd);
        logger.debug("Login ret: "+sessid);
        this.sessid = sessid;
        return sessid;
    }
    
    Hashtable getCommands() {
        String args[] = {sessid};
        return (Hashtable) sendRawCommand("get_commands", args);
    }
    
    String getHelp(String args[]) {
        return (String) sendRawCommand("help", args);
    }
    
    Object sendCommand(String cmd, String[] args) {
        String v[] = new String[args.length+2];        
        v[0] = sessid;
        v[1] = cmd;
        System.arraycopy(args, 0, v, 2, args.length);
        return sendRawCommand("run_command", v);
    }

    Object sendRawCommand(String cmd, String[] args) {
        try {
            logger.debug("sendCommand("+cmd+", ");
            for(int i = 0; i < args.length; i++) logger.debug(args[i]+", ");
            return xmlrpc.execute(cmd, new Vector(Arrays.asList(args)));
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
