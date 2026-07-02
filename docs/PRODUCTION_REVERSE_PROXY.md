# T-Food Production Reverse Proxy Guide

Target: Ubuntu VPS with Docker Compose, a host-level Nginx reverse proxy, and
Let's Encrypt certificates.

The Docker `frontend` service already serves the compiled React app, proxies
`/api/`, `/admin/`, and `/ws/` to Django, and serves public static/media files.
The host Nginx should terminate HTTPS and proxy traffic to the frontend
container port.

## Host Nginx Site

Create `/etc/nginx/sites-available/tfood`:

```nginx
server {
    listen 80;
    server_name your-domain.example www.your-domain.example;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.example www.your-domain.example;

    ssl_certificate /etc/letsencrypt/live/your-domain.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.example/privkey.pem;

    client_max_body_size 10M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/tfood /etc/nginx/sites-enabled/tfood
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.example -d www.your-domain.example
```

## Media Rules

Public media may be served through the Docker `frontend` service from
`/media/`. Examples include public restaurant images, menu/product images, and
approved review photos.

Private media must never be mounted into host Nginx or served directly.
Examples include verification documents and pending, rejected, or hidden review
photos. Those files stay in the `private_media_data` volume and are accessed
only through authenticated backend endpoints.

## Security Checklist

- PostgreSQL and Redis are not exposed on public ports.
- Host Nginx exposes only ports 80 and 443.
- `APP_PORT=8088` binds the frontend container to localhost-facing reverse
  proxy traffic in the deployment guide.
- `SECURE_SSL_REDIRECT=True` after HTTPS is active.
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `CORS_ALLOWED_ORIGINS` contain
  only the production domain origins.
- Upload limit is 10 MB at host Nginx and in the frontend container.
- Provider credentials and Django secrets are stored only in `.env` or a future
  secrets manager, never in Git.

## Verification

```bash
curl -I https://your-domain.example/
curl -i https://your-domain.example/api/v1/health/
curl -i https://your-domain.example/api/v1/health/?detail=1
```

The detailed health response should report database, cache, media storage,
channel layer, Celery worker, Celery Beat, and dispatch worker readiness without
exposing secrets or private media paths.
