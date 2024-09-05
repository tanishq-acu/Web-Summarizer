FROM python:3.11-slim

# Fixed layers
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get -y install git && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip

# Add dependent layers if requirements.txt changes
COPY requirements.txt .
RUN pip install --no-dependencies --no-cache-dir -r requirements.txt && \
    playwright install && \
    playwright install-deps

RUN pip install flask fastapi
RUN pip install opentelemetry-instrumentation-django opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-flask
RUN pip install opentelemetry-exporter-jaeger
RUN pip install acutracer==0.1.10
# Add code and setup env vars
COPY . .
ENV SSL_CERT_FILE="/certs/ca.pem"

CMD ["python", "app.py"]

EXPOSE 7860
