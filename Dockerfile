FROM tiangolo/uwsgi-nginx:python3.6

COPY ./app /app
RUN pip install -r /app/requirements.txt
COPY nginx.conf /etc/nginx/conf.d/

ENV UWSGI_INI /app/uwsgi.ini
WORKDIR /app

CMD ["/usr/bin/supervisord"]
