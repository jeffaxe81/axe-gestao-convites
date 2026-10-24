FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/isadora
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home isadora
COPY --chown=isadora:isadora app ./app
COPY --chown=isadora:isadora wsgi.py ./wsgi.py
USER isadora
EXPOSE 8080
CMD ["sh", "-c", "python -m app.db migrate && exec gunicorn --bind 0.0.0.0:8080 --workers 2 --threads 4 --access-logfile - wsgi:app"]
