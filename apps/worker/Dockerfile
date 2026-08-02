FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Variáveis de ambiente vêm do runtime (Railway/VPS/docker run --env-file),
# não de um .env copiado pra imagem — nunca commitar segredo na imagem.
CMD ["python", "-m", "main"]
