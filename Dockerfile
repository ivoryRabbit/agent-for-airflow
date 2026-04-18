FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

# Install all LLM provider extras so the image works with any LLM_PROVIDER value
RUN pip install --no-cache-dir ".[claude,openai,gemini]" python-dotenv

COPY app/ ./app/

CMD ["python", "-m", "app.app"]
