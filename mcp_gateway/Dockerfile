FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8001
CMD ["meme-games-mcp", "--host", "0.0.0.0", "--port", "8001"]
