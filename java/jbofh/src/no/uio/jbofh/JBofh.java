/*
 * JBofh.java
 *
 * Created on November 1, 2002, 12:20 PM
 */

package no.uio.jbofh;

import java.io.*;
import java.text.ParseException;
import java.net.URL;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Iterator;
import java.util.Properties;
import java.util.Vector;
import org.apache.log4j.Category;
import org.apache.log4j.PropertyConfigurator;
import org.apache.xmlrpc.XmlRpcClient;
import org.apache.xmlrpc.XmlRpcException;
import org.gnu.readline.*;
import javax.swing.JOptionPane;

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
        for (Enumeration e = jbofh.bc.commands.keys(); e.hasMoreElements(); ) {
            String protoCmd = (String) e.nextElement();
            Vector cmd = (Vector) ((Vector) jbofh.bc.commands.get(protoCmd)).get(0);
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
     * Analyze the command that user has entered by comparing with the
     * list of legal commands, and translating to the command-parts
     * full name.  When the command is not unique, the value of expat
     * determines the action.  If < 0, or not equal to the current
     * argument number, an AnalyzeCommandException is thrown.
     * Otherwise a list of legal values is returned.
     *
     * If expat < 0 and all checked parameters defined in the list of
     * legal commands were ok, the expanded parameters are returned.
     *
     * @param cmd the arguments to analyze
     * @param expat the level at which expansion should occour, or < 0 to translate
     * @throws AnalyzeCommandException
     * @return list of completions, or translated commands
     */    
    public Vector analyzeCommand(Vector cmd, int expat) throws AnalyzeCommandException {
        int lvl = 0;
        boolean debugCmdAnalyzer = false;
        Hashtable h = complete;
        Enumeration e = h.keys();
        if (debugCmdAnalyzer) 
            while(e.hasMoreElements()) logger.debug("dta: "+e.nextElement());
        e = h.keys();

        if (debugCmdAnalyzer) logger.debug("analyzeCommand("+cmd.size()+", "+expat);
        while(expat < 0 || lvl <= expat) {
            Vector thisLvl = new Vector();
            while(e.hasMoreElements()) {   // Find matching commands at this level
                String tmp = (String) e.nextElement();
                if (debugCmdAnalyzer) logger.debug("chk: "+tmp);
		boolean ok = false;
		if(lvl >= cmd.size()) {
		    ok = true;
		} else if((cmd.get(lvl) instanceof String) &&
                    tmp.startsWith((String) cmd.get(lvl))) {
		    ok = true;
                    if(tmp.equals((String) cmd.get(lvl))) {
                        thisLvl.clear();
                        thisLvl.add(tmp);
                        break;
                    }
		}
		if(ok) {
                    if (debugCmdAnalyzer) logger.debug("added");
                    thisLvl.add(tmp);
                }
            }
            if (debugCmdAnalyzer) logger.debug(expat+" == "+lvl);
            if(expat == lvl) {
                return thisLvl;
            }
            if(thisLvl.size() == 1) {  // Check next level
                cmd.set(lvl, thisLvl.get(0));
                h = (Hashtable) h.get(cmd.get(lvl));
                if(h.size() == 0 && expat < 0) {
                    Vector ret = new Vector();
                    for(int i = 0; i < lvl; i++) ret.add(cmd.get(i));
                    return ret;
                }
                /* TODO:  If h.size() == 0 -> we have reached the max completion
                 * depth.  It would perhaps be nice to signal that even when expat >= 0?
                 **/
                if(h == null) {
                    Vector ret = new Vector();
                    for(int i = 0; i < lvl; i++) ret.add(cmd.get(i));
                    return ret;
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
         * The readLine library gives too little information about the
         * current line to get this correct as it does not seem to
         * include information about where on the line the cursor is
         * when tab is pressed, making it impossible to tab-complete
         * within a line.
         * 
         **/
        String cmdLineText;
        if(jbofh.guiEnabled) {
            cmdLineText = jbofh.mainFrame.getCmdLineText();
        } else {
            cmdLineText = Readline.getLineBuffer();
        }
        if(param == 0) {  // 0 -> first call to iterator
            Vector args;
	    try {
		args = jbofh.cLine.splitCommand(cmdLineText);
	    } catch (ParseException pe) {
		iter = null;
		return null;
	    }
            logger.debug("len="+args.size()+", trail_space="+(cmdLineText.endsWith(" ") ? "true" : "false"));
            int len = args.size();
            if(! cmdLineText.endsWith(" ")) len--;
            if(len < 0) len = 0;
            logger.debug("new len: "+len);
            if(len >= 2) {
                iter = null;
                return null;
            }
            try {
                possible = analyzeCommand(args, len);
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
    CommandLine cLine;
    BofhdConnection bc;
    static Category logger = Category.getInstance(JBofh.class);
    BofhdCompleter bcompleter;
    Hashtable knownFormats;
    String version = "unknown";
    boolean guiEnabled;
    JBofhFrame mainFrame;

    /** Creates a new instance of JBofh */
    public JBofh(String def_uname, String def_password, boolean gui, String log4jPropertyFile) 
        throws BofhdException {
	guiEnabled = gui;
        try {
	    URL url = ResourceLocator.getResource(this, log4jPropertyFile);
            if(url == null) throw new IOException();
	    props = new Properties();
	    props.load(url.openStream());
	    PropertyConfigurator.configure(props);
	    props = new Properties();
	    url = ResourceLocator.getResource(this, "/jbofh.properties");
            props.load(url.openStream());
        } catch(IOException e) {
	    showMessage("Error reading property files", true);
	    System.exit(1);
	}
	if(gui) mainFrame = new JBofhFrame(this);
	URL url = ResourceLocator.getResource(this, "/version.txt");
	try {
	    BufferedReader br = new BufferedReader(new InputStreamReader(url.openStream()));
	    version = br.readLine();
	    br.close();
	} catch (IOException e) {}  // ignore failure

        bc = new BofhdConnection(logger);
        String intTrust = (String) props.get("InternalTrustManager.enable");
        showMessage("Bofhd server is at "+props.get("bofhd_url"), true);
        bc.connect((String) props.get("bofhd_url"), 
            (intTrust != null && intTrust.equals("true")) ? true : false);
        // Setup ReadLine routines
        try {
            Readline.load(ReadlineLibrary.GnuReadline);
        }
        catch (UnsatisfiedLinkError ignore_me) {
            showMessage("couldn't load readline lib. Using simple stdin.", true);
        }

        cLine = new CommandLine(logger, this);
	String uname, password;
	try {
	    if(def_password != null) {  // Shortcut wile debugging (-q param)
		bc.login(def_uname, def_password);
	    } else {
		uname = cLine.promptArg("Username " + 
                    (def_uname == null ? "" : "["+def_uname+"]") +": ", 
                    false);
		if(uname.equals("")) uname = def_uname;
                ConsolePassword cp = new ConsolePassword();
		if(guiEnabled) {
		    try {
			password = cp.getPasswordByJDialog("Password:", mainFrame.frame);
		    } catch (ConsolePassword.MethodFailedException e) {
			return;
		    }
		} else {
		    password = cp.getPassword("Password:");
		}
		bc.login(uname, password);
	    }
	} catch (IOException io) {
	    System.exit(0);
	}

        bc.updateCommands();
        bcompleter = new BofhdCompleter(this, logger);
	Readline.setCompleter(bcompleter);

        knownFormats = new Hashtable();
	showMessage("Welcome to jbofh, v "+version+", type \"help\" for help", true);
        enterLoop();
    }

    void showMessage(String msg, boolean crlf) {
	if(guiEnabled) {
	    mainFrame.showMessage(msg, crlf);
	} else {
	    if(crlf) {
		System.out.println(msg);
	    } else {
		System.out.print(msg);
	    }
	}
    }

    /**
     * Translate a command-line command to a protocol-command.
     *
     * @param cmd the command-line arguments
     * @return the protocol command
     */    
    Object []translateCommand(Vector cmd) {
        Object ret[] = new Object[2];
        if(cmd.size() < 2) return null;
        for (Enumeration e = bc.commands.keys() ; e.hasMoreElements() ;) {
            Object key = e.nextElement();
            Vector cmd_def = (Vector) bc.commands.get(key);
            if(cmd_def.get(0) instanceof String) {
                showMessage("Warning, "+key+" is old protocol, skipping", true);
                continue;
            }
            Vector c = (Vector) cmd_def.get(0);
            if(((String) cmd.get(0)).equals(c.get(0)) && 
                ((String) cmd.get(1)).equals(c.get(1))) {
                ret[0] = key;
                Vector t = new Vector();                
                for(int i = 2; i < cmd.size(); i++) t.add(cmd.get(i));
                ret[1] = t;
                return ret;
            }
        }
        return null; // Throw?
    }
            
    void enterLoop() {
        while(true) {
            Vector args;
            try {
                args = cLine.getSplittedCommand();
            } catch (IOException io) {
                if(guiEnabled && (! mainFrame.confirmExit()))
                    continue;
                break;
            } catch (ParseException pe) {
                showMessage("Error parsing command: "+pe, true);
                continue;
            }
            if(args.size() == 0) continue;
	    try {
		if(((String) args.get(0)).equals("commands")) {  // Neat while debugging
		    for (Enumeration e = bc.commands.keys() ; e.hasMoreElements() ;) {
			Object key = e.nextElement();
			showMessage(key+" -> "+ bc.commands.get(key), true); 
		    }
                } else if(((String) args.get(0)).equals("quit") || 
                    ((String) args.get(0)).equals("q")) {
                    bye();
		} else if(((String) args.get(0)).equals("source")) {
                    if(args.size() == 0) {
                        showMessage("Must specify filename to source", true);
                    } else {
                        sourceFile((String) args.get(1));
                    }
		} else if(((String) args.get(0)).equals("help")) {
		    args.remove(0);
		    showMessage(bc.getHelp(args), true);
		} else {
		    try {
			Vector lst = bcompleter.analyzeCommand(args, -1);
			for(int i = 0; i < lst.size(); i++) args.set(i, lst.get(i));
		    } catch (AnalyzeCommandException e) {
			showMessage("Error translating command:"+e, true); continue;
		    }
                    
		    Object r[] = translateCommand(args);
		    if(r == null) {
			showMessage("Error translating command", true); continue;
		    }
		    String protoCmd = (String) r[0];
		    Vector protoArgs = (Vector) r[1];
		    protoArgs = checkArgs(protoCmd, protoArgs);
		    if(protoArgs == null) continue;
		    try {
			boolean multiple_cmds = false;
			for (Enumeration e = protoArgs.elements() ; e.hasMoreElements() ;) 
			    if(e.nextElement() instanceof Vector)
				multiple_cmds = true;
                        if(guiEnabled) mainFrame.showWait(true);
			Object resp = bc.sendCommand(protoCmd, protoArgs);
			if(resp != null) showResponse(protoCmd, resp, multiple_cmds);
		    } catch (BofhdException ex) {
			showMessage(ex.getMessage(), true);
		    } catch (Exception ex) {
			showMessage("Unexpected error (bug, true): "+ex, true);
			ex.printStackTrace();
		    } finally {
                        if(guiEnabled) mainFrame.showWait(false);
                    }
		}
	    } catch (BofhdException be) {
		showMessage(be.getMessage(), true);
	    }
	}
        bye();
    }

    void sourceFile(String filename) {
        if(guiEnabled) mainFrame.showWait(true);
        Vector cmds = new Vector();  // For convenience we read the whole file in one go
        try {
            BufferedReader in = new BufferedReader(
                new InputStreamReader(new FileInputStream(filename)));
            String sin;
            while((sin = in.readLine()) != null) {
                cmds.add(sin);
            }
        } catch (IOException io) {
            showMessage("Error reading file: "+io.getMessage(), true);
            if(guiEnabled) mainFrame.showWait(false);
            return;
        }
        
        for (Enumeration e = ((Vector) cmds).elements() ; e.hasMoreElements() ;) {
            String cmd = (String) e.nextElement();
            Vector args;
            try {
                args = cLine.splitCommand(cmd);
            } catch (ParseException ex) {
                showMessage("Error translating command: "+cmd, true); continue;
             }
            Object r[] = translateCommand(args);
            if(r == null) {
                showMessage("Error translating command: "+cmd, true); continue;
            }
            String protoCmd = (String) r[0];
            Vector protoArgs = (Vector) r[1];
            try {
                showMessage("jbofh >"+cmd, true);
                Object resp = bc.sendCommand(protoCmd, protoArgs);
                if(resp != null) showResponse(protoCmd, resp, false);
            } catch (BofhdException ex) {
                showMessage(ex.getMessage(), true);
            } catch (Exception ex) {
                showMessage("Unexpected error (bug, true): "+ex, true);
                ex.printStackTrace();
            }
        }
        if(guiEnabled) mainFrame.showWait(false);
    }

    void bye() {
        showMessage("I'll be back", true);
        try {
            bc.logout();
        } catch (BofhdException ex) { } // Ignore
        System.exit(0);
    }

    Vector checkArgs(String cmd, Vector args) throws BofhdException {
        String sample[] = {};
        Vector ret = (Vector) args.clone();
        Vector cmd_def = (Vector) bc.commands.get(cmd);
	if(cmd_def.size() == 1) return ret;
	Object pspec = cmd_def.get(1);
	if (pspec instanceof String) {
	    if(! "prompt_func".equals(pspec)) {
		throw new BofhdException("Bad param spec");
	    }
	    return processServerCommandPromptFunction(cmd, ret);
	}
        for(int i = args.size(); i < ((Vector) pspec).size(); i++) {
	    Hashtable param = (Hashtable) ((Vector) pspec).get(i);
            logger.debug("ps: "+i+" -> "+param);
            /* TODO:  I'm not sure how to handle the diff between optional and default */
            Integer opt = (Integer) param.get("optional");
            if(opt != null && opt.intValue() == 1) 
                break;
	    Object tmp = param.get("default");
	    String defval = null;
	    if(tmp != null) {
		if(tmp instanceof String){
		    defval = (String) tmp;
		} else {
		    ret.add(0, bc.sessid);
		    ret.add(1, cmd);
		    defval = (String) bc.sendRawCommand("get_default_param", ret);
		    ret.remove(0);
		    ret.remove(0);
		}
	    }
	    String prompt = (String) param.get("prompt");
	    String type = (String) param.get("type");
            try {
		String s;
		if (type != null && type.equals("accountPassword")) {
		    ConsolePassword cp = new ConsolePassword();

		    if(guiEnabled) {
			try {
			    s = cp.getPasswordByJDialog(prompt + ">", mainFrame.frame);
			} catch (ConsolePassword.MethodFailedException e) {
			    s = "";
			}
		    } else {
			s = cp.getPassword(prompt + ">");
		    }
		} else {
		    s = cLine.promptArg(prompt+
					(defval == null ? "" : " ["+defval+"]")+" >", false);
		}
		if(defval != null && s.equals("")) {
		    ret.add(defval);
                } else if(s.equals("?")) {
                    i--;
                    Vector v = new Vector();
                    v.add("arg_help");
                    v.add(param.get("help_ref"));
                    String help = (String) bc.getHelp(v);
                    showMessage(help, true);
		} else {
		    ret.add(s);
		}
            } catch (IOException io) {
                return null;
            }
        }
        return ret;
    }
    
    Vector processServerCommandPromptFunction(String cmd, Vector ret)  throws BofhdException {
	while(true) {
	    ret.add(0, bc.sessid);
	    ret.add(1, cmd);
            Object obj =  bc.sendRawCommand("call_prompt_func", ret);
            if (! (obj instanceof Hashtable))
                throw new BofhdException("Server bug: prompt_func returned " + obj);
	    Hashtable arginfo = (Hashtable) obj;
	    ret.remove(0);
	    ret.remove(0);
	    try {
                if(arginfo.get("prompt") == null && arginfo.get("last_arg") != null)
                    break;
		String defval = (String) arginfo.get("default");
                Vector map = (Vector) arginfo.get("map");
                if(map != null) {
                    for(int i = 0; i < map.size(); i++) {
                        Vector line = (Vector) map.get(i);
                        Vector description = (Vector) line.get(0);
                        String format_desc = (String) description.get(0);
                        description.remove(0);
                        if(i == 0) {
                            format_desc = "%4s " + format_desc;
                            description.add(0, "Num");
                        } else {
                            format_desc = "%4i " + format_desc;
                            description.add(0, new Integer(i));
                        }
                        PrintfFormat pf = new PrintfFormat(format_desc);
                        showMessage(pf.sprintf(description.toArray()), true);
                    }
                }
		String s = cLine.promptArg((String) arginfo.get("prompt") +
                    (defval == null ? "" : " ["+defval+"]")+" >", false);
		if(s.equals("") && defval == null) continue;
                if(s.equals("?")) {
                    if(arginfo.get("help_ref") == null) {
                        showMessage("Sorry, no help available", true);
                        continue;
                    }
                    Vector v = new Vector();
                    v.add("arg_help");
                    v.add(arginfo.get("help_ref"));
                    String help = (String) bc.getHelp(v);
                    showMessage(help, true);
                    continue;
                }
		if(! s.equals("")) {
		    if(map != null && arginfo.get("raw") == null) {
                        try {
                            int i = Integer.parseInt(s);
                            if(i == 0) throw new Exception("");
			    ret.add(((Vector)map.get(i)).get(1));
                        } catch (Exception e) {
			    showMessage("Value not in list", true);
                        }
		    } else {
			ret.add(s);
                    } 
		} else {
		    if(defval != null) ret.add(defval);
		}
		if(arginfo.get("last_arg") != null) break;
	    } catch (IOException io) {
                return null;
            }
	}
	return ret;
    }

    void showResponse(String cmd, Object resp, boolean multiple_cmds) throws BofhdException {
	if(multiple_cmds) {
	    /* TBD: Should we try to provide some text indicating
	     * which command each response belongs to?
	     */
	    for (Enumeration e = ((Vector) resp).elements() ; e.hasMoreElements() ;) {
		Object next_resp = e.nextElement();
		showResponse(cmd, next_resp, false);
	    }
	    return;
	}
	if(resp instanceof String) {
	    showMessage((String) resp, true);
	    return;
	}
        Vector args = new Vector();
        args.add(cmd);
        Hashtable format = (Hashtable) knownFormats.get(cmd);
        if(format == null) {
	    Object f = bc.sendRawCommand("get_format_suggestion", args);
	    if(f instanceof String && ((String)f).equals(""))
		f = null;
	    if(f != null) {
		knownFormats.put(cmd, f);
		format = (Hashtable) knownFormats.get(cmd);
	    } else {
		throw new IllegalArgumentException("result was class: "+
                    resp.getClass().getName()+ ", no format suggestion exists");
	    }
        }
	if(! (resp instanceof Vector) ){
	    Vector tmp = new Vector();    // Pretend that returned value was a Vector
	    tmp.add(resp);
	    resp = tmp;
	} else {   	    // Vector responses may have a header
	    String hdr = (String) format.get("hdr");
	    if(hdr != null) showMessage(hdr, true);
	}
	for (Enumeration ef = ((Vector) format.get("str_vars")).elements() ; 
	     ef.hasMoreElements() ;) {
	    Vector format_info = (Vector) ef.nextElement();
	    String format_str = (String) format_info.get(0);
	    Vector order = (Vector) format_info.get(1);
	    for (Enumeration e = ((Vector) resp).elements() ; e.hasMoreElements() ;) {
		Hashtable row = (Hashtable) e.nextElement();
		if(! row.containsKey(order.get(0)))
		    continue;
		try {
		    PrintfFormat pf = new PrintfFormat(format_str);
		    Object a[] = new Object[order.size()];
		    for(int i = 0; i < order.size(); i++) 
			a[i] = row.get(order.get(i));
		    showMessage(pf.sprintf(a), true);
		} catch (IllegalArgumentException ex) {
		    logger.error("Error formatting "+resp+"\n as: "+format, ex);
		    showMessage("An error occoured formatting the response, see log for details", true);
		}
	    }
	}
    }

    static boolean isMSWindows() { 
	String os = System.getProperty("os.name"); 
	if (os != null && os.startsWith("Windows")) return true; 
	return false; 
    }
    /**
     * @param args the command line arguments
     */
    public static void main(String[] args) {
	boolean gui = JBofh.isMSWindows();
        try {
	    boolean test_login = false;
	    String log4jPropertyFile = "/log4j_normal.properties";
	    for(int i = 0; i < args.length; i++) {
		if(args[i].equals("-q")) {
		    test_login = true;
		} else if(args[i].equals("-gui")) {
		    gui = true;
		} else if(args[i].equals("-nogui")) {
		    gui = false;
		} else if(args[i].equals("-d")) {
                    log4jPropertyFile = "/log4j.properties";
		}
	    }
	    if(test_login) {
		new JBofh("bootstrap_account", "test", gui, log4jPropertyFile);
	    } else {    // "test" md5: $1$F9feZuRT$hNAtCcCIHry4HKgGkkkFF/
                // insert into account_authentication values((select entity_id from entity_name where entity_name='bootstrap_account'), (select code from authentication_code where code_str='MD5-crypt'), '$1$F9feZuRT$hNAtCcCIHry4HKgGkkkFF/');
		new JBofh(System.getProperty("user.name"), null, gui, log4jPropertyFile);
	    }
	} catch (BofhdException be) {
	    String msg = "Caught error during init, terminating: \n"+ be.getMessage();
	    if(gui) {
		JOptionPane.showMessageDialog(null, msg, "Fatal error", 
					      JOptionPane.ERROR_MESSAGE);
                System.exit(0);
	    } else {
		System.out.println(msg);
	    }
	}
    }    
}
