FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
COPY bot ./bot
RUN pip install --no-cache-dir -e .

COPY . .
