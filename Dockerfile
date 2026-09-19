FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-hosted.txt ./
RUN pip install --no-cache-dir -r requirements-hosted.txt
COPY ps1 ./ps1
COPY web ./web
COPY specs ./specs
COPY data ./data
RUN useradd --uid 10001 --create-home tracklight && mkdir /data && chown tracklight:tracklight /data
USER tracklight
ENV PORT=8080 TRACKLIGHT_DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/api/health',timeout=3)"
CMD ["python", "-m", "ps1.hosted"]
