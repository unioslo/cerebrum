package no.uio.ephorte.data;

public class BadDataException extends Exception {
    private static final long serialVersionUID = 1L;

    public BadDataException(String string) {
        super(string);
    }

}
