/*
 * JBofh.java
 *
 * Created on November 1, 2002, 12:20 PM
 */

package no.uio.jbofh;

import org.apache.xmlrpc.XmlRpcException;
import org.apache.xmlrpc.XmlRpcClient;
import java.io.*;
import org.gnu.readline.*;
import java.util.Properties;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.Vector;
import java.util.Hashtable;
import org.apache.log4j.Category;
import org.apache.log4j.PropertyConfigurator;

/**
 *
 * @author  runefro
 */
public class JBofh {
    Properties props;
    Hashtable commands;
    CommandLine cLine;
    BofhdConnection bc;
    static Category logger = Category.getInstance(JBofh.class);

    /** Creates a new instance of JBofh */
    public JBofh() {
        PropertyConfigurator.configure("log4j.properties");
        props = new Properties();
        try {
            props.load(new FileInputStream("jbofh.properties"));
        } catch(IOException e) {}
        bc = new BofhdConnection(logger);
        bc.connect((String) props.get("bofhd_url"));
        
        bc.login("runefro", "password");
        // Setup ReadLine routines
        try {
            Readline.load(ReadlineLibrary.GnuReadline);
        }
        catch (UnsatisfiedLinkError ignore_me) {
            System.err.println("couldn't load readline lib. Using simple stdin.");
        }
        
        commands = bc.getCommands();
        cLine = new CommandLine();
        enterLoop();
    }
       
    public Object []translateCommand(String cmd[]) {
        Object ret[] = new Object[2];
        for (Enumeration e = commands.keys() ; e.hasMoreElements() ;) {
            Object key = e.nextElement();
            Vector cmd_def = (Vector) commands.get(key);
            // logger.debug("G: "+key+" -> "+cmd_def);
            if(cmd_def.get(0) instanceof String) {
                System.out.println("Warning, "+key+" is old protocol, skipping");
                continue;
            }
            Vector c = (Vector) cmd_def.get(0);
            if(cmd[0].equals(c.get(0)) && cmd[1].equals(c.get(1))) {
                ret[0] = key;
                String t[] = new String[cmd.length - 2];
                for(int i = 2; i < cmd.length; i++) t[i-2] = cmd[i];
                ret[1] = t;
                return ret;
            }
        }
        return null; // Throw?
    }
            
    public void enterLoop() {
        while(true) {
            String args[] = cLine.getSplittedCommand();
            if(args.length == 0) continue;
            // for(int i = 0; i < args.length; i++) logger.debug(i+": "+args[i]);
            if(args[0].equals("commands")) {  // Neat while debugging
                for (Enumeration e = commands.keys() ; e.hasMoreElements() ;) {
                    Object key = e.nextElement();
                    System.out.println(key+" -> "+ commands.get(key)); 
                }
            } else if(args[0].equals("help")) {
                String v[] = new String[args.length-1];        
                System.arraycopy(args, 0, v, 0, args.length-1);
                System.out.println(bc.getHelp(v));
            } else {
                Object r[] = translateCommand(args);
                if(r == null) {
                    System.out.println("Error translating command"); continue;
                }
                logger.debug("Tra: "+r[0]+" -> ("+((Object [])r[1]).length +") "+r[1]);
                for(int i = 0; i < ((Object [])r[1]).length; i++)
                    logger.debug(i+": "+((Object [])r[1])[i]);
                Object resp = bc.sendCommand((String) r[0], (String [])r[1]);
                if(resp != null) showResponse((String) r[0], resp);
            }
        }
    }
    
    public void showResponse(String cmd, Object resp) {
        String args[] = { cmd };
        Hashtable format = (Hashtable) bc.sendRawCommand("get_format_suggestion", args);
        System.out.println("Format: "+resp);
        System.out.println("as: "+format);
    }
    /**
     * @param args the command line arguments
     */
    public static void main(String[] args) {
        new JBofh();
    }
    
}
