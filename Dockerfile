FROM public.ecr.aws/bedrock-agentcore/runtime:latest-python3.12

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

CMD ["python", "app.py"]
