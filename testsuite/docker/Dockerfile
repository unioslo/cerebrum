FROM python:2-alpine
RUN apk add --no-cache bash gcc g++ swig python-dev postgresql-client \
                       postgresql-dev libffi-dev openssl-dev openldap-dev \
                       cyrus-sasl-dev gettext libxml2 libxml2-dev libxslt \
                       libxslt-dev gpgme gpgme-dev libffi-dev py-psycopg2
COPY ../../requirements.txt /requirements.txt
COPY test-requirements.txt /test-requirements.txt
RUN pip install -r /requirements.txt
RUN pip install -r /test-requirements.txt
RUN adduser -S cerebrum
