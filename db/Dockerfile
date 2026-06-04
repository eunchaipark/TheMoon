FROM pgvector/pgvector:pg16

# init.sql 은 docker-entrypoint-initdb.d 에 넣으면 자동 실행

COPY init.sql /docker-entrypoint-initdb.d/init.sql
