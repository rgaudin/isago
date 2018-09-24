# isago
web-based isago calculator (Mali electricity prepaid system)

## deploy

``` sh
docker run -d -p 2111:80 rgaudin/isago
```

Sample nginx host configuration:

``` conf
server {
    server_name isago.ml;
    listen 80;
    listen [::]:80;

    location /.well-known/ {
        root /var/www/html/;
    }
    root /var/www;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    server_name isago.ml;
    listen 443 ssl http2;

    add_header Strict-Transport-Security "max-age=31536000;";
    add_header Access-Control-Allow-Origin "*";

    ssl_certificate /etc/letsencrypt/live/isago.ml/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/isago.ml/privkey.pem;

    location /.well-known/ {
        root /var/www/html/;
    }

    root /var/www;
    index index.html;

    location / {
        proxy_pass          http://127.0.0.1:2111;
        proxy_set_header    Host            $host;
        proxy_set_header    X-Real-IP       $remote_addr;
        proxy_set_header    X-Forwarded-for $remote_addr;
        port_in_redirect    off;
    }
}
```
