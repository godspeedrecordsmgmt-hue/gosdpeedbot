FROM python:3.10-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY bot.py .
COPY .env .

# Создаем директорию для данных
RUN mkdir -p /app/data /app/logs /app/photos

# Открываем порт (если нужен)
EXPOSE 8080

# Запускаем бота
CMD ["python", "bot.py"]
