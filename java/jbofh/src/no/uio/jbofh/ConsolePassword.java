package no.uio.jbofh;

import java.io.*;
import javax.swing.JOptionPane;
import javax.swing.JPasswordField;
import javax.swing.JDialog;
import java.awt.Frame;

/**
 * <code>ConsolePassword</code> is an attempt to create a pure java
 * class that can be used to read a password from the console with
 * echo turned off.
 *
 * This is done by trying the following aproaches:
 * - run the /bin/stty command to turn echo on/off
 * - using JTextField 
 * - using a bussy-loop in a separate thread that keeps overwriting
 *   the area where the keypress normally is shown
 *
 * This class should be unneccesary, but Sun has unfortunately decided
 * that Java should not support the console.  Please vote for the > 6
 * years old bug 4050435.
 * http://developer.java.sun.com/developer/bugParade/bugs/4050435.html
 *
 * @author  runefro
 */

class ConsolePassword {
    class MethodFailedException extends Exception { }

    public void setEcho(boolean on) throws MethodFailedException {
        String[] cmd = {
            "/bin/sh",
            "-c",
            "/bin/stty " + (on ? "echo" : "-echo") + " < /dev/tty"
        };
        int exitcode = 0;
        try {
            Process p = Runtime.getRuntime().exec(cmd);
            exitcode = p.waitFor();
        } catch (IOException e) { 
            exitcode = -1; 
        } catch (InterruptedException e) { 
            exitcode = -1; 
        }
        if(exitcode != 0) {
            throw new MethodFailedException();
        }
    }

    public String getPasswordByStty(String prompt) 
        throws MethodFailedException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));

        try {
            setEcho(false);
            System.out.print(prompt);
            String ret = br.readLine();
            System.out.println();
            return ret;
        } catch (IOException e) {
            return null;
        } finally {
            setEcho(true);
        }
    }

    public String getPasswordByJDialog(String prompt, Frame parent) 
        throws MethodFailedException {
        try {
            JPasswordField pf = new JPasswordField(10);
            JOptionPane pane = new JOptionPane(pf, JOptionPane.QUESTION_MESSAGE, 
                JOptionPane.OK_CANCEL_OPTION);
            JDialog dialog = pane.createDialog(parent, prompt);
            pf.requestFocus();
            dialog.show();
            dialog.dispose();
            Object value = pane.getValue();
            if(((Integer) value).intValue() == JOptionPane.OK_OPTION) 
                return new String(pf.getPassword());
            return null;
        } catch (java.lang.NoClassDefFoundError e) {
            throw new MethodFailedException();
        }
    }

    class HidingThread extends Thread {
        private boolean keep_hiding = true;
        private String prompt;
        public HidingThread(String prompt) {
            super();
            this.prompt = prompt;
        }
        public void run() {
            while(keep_hiding) {
                System.out.print("\r"+prompt+" \r"+prompt);
                try {
                    sleep(5);
                }catch (InterruptedException e) { }
            }
        }
        public void stopHiding() {
            keep_hiding = false;
        }
    }

    public String getPasswordByBusyLoop(String prompt) 
        throws MethodFailedException {
        
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        HidingThread t = new HidingThread(prompt);
        t.start();
        String ret;
        try {
            ret = br.readLine();
        } catch (IOException e) {
            throw new MethodFailedException();
        } finally {
            t.stopHiding();
        }
        return ret;
    }

    public String getPassword(String prompt) {
        try {
            return getPasswordByStty(prompt);
        } catch (MethodFailedException e) {}
        try {
            return getPasswordByJDialog(prompt, null);
        } catch (MethodFailedException e) {}
        try {
            return getPasswordByBusyLoop(prompt);
        } catch (MethodFailedException e) {}
        return null;
    }

    public static void main(String[] args) {
        ConsolePassword cp = new ConsolePassword();
        System.out.println("You typed: "+cp.getPassword("Enter your password: "));
    }
}
