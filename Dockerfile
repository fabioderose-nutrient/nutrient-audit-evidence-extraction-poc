FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libicu-dev ca-certificates \
 && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8010
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY samples ./samples
COPY web ./web
COPY app ./app
EXPOSE 8010
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
