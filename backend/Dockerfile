FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY startup.sh ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY add_admin.py ./
EXPOSE 8000
# Run via `sh` so a lost exec bit (common from Windows checkouts) can't break boot.
CMD ["sh", "./startup.sh"]
