FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY app/ ./app/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0"]
