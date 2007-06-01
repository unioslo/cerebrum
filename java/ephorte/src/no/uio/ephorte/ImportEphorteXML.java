package no.uio.ephorte;

import java.io.IOException;

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
                "  -u url : Alternative WebService URL\n"
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
        String fname = "/tmp/ephorte.xml";
        String url = null;
        
        if(args.length < 2) usage();
        for (int i = 0; i < args.length; i++) {
            String cmd = args[i];
            String val=args[++i];
            if(cmd.equals("-u")) {
                url = val;
            } else if (cmd.equals("-i")) {
                fname = val;
            } else {
                usage();
            }
        }
        EphorteGW ephorteGW = url == null ? new EphorteGW() : new EphorteGW(url);
        CustomXMLParser cp = new CustomXMLParser(fname);
        for (Person p : cp.getPersons()) {
            ephorteGW.updatePersonInfo(p);
        }
    }
}
