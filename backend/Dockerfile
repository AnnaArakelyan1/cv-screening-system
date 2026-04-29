FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    fonts-dejavu-core \
    openssl \
    && rm -rf /var/lib/apt/lists/*

RUN openssl req -x509 -newkey rsa:4096 -keyout /app/key.pem -out /app/cert.pem \
    -days 365 -nodes -subj "/CN=localhost"

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install sentence-transformers
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]