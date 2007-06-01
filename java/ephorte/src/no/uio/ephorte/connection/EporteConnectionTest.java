package no.uio.ephorte.connection;

import java.io.File;
import java.io.IOException;
import java.rmi.RemoteException;
import java.util.Hashtable;
import java.util.Vector;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;

import org.w3c.dom.Document;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

/**
 * For offline testing of the sync logic. Uses pre-generated XML-responses to
 * queries stored in /tmp/test_TYPE.xml, where TYPE corresponds to the rvalue in
 * criteriaCollectionString. The XML can be aquired by running once in a live
 * environment, while running the axis framework in debug mode. The resulting
 * xml-blocks (the NewDataSet tag and its contents) can be extracted from the
 * axis.log.
 * 
 * The log4j.properties file can look something like this:
 * log4j.rootLogger=WARN, A1 log4j.logger.org.apache.axis.transport=DEBUG
 * log4j.appender.A1=org.apache.log4j.FileAppender
 * log4j.appender.A1.File=axis.log
 * log4j.appender.A1.layout=org.apache.log4j.PatternLayout
 * log4j.appender.A1.layout.ConversionPattern=%-4r [%t] %-5p %c %x - %m%n
 */
public class EporteConnectionTest extends EphorteConnection {
    DocumentBuilderFactory factory;

    protected void connect() {
        factory = DocumentBuilderFactory.newInstance();
    }

    protected Vector<Hashtable<String, String>> getDataSet(String criteriaCollectionString,
            String tagName) {
        String ftype = criteriaCollectionString
                .substring(criteriaCollectionString.indexOf('=') + 1);
        Vector<Hashtable<String, String>> ret = new Vector<Hashtable<String, String>>();
        DocumentBuilder builder;
        try {
            builder = factory.newDocumentBuilder();
            Document document = builder.parse(new File("/tmp/test_" + ftype + ".xml"));
            NodeList nl = document.getElementsByTagName(tagName);
            for (int i = 0; i < nl.getLength(); i++) {
                Hashtable<String, String> entry = new Hashtable<String, String>();
                Node node = nl.item(i);
                NodeList c = node.getChildNodes();
                for (int j = 0; j < c.getLength(); j++) {
                    Node n2 = c.item(j);
                    entry.put(n2.getNodeName(), n2.getFirstChild().getNodeValue());
                }
                ret.add(entry);
            }
        } catch (ParserConfigurationException e) {
            e.printStackTrace();
        } catch (SAXException e) {
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        }
        return ret;
    }

    @Override
    protected int updatePersonByXML(String xml) throws RemoteException {
        return 99;
    }

}
