package no.uio.jbofh;

import java.awt.Frame;
import java.io.IOException;

/**
 * These methods are used by the gui, which is currently implemented
 * in swing.  By using this interface, it is possible to compile jbofh
 * when swing is not available.
*/

public interface JBofhFrame {
    java.awt.Frame frame = null;

    public String getPasswordByJDialog(String prompt, Frame parent) 
        throws MethodFailedException;
    public String getCmdLineText();
    public String promptArg(String prompt, boolean addHist) throws IOException;
    public void showMessage(String msg, boolean crlf);
    public boolean confirmExit();
    public void showWait(boolean on);
    public void showErrorMessageDialog(String title, String msg);

}

