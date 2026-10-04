FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --system --uid 10001 appuser && mkdir /data && chown appuser /data
COPY app/ /app/
COPY curriculum/ /app/docs/curriculum/
COPY vorlagen/ /app/docs/vorlagen/

ENV DATA_DIR=/data DOCS_DIR=/app/docs
USER appuser
VOLUME /data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

# 1 Worker + Threads: SQLite-Schreibzugriffe und Login-Drosselung bleiben konsistent
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8080", "--access-logfile", "-", "server:app"]
