/*
 * CommandLine.java
 *
 * Created on November 4, 2002, 11:06 AM
 */

package no.uio.jbofh;

import java.util.Vector;
import java.util.Enumeration;
import org.gnu.readline.*;
import java.io.EOFException;
import org.apache.log4j.Category;
import java.io.IOException;
import java.text.ParseException;


/**
 *
 * @author  runefro
 */
public class CommandLine {
    Category logger;
    JBofh jbofh;

    /** Creates a new instance of CommandLine */
    public CommandLine(Category logger, JBofh jbofh) {
	this.jbofh = jbofh;
	if(! (jbofh != null && jbofh.guiEnabled)) {
	    Readline.initReadline("myapp");
	    this.logger = logger;
	    Runtime.getRuntime().addShutdownHook(new Thread() {
		    public void run() {
			Readline.cleanup();
		    }
		});
	}
    }

    /**
     * Split string into tokens, using whitespace as delimiter.
     * Matching '/" pairs can be used to include whitespace in the
     * tokens.  Sub-groups marked by matching parenthesis are returned
     * as sub-vectors. Sub-sub groups are not allowed.
     *
     * @param str
     * @return A vector of parsed tokens.
     */    
    Vector splitCommand(String str) throws ParseException {
        /* This could probably be done easier by using String.parse(), but that would require JDK1.4 */
        
        char chars[] = (str+" ").toCharArray();
        Vector ret = new Vector();
	Vector subCmd = null, curApp = ret;
        int i = 0, pstart = 0;
        Character quote = null;
        while(i < chars.length) {
            if(quote != null) {
                if(chars[i] == quote.charValue()) {                
                    if(i > pstart) {
                        curApp.add(new String(str.substring(pstart, i)));
		    }
                    pstart = i+1;
                    quote = null;
                }                
            } else {
                if(chars[i] == '\'' || chars[i] == '"') {
                    pstart = i+1;
                    quote = new Character(chars[i]);
                } else if(chars[i] == ' ' || chars[i] == '(' || chars[i] == ')') {                
                    if(i > pstart) {
                        curApp.add(new String(str.substring(pstart, i)));
		    }
                    pstart = i+1;
		    if(chars[i] == ')') {
			if(subCmd == null) 
			    throw new ParseException(") with no (", i);
			ret.add(curApp);
			curApp = ret;
			subCmd = null;
		    } else if(chars[i] == '(') {
			if(subCmd != null) 
			    throw new ParseException("nested paranthesis detected", i);
			subCmd = new Vector();
			curApp = subCmd;
		    }
                }
            }
            i++;
        }
	if(quote != null)
	    throw new ParseException("Missing end-quote", i);
	if(subCmd != null)
	    throw new ParseException("Missing end )", i);
        return ret;
    }
    
    String promptArg(String prompt, boolean addHist) throws IOException {
	if(jbofh.guiEnabled) {
            return jbofh.mainFrame.promptArg(prompt, addHist);
	}
        while (true) {
	    Vector oldHist = new Vector();
	    // A readline thingy where methods were non-static would have helped a lot.
	    if(! addHist) Readline.getHistory(oldHist);
	    String ret = Readline.readline(prompt);
	    if(! addHist) {
		Readline.clearHistory();
		for (Enumeration e = oldHist.elements() ; e.hasMoreElements() ;) 
		    Readline.addToHistory((String) e.nextElement());
	    }
	    if(ret == null) ret = "";
	    return ret;
        }
    }
    
    Vector getSplittedCommand() throws IOException, ParseException {
	return splitCommand(promptArg("jbofh> ", true));
    }

    public static void main(String[] args) {
	String tests[] = {
	    "dette er en test",
	    "en 'noe annerledes' test",
	    "en (parantes test 'med quote' test) hest",
	    "mer(test hei)du morn ",
	    "en liten (test av) dette) her",
	    "mer (enn du(skulle tro))"
	};
        CommandLine cLine = new CommandLine(Category.getInstance(CommandLine.class), null);
	for(int j = 0; j < tests.length; j++) {
	    System.out.println("split: --------"+tests[j]+"-----------");
	    try {
		Vector v = cLine.splitCommand(tests[j]);
		for(int i = 0; i < v.size(); i++)
		    System.out.println(i+": '"+v.get(i)+"'");
	    } catch (ParseException ex) {
		System.out.println("got: "+ex);
	    }
	}	
    }
}
