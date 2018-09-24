FROM tiangolo/uwsgi-nginx:python3.6

RUN pip install -r /app/requirements.txt

COPY nginx.conf /etc/nginx/conf.d/
COPY ./app /app

ENV UWSGI_INI /app/uwsgi.ini
WORKDIR /app

CMD ["/usr/bin/supervisord"]
