# 1. Usa o Alpine Linux: O padrão ouro de segurança e leveza
FROM python:3.10-alpine3.22

WORKDIR /app

# 2. Instala dependências do PostgreSQL específicas para Alpine
# Dividimos em "pacotes de uso" e "pacotes de compilação" (.build-deps)
RUN apk update && apk upgrade && apk add --no-cache \
    postgresql-libs \
    tzdata \
    && apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    postgresql-dev \
    linux-headers

# 3. Copia os requisitos e atualiza o pip por segurança
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. FAXINA DE SEGURANÇA: Apaga os compiladores (gcc) de dentro do contêiner.
# Se um hacker invadir, ele não terá ferramentas para compilar malwares lá dentro.
RUN apk --purge del .build-deps

# 5. Copia o código
COPY . .

EXPOSE 5000

# 6. Inicia com Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "main:app"]
