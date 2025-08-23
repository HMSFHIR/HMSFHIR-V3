
<img width="1024" height="1024" alt="HMSFHIRcropped" src="https://github.com/user-attachments/assets/dafbd74c-3009-4578-a724-860228f28cda" />


# FHIR HMS Core

This project is the core backend for a Healthcare Management System (HMS) built with Django, PostgreSQL, Redis, and Celery. It provides FHIR-compliant APIs and background task processing.

## Features

- **Django Web Server**: Main application server.
- **PostgreSQL**: Database for persistent storage.
- **Redis**: In-memory data store for caching and Celery broker.
- **Celery**: Distributed task queue for background jobs.
- **Docker Compose**: Easy orchestration of all services.

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/MensahPrince/HMSFHIR-V3
    cd fhir_hms/core
    ```

2. Start the services:
    ```bash
    docker-compose up --build
    ```

3. The web server will be available at [http://localhost:8000](http://localhost:8000).

### Services

| Service       | Port   | Description                |
|---------------|--------|----------------------------|
| Web (Django)  | 8000   | Main API server            |
| PostgreSQL    | 5433   | Database                   |
| Redis         | 6379   | Cache & Celery broker      |
| Celery Worker | N/A    | Background task processor  |
| Celery Beat   | N/A    | Periodic task scheduler    |

## Development

- Code is mounted into containers for live reload.
- Database data is persisted in a Docker volume.

## Useful Commands

- Run migrations manually:
  ```bash
  docker-compose exec web python manage.py migrate
  ```
- Access Django shell:
  ```bash
  docker-compose exec web python manage.py shell
  ```
  ## Creating a Superuser

To create a Django superuser for admin access, run:

```bash
docker-compose exec web python manage.py createsuperuser
```

## License

See [LICENSE](../LICENSE) for details.


