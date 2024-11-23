# Використання базового образу Python
FROM python:3.12

# Встановлення робочої директорії у контейнері
WORKDIR /app

# Копіювання файлів проекту в контейнер
COPY . /app

# Встановлення залежностей
RUN pip install -r requirements.txt

# Команда для запуску застосунку
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8800", "-w", "1"]
