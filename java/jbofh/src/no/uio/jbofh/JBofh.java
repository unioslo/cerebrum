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
import java.util.Iterator;
import org.apache.log4j.Category;
import org.apache.log4j.PropertyConfigurator;


import com.sun.java.text.PrintfFormat;

/**
 * Thrown when analyzeing of command failes.
 *
 * @author  runefro
 */

class AnalyzeCommandException extends Exception {
    /**
     * @param msg message describing the error
     */    
    AnalyzeCommandException(String msg) {
        super(msg);
    }
}

/**
 * Tab-completion utility for use with readline.  Also supports translation 
 * of short-form of unique commands to full-form.
 *
 * @author  runefro
 */

class BofhdCompleter implements org.gnu.readline.ReadlineCompleter {
    JBofh jbofh;
    Vector possible;
    Iterator iter;
    Category logger;
    Hashtable complete;

    BofhdCompleter(JBofh jbofh, Category logger) {
        this.jbofh = jbofh;
        this.logger = logger;
        buildCompletionHash();
    }
    
    public void buildCompletionHash() {
        complete = new Hashtable();
        for (Enumeration e = jbofh.commands.keys(); e.hasMoreElements(); ) {
            String protoCmd = (String) e.nextElement();
            Vector cmd = (Vector) ((Vector) jbofh.commands.get(protoCmd)).get(0);
            logger.debug(protoCmd+" -> "+cmd);
            Hashtable h = complete;
            for(int i = 0; i < cmd.size(); i++) {
                Hashtable h2 = (Hashtable) h.get(cmd.get(i));
                if(h2 == null) {
                    h2 = new Hashtable();
                    h.put(cmd.get(i), h2);
                }
                h = h2;
            }
        }
        logger.debug(complete);
    }
    
    /**
     * Analyze the command that user has entered by comparing with the list of legal 
     * commands, and translating to the command-parts full name.  When the command is 
     * not unique, the value of expat determines the action.  If < 0, or not equal to
     * the current argument number, an AnalyzeCommandException is thrown.  Otherwise a 
     * list of legal values is returned.
     *
     * If expat < 0 and all checked parameters defined in the list of legal commands 
     * were ok, the expanded parameters are returned.
     *
     * @param cmd the arguments to analyze
     * @param expat the level at which expansion should occour, or < 0 to translate
     * @throws AnalyzeCommandException
     * @return list of completions, or translated commands
     */    
    public Object []analyzeCommand(String cmd[], int expat) throws AnalyzeCommandException {
        int lvl = 0;
        Hashtable h = complete;
        Enumeration e = h.keys();
        while(e.hasMoreElements()) logger.debug("dta: "+e.nextElement());
        e = h.keys();

        logger.debug("analyzeCommand("+cmd.length+", "+expat);
        while(expat < 0 || lvl <= expat) {
            Vector thisLvl = new Vector();
            while(e.hasMoreElements()) {
                String tmp = (String) e.nextElement();
                logger.debug("chk: "+tmp);
                if(lvl >= cmd.length || tmp.startsWith(cmd[lvl])) {
                    logger.debug("added");
                    thisLvl.add(tmp);
                }
            }
            logger.debug(expat+" == "+lvl);
            if(expat == lvl) {
                return thisLvl.toArray();
            }
            if(thisLvl.size() == 1) {  // Check next level
                cmd[lvl] = (String) thisLvl.get(0);
                h = (Hashtable) h.get(cmd[lvl]);
                if(h.size() == 0 && expat < 0) {
                    Object ret[] = new Object[lvl];
                    for(int i = 0; i < lvl; i++) ret[i] = cmd[i];
                    return ret;
                }
                /* TODO:  If h.size() == 0 -> we have reached the max completion
                 * depth.  It would perhaps be nice to signal that even when expat >= 0?
                 **/
                if(h == null) {
                    Vector ret = new Vector();
                    for(int i = 0; i < lvl; i++) ret.add(cmd[i]);
                    return ret.toArray();
                }
                e = h.keys();
                lvl++;
            } else {
                throw new AnalyzeCommandException("size="+thisLvl.size());
            }
        }
        logger.error("oops!");
        throw new RuntimeException("Internal error");  // Not reached
    }
        
    public String completer(String str, int param) {
        /*
         * The readLine library gives too little information about the current line to get 
         * this correct as it does not seem to include information about where on the line 
         * the cursor is when tab is pressed, making it impossible to tab-complete within 
         * a line.
         *
         * 
         **/
        if(param == 0) {  // 0 -> first call to iterator
            String args[] = jbofh.cLine.splitCommand(Readline.getLineBuffer());
            logger.debug("len="+args.length+", trail_space="+(Readline.getLineBuffer().endsWith(" ") ? "true" : "false"));
            int len = args.length;
            if(! Readline.getLineBuffer().endsWith(" ")) len--;
            if(len < 0) len = 0;
            logger.debug("new len: "+len);
            if(len >= 2) {
                iter = null;
                return null;
            }
            possible = new Vector();
            try {
                Object lst[] = analyzeCommand(args, len);
                for(int i = 0; i < lst.length; i++) possible.add(lst[i]);
                iter = possible.iterator();
            } catch (AnalyzeCommandException e) {
                logger.debug("Caught: ", e);
                iter = null;
            }
        }
        if(iter != null && iter.hasNext()) return (String) iter.next();
        return null;
    }
}

/**
 * Main class for the JBofh program.
 *
 * @author  runefro
 */
public class JBofh {
    Properties props;
    Hashtable commands;
    CommandLine cLine;
    BofhdConnection bc;
    static Category logger = Category.getInstance(JBofh.class);
    BofhdCompleter bcompleter;
    Hashtable knownFormats;

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
        commands = bc.getCommands();

        bcompleter = new BofhdCompleter(this, logger);
        // Setup ReadLine routines
        try {
            Readline.load(ReadlineLibrary.GnuReadline);
            Readline.setCompleter(bcompleter);
        }
        catch (UnsatisfiedLinkError ignore_me) {
            System.err.println("couldn't load readline lib. Using simple stdin.");
        }
        cLine = new CommandLine(logger);
        knownFormats = new Hashtable();
        enterLoop();
    }

    /**
     * Translate a command-line command to a protocol-command.
     *
     * @param cmd the command-line arguments
     * @return the protocol command
     */    
    Object []translateCommand(String cmd[]) {
        Object ret[] = new Object[2];
        for (Enumeration e = commands.keys() ; e.hasMoreElements() ;) {
            Object key = e.nextElement();
            Vector cmd_def = (Vector) commands.get(key);
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
            
    void enterLoop() {
        while(true) {
            String args[] = cLine.getSplittedCommand();
            if(args == null) break;
            if(args.length == 0) continue;
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
                try {
                    Object lst[] = bcompleter.analyzeCommand(args, -1);
                    for(int i = 0; i < lst.length; i++) args[i] = (String) lst[i];
                } catch (AnalyzeCommandException e) {
                    System.out.println("Error translating command:"+e); continue;
                }
                    
                Object r[] = translateCommand(args);
                if(r == null) {
                    System.out.println("Error translating command"); continue;
                }
                String protoCmd = (String) r[0];
                Object protoArgs[] = (Object []) r[1];
                protoArgs = checkArgs(protoCmd, protoArgs);
                Object resp = bc.sendCommand(protoCmd, (String [])protoArgs);
                if(resp != null) showResponse(protoCmd, resp);
            }
        }
        System.out.println("I'll be back");
    }

    Object []checkArgs(String cmd, Object args[]) {
        /*
        logger.debug("Tra: "+cmd+" -> ("+args.length +") "+args);
        for(int i = 0; i < args.length; i++)
            logger.debug(i+": "+args[i]); */
        String sample[] = {};
        Vector ret = new Vector();
        for(int i = 0; i < args.length; i++) 
            ret.add(args[i]);        
        Vector cmd_def = (Vector) commands.get(cmd);
        Vector pspec = (Vector) cmd_def.get(1);
        for(int i = args.length; i < pspec.size(); i++) {
            logger.debug("ps: "+i+" -> "+pspec.get(i));
            /* TODO:  I'm not sure how to handle the diff between optional and default */
            Integer opt = (Integer) ((Hashtable)pspec.get(i)).get("optional");
            if(opt == null) opt = (Integer) ((Hashtable)pspec.get(i)).get("default");
            if(opt != null && opt.intValue() == 1) 
                break;
            ret.add(0, bc.sessid);
            ret.add(1, cmd);
            String prompt = (String) bc.sendRawCommand("prompt_next_param", (String [])ret.toArray(sample));            
            ret.remove(0);
            ret.remove(0);
            ret.add(cLine.promptArg(prompt+" >", false));
        }
        return ret.toArray(sample);
    }
    
    void showResponse(String cmd, Object resp) {
        String args[] = { cmd };
        Hashtable format = (Hashtable) knownFormats.get(cmd);
        if(format == null) {
            knownFormats.put(cmd, bc.sendRawCommand("get_format_suggestion", args));
            format = (Hashtable) knownFormats.get(cmd);
        }
        
	Vector order = (Vector) format.get("var");
	if(! (resp instanceof Vector) ){
	    Vector tmp = new Vector();
	    tmp.add(resp);
	    resp = tmp;
	} else {
	    String hdr = (String) format.get("hdr");
	    if(hdr != null) System.out.println(hdr);
	}
	for (Enumeration e = ((Vector) resp).elements() ; e.hasMoreElements() ;) {
	    Object row = e.nextElement();
	    try {
		PrintfFormat pf = new PrintfFormat((String) format.get("str"));
		Object a[] = new Object[order.size()];
		for(int i = 0; i < order.size(); i++) 
		    a[i] = ((Hashtable) row).get((String) order.get(i));
		System.out.println(pf.sprintf(a));
	    } catch (IllegalArgumentException ex) {
		logger.error("Error formatting "+resp+"\n as: "+format, ex);
		System.out.println("An error occoured formatting the response, see log for details");
	    }
        }
    }
    /**
     * @param args the command line arguments
     */
    public static void main(String[] args) {
        new JBofh();
    }    
}
