FROM python:alpine3.6

RUN pip install medallion

WORKDIR /var/taxii
EXPOSE 5000

CMD ["medallion", "config.json"]
