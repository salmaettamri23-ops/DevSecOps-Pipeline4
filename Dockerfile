FROM python:3.11-slim

WORKDIR /workspace

# Récupère les derniers patchs de sécurité Debian (perl, util-linux, etc.)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip "setuptools>=78.1.1" wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 3000

CMD ["python", "app/main.py"]