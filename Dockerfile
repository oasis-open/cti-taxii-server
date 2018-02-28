FROM python:alpine3.6

COPY . /taxii
WORKDIR /taxii
RUN pip install .

WORKDIR /var/taxii
EXPOSE 5000

CMD ["medallion", "config.json"]
