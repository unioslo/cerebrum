/*
 * JBofhFrame.java
 *
 * Created on June 4, 2003, 11:23 AM
 */

package no.uio.jbofh;

import java.awt.BorderLayout;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Dimension;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.awt.event.ActionListener;
import java.awt.event.ActionEvent;
import java.awt.EventQueue;
import javax.swing.JPanel;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JTextField;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import java.io.IOException;

import javax.swing.KeyStroke;
import java.awt.event.KeyEvent;
import javax.swing.AbstractAction;
import javax.swing.Action;
import javax.swing.text.Keymap;

/**
 *
 * @author  runefro
 */
public class JBofhFrame implements ActionListener {
    JTextArea tfOutput;
    JTextField tfCmdLine;
    JLabel lbPrompt;
    JFrame frame;
    private boolean isBlocking = false;
    private boolean wasEsc = false;

    class MyKeyAction extends AbstractAction {
        public MyKeyAction(String name) {
            super(name);
        }
        
        public void actionPerformed(ActionEvent e) {
            if("esc".equals(getValue(Action.NAME))) {
                wasEsc = true;
                releaseLock();
            }
        }
    }

    public JBofhFrame() {
        makeGUI();
    }

    void makeGUI() {
	JPanel np = new JPanel();
	JScrollPane sp = new JScrollPane(tfOutput = new JTextArea());
	frame = new JFrame("JBofh");
	
	tfOutput.setEditable(false);
	np.setLayout(new GridBagLayout());
	GridBagConstraints gbc = new GridBagConstraints();
	gbc.anchor = GridBagConstraints.WEST;
	np.add(lbPrompt = new JLabel(), gbc);
        gbc.fill = GridBagConstraints.HORIZONTAL;
	gbc.gridwidth = GridBagConstraints.REMAINDER;
	gbc.weightx = 1.0;
	np.add(tfCmdLine = new JTextField(), gbc);
	tfCmdLine.addActionListener(this);
	frame.getContentPane().add(sp, BorderLayout.CENTER);
	frame.getContentPane().add(np, BorderLayout.SOUTH);

        // We want control over some keys used on tfCmdLine
        tfCmdLine.setFocusTraversalKeysEnabled(false);
        Keymap keymap = tfCmdLine.addKeymap("MyBindings", tfCmdLine.getKeymap());
        keymap.addActionForKeyStroke(KeyStroke.getKeyStroke(KeyEvent.VK_TAB, 0), 
            new MyKeyAction("tab"));
        keymap.addActionForKeyStroke(KeyStroke.getKeyStroke(KeyEvent.VK_DOWN, 0), 
            new MyKeyAction("down"));
        keymap.addActionForKeyStroke(KeyStroke.getKeyStroke(KeyEvent.VK_UP, 0), 
            new MyKeyAction("up"));
        keymap.addActionForKeyStroke(KeyStroke.getKeyStroke(KeyEvent.VK_ESCAPE, 0), 
            new MyKeyAction("esc"));
        tfCmdLine.setKeymap(keymap);

        frame.addWindowListener(new WindowAdapter() {
            public void windowClosing(WindowEvent e) {
                System.exit(0);
            }
        });
	frame.pack();
	frame.setSize(new Dimension(700,400));
        frame.setVisible(true);
    }

    boolean confirmExit() {
        if(JOptionPane.OK_OPTION == JOptionPane.showConfirmDialog(frame, "Really exit?", 
               "Please confirm", JOptionPane.OK_CANCEL_OPTION, JOptionPane.WARNING_MESSAGE))
            return true;
        return false;
    }

    void showMessage(String msg, boolean crlf) {
        tfOutput.append(msg);
        if(crlf) tfOutput.append("\n");
        tfOutput.setCaretPosition(tfOutput.getText().length());
    }
    
    String promptArg(String prompt, boolean addHist) throws IOException {
        /* We lock the current thread so that execution does not
         * continue until JBofh.actionPerformed releases the
         * lock  */
        lbPrompt.setText(prompt);
        tfCmdLine.requestFocusInWindow();
        synchronized (tfCmdLine.getTreeLock()) {
            while (true) {
                try {
                    isBlocking = true;
                    tfCmdLine.getTreeLock().wait();  // Lock
                    if(wasEsc){
                        wasEsc = false;
                        throw new IOException("escape hit");
                    }
                    String text = tfCmdLine.getText();
                    showMessage(prompt+text, true);
                    tfCmdLine.setText("");
                    // If we don't set the caret position, requestFocus failes
                    tfCmdLine.setCaretPosition(0);
                    return text;
                } catch (InterruptedException e) {
                    return null;
                }
            }
        }
    }

    public void actionPerformed(ActionEvent evt) {
        if(evt.getSource() == tfCmdLine) {
            releaseLock();
	}
    }

    protected void releaseLock() {
        if(! isBlocking) return;
        synchronized (tfCmdLine.getTreeLock()) {
            isBlocking = false;
            EventQueue.invokeLater(new Runnable(){ public void run() {} });
            tfCmdLine.getTreeLock().notifyAll();
        }
    }
}
