# Imagem oficial com Chromium + dependências do Playwright já instaladas.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CONQUISTAS_CONFIG=/app/conquistas.toml

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Dados (sessão, banco, logs) ficam em volume para sobreviver ao contêiner.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# O login precisa de interface gráfica: faça `conquistas login` no host e
# monte ./data no contêiner (veja o README).
ENTRYPOINT ["conquistas"]
CMD ["--help"]
