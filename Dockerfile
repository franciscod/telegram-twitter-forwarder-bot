FROM python:3.7
WORKDIR /usr/src/app
COPY . .
RUN pip install -r requirements.txt
CMD ["python3", "main.py"]
