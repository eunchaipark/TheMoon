FROM apache/spark:3.5.3-python3

USER root

RUN pip install --no-cache-dir \
    sentence-transformers==3.2.1 \
    psycopg2-binary==2.9.10 \
    numpy \
    && pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

RUN curl -L --retry 3 --retry-delay 5 -o /opt/spark/jars/postgresql-42.7.3.jar \
    https://jdbc.postgresql.org/download/postgresql-42.7.3.jar

COPY jobs/ /opt/spark/jobs/

USER 185