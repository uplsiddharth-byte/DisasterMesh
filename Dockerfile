FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

ENV PYTHONUNBUFFERED=1
ENV PORT=5001

EXPOSE 5001

CMD gunicorn -w 1 -b 0.0.0.0:$PORT --timeout 120 dashboard.app:app
