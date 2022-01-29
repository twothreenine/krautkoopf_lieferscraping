FROM python:3.10

WORKDIR /usr/src/app
COPY . /usr/src/app
RUN pip install -r requirements.txt

VOLUME /usr/src/app/config
EXPOSE 8080
CMD ["python3", "web.py"]
