FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# emergentintegrations cikarilir (gereksiz), sonra paketler kurulur
RUN grep -v "emergentintegrations" requirements.txt > requirements_clean.txt && \
    pip install --no-cache-dir -r requirements_clean.txt

COPY . .

# Sifrelenmis session ve ayar dosyalari icin volume noktasi
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
