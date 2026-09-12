FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uncomment to include the CrewAI summary layer + semantic search:
# COPY requirements-ai.txt .
# RUN pip install --no-cache-dir -r requirements-ai.txt

COPY app/ ./app/
COPY example-resume-bank.md .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
