package no.uio.ephorte.connection;

public class TooManyRecordsException extends Exception {
    private static final long serialVersionUID = 1L;

    public TooManyRecordsException(String string) {
        super(string);
    }
}
