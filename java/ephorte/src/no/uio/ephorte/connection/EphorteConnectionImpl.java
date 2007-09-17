package no.uio.ephorte.connection;

import java.net.MalformedURLException;
import java.rmi.RemoteException;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.util.Hashtable;
import java.util.Properties;
import java.util.Vector;

import javax.xml.rpc.ServiceException;

import no.gecko.www.ephorte.webservices.GetDataSetResponseGetDataSetResult;
import no.gecko.www.ephorte.webservices.ServicesLocator;
import no.gecko.www.ephorte.webservices.ServicesSoap;

import org.apache.axis.message.MessageElement;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

public class EphorteConnectionImpl extends EphorteConnection {
    String sessionID;
    ServicesSoap service;
    private Log log = LogFactory.getLog(EphorteConnectionImpl.class);
    private Properties props;

    public EphorteConnectionImpl(Properties props) {
        this.props = props;
        connect(props.getProperty("url"), props.getProperty("uname"),
                props.getProperty("password"), props.getProperty("database"));
    }

    protected void connect(String url, String userName, String passWord, String dataBase) {
        ServicesLocator locator = new ServicesLocator();
	log.info("Using web-service at url: " + url);
	log.info("Using database: " + dataBase + ", user: " + userName);
        try {
            if (url == null) {
                service = locator.getServicesSoap();
            } else {
                service = locator.getServicesSoap(new java.net.URL(url));
            }
            sessionID = service.login(userName, passWord, "", dataBase, null);
        } catch (ServiceException e) {
            e.printStackTrace();
            System.exit(1);
        } catch (RemoteException e) {
            e.printStackTrace();
            System.exit(1);
        } catch (MalformedURLException e) {
            e.printStackTrace();
            System.exit(1);
        }
    }

    protected int updatePersonByXML(String xml) throws RemoteException {
        return service.updatePersonByXML(sessionID, xml, "");
    }

    /**
     * Fetches data from the specified ePhorte table, and returns database rows
     * as a Vector of Hashtables
     * 
     * @param criteriaCollectionString
     * @param tagName
     * @return
     * @throws RemoteException
     */
    public Vector<Hashtable<String, String>> getDataSet(String criteriaCollectionString,
            String tagName) throws RemoteException {
        Vector<Hashtable<String, String>> ret = new Vector<Hashtable<String, String>>();
        GetDataSetResponseGetDataSetResult res = service.getDataSet(sessionID,
                criteriaCollectionString+";MaxRecords=30000");  
        /* MaxRecords was a guess based on 
         * C:\Program Files\ePhorteWeb\shared\WebServices\DataSamples\ASP\ExtCust.asp */
        for (MessageElement me : res.get_any()) {
	    /* TODO: This hack should not run in a production system. 
	     *       For now MaxRecords and AbsoluteMaxRecords will be
	     *       set to values large enough to avoid this
	     *       situation, but this code must be more robust.
	     */
            NodeList nl = me.getElementsByTagName("PartialResult");
            for (int i = 0; i < nl.getLength(); i++) {
                Node node = nl.item(i);
                if ("true".equals(node.getFirstChild().getNodeValue())) {
                    log.warn("WebService returned partial result.  Using JDBC hack");
                    ret = queryDatabase(criteriaCollectionString.substring(criteriaCollectionString.indexOf('=') + 1));
                    log.info("getDataSet("+criteriaCollectionString+") found "+ret.size()+" entries (using JDBC)");
                    return ret;
                }
            }
            nl = me.getElementsByTagName(tagName);
            Hashtable<String, String> entry = new Hashtable<String, String>();
            for (int i = 0; i < nl.getLength(); i++) {
                Node node = nl.item(i);
                NodeList c = node.getChildNodes();
                for (int j = 0; j < c.getLength(); j++) {
                    Node n2 = c.item(j);
                    entry.put(n2.getLocalName(), n2.getFirstChild().getNodeValue());
                    // System.out.println(n2.getLocalName() +" -> "+
                    // n2.getFirstChild().getNodeValue());
                }
                if (!entry.isEmpty())
                    ret.add(entry);
                entry = new Hashtable<String, String>();
            }
        }
        log.info("getDataSet("+criteriaCollectionString+") found "+ret.size()+" entries (using WebService)");
        return ret;
    }

    private Vector<Hashtable<String, String>> queryDatabase(String table) {
        Vector<Hashtable<String, String>> ret = new Vector<Hashtable<String, String>>();
	log.debug("Try to connect to db (using JDBC)");
        try {
            Class.forName(props.getProperty("db_driver"));
        } catch (ClassNotFoundException e) {
            e.printStackTrace();
            return null;
        }
        try {
            Connection conn = DriverManager.getConnection(props.getProperty("db_url"), props
                    .getProperty("db_user"), props.getProperty("db_password"));
            PreparedStatement qry = conn.prepareStatement("SELECT * FROM " + table);
            ResultSet rs = qry.executeQuery();
            ResultSetMetaData meta = rs.getMetaData();
            String[] cols = new String[meta.getColumnCount()];
            for (int n = 1; n <= meta.getColumnCount(); n++) {
                cols[n - 1] = meta.getColumnName(n);
            }

            while (rs.next()) {
                Hashtable<String, String> entry = new Hashtable<String, String>();
                for (int n = 0; n < cols.length; n++) {
                    String tmp = rs.getString(cols[n]);
                    if (tmp != null) {
                        entry.put(cols[n], tmp);
                    }
                }
                ret.add(entry);
            }

            rs.close();
            qry.close();
            conn.close();
            return ret;
        } catch (SQLException e) {
            e.printStackTrace();
            return null;
        }
    }

}
