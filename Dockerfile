FROM python:3.11-slim

WORKDIR /srv/scam-guard

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY static ./static
COPY tests ./tests

RUN mkdir -p /srv/scam-guard/data /srv/scam-guard/audio/briefings

ENV SCAMGUARD_DB_PATH=/srv/scam-guard/data/scamguard.db
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
