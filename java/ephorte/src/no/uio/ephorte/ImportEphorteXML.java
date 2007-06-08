package no.uio.ephorte;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Properties;
import java.util.Vector;

import javax.xml.parsers.ParserConfigurationException;

import no.uio.ephorte.connection.EphorteGW;
import no.uio.ephorte.data.Person;
import no.uio.ephorte.xml.CustomXMLParser;

import org.xml.sax.SAXException;

public class ImportEphorteXML {
    private static void usage() {
        System.out.println("Usage: import [options]\n"+
                "This script can be used to import data to ePhorte.\n\n"+
                "  -i fname : import specified filename\n"+
                "  -p fname : property filename (see example.props)\n"+
                "  -d table : dump table in a somewhat readable format\n"+
                "  -t tag   : tag to select from -d option"
                );
        System.exit(1);
    }

    /**
     * @param args
     * @throws ParserConfigurationException
     * @throws IOException
     * @throws SAXException
     */
    public static void main(String[] args) throws SAXException, IOException,
            ParserConfigurationException {
        String fname = null, table = null, tag = null;
        Properties props = null;
        
        if(args.length < 2) usage();
        for (int i = 0; i < args.length; i++) {
            String cmd = args[i];
            String val=args[++i];
            if(cmd.equals("-p")) {
                props = new Properties();
                props.load(new FileInputStream(val));
            } else if (cmd.equals("-i")) {
                fname = val;
            } else if (cmd.equals("-d")) {
                table = val;
            } else if (cmd.equals("-t")) {
                tag = val;
            } else {
                usage();
            }
        }
        if(props == null) {
            System.err.println("-p required");
            System.exit(1);
        }
        EphorteGW ephorteGW = new EphorteGW(props);
        if(table != null) {
            // Example: -d pernavn -t PerNavn
            Vector<String> keys = new Vector<String>();
            Vector<Hashtable<String, String>> tmp = ephorteGW.getConn().getDataSet("object="+table, tag);
            for (Hashtable<String, String> ht : tmp) {
                for ( Enumeration<String> e = ht.keys(); e.hasMoreElements() ;) {
                    String n = e.nextElement();
                    if(! keys.contains(n)) {
                        keys.add(n);
                    }
                }
            }                
            for (String k : keys) {
                System.out.print(k+";");
            }
            System.out.println();
            for (Hashtable<String, String> ht : tmp) {
                for (String k : keys) {
                    System.out.print(ht.get(k)+";");
                }
                System.out.println();
            }
        } else if (fname != null) {
            ephorteGW.prepareSync();
            CustomXMLParser cp = new CustomXMLParser(fname);
            for (Person p : cp.getPersons()) {
                ephorteGW.updatePersonInfo(p);
            }
        }
    }
}
