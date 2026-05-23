FROM python:3.11-slim

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

EXPOSE 7860

CMD ["uvicorn", "webapp.app:app", "--host", "0.0.0.0", "--port", "7860"]
