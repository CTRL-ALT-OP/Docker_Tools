FROM python:3.13.2-alpine3.21@sha256:323a717dc4a010fee21e3f1aac738ee10bb485de4e7593ce242b36ee48d6b352
WORKDIR /app

# your Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy in code + tests
COPY . .

CMD ["sh"]