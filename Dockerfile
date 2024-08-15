FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get -y install git

COPY . .
COPY ca.pem /root/ca.pem
RUN pip install --upgrade pip
RUN pip install --no-dependencies --no-cache-dir -r requirements.txt
RUN playwright install 
RUN playwright install-deps
ENV SSL_CERT_FILE="/root/ca.pem"
CMD ["python", "app.py"]

EXPOSE 7860