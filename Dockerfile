FROM ubuntu:xenial

RUN apt-get update && apt-get install -y \
    python-dev \
    python-pip \
    python-setuptools \
    virtualenv \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY . /taxii
WORKDIR /taxii
RUN pip install pymongo
RUN pip install .
RUN pip install pymongo
WORKDIR /var/taxii
EXPOSE 5000

CMD ["medallion", "--host", "0.0.0.0", "config.json"]
