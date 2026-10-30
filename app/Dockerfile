FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# O código e os dados entram por volume (docker-compose.yml): o coletor ao vivo
# roda no host e reescreve apuracao/data/; o container só lê.
USER nobody
CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "3030"]
