# Dockerfile for Railway/Heroku deployment

FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "ict_bot.py"]