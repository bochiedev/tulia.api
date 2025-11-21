# 23 — Deployment, Caching & Performance

- Django + DRF running behind Nginx/Gunicorn.
- Celery workers + Beat using Redis.
- PostgreSQL for primary data.
- Redis:
  - Caching
  - Rate limiting
  - Temporary OTP / ephemeral data.

## 23.1 Caching

- Cache frequently requested catalog slices per tenant.
- Cache popular FAQ answers (with invalidation when docs change).

## 23.2 Scalability

- Horizontal scaling of:
  - Web workers
  - Celery workers
- Use queues for:
  - Inbound message processing
  - RAG queries
  - Payment provider calls
