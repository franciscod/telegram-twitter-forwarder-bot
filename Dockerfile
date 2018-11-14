#Download base image python 3.5
FROM python:3.5

WORKDIR /bot

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python3.5", "main.py"]

