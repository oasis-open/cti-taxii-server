FROM python:alpine3.6

COPY . /taxii
WORKDIR /taxii
RUN pip install .
RUN pip install pymongo
WORKDIR /var/taxii
EXPOSE 5000

CMD ["medallion", "config.json"]
