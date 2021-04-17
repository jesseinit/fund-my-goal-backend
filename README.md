# FundMe

FundMe is a crowd-funding platform designed to help users achieve their financial goals.

<!-- ## Code Coverage -->

<!-- [![codecov](https://codecov.io/gh/xerde/xerde-user/branch/staging/graph/badge.svg?token=P0PWWE03UU)](https://codecov.io/gh/xerde/xerde-user) -->

## Installing

```sh
    $ git clone https://github.com/jesseinit/fundme-backend.git
    $ cd fundme-backend
    $ git checkout main
    $ python -m venv venv
    $ source venv/bin/acivate
    $ pip install -r requirement.txt
```

- Create a `.env` file and copy/paste the environment variables from the `.env_example` file that's already existent in the root project directory.
- Create a postgreSQL database called `fundme_db` using the default `postgres` user and change the value of variable `DB_PASSWORD` in your `.env` file to your `postgres` user's password.
- Run the following commands to make the database migrations.

```sh
    $ python manage.py makemigrations && python manage.py migrate
    OR
    $ make migrate
```

## Running the application

Run the command below to run the application locally.

```
  $ python manage.py runserver
  OR
  $ make start-dev
```

## Running the tests

Run the command below to run the tests for the application.

```
  $ pytest
  OR
  $ make test
```

## Coverage

Run the command below to collect code coverage stats.

```
    make coverage
```

## Deployment

The application's deployment is still pending for the backend APIs. Details will be filled here as soon as it is ready.

## Built With

The project has been built with the following technologies so far:

- [Django](https://www.djangoproject.com/) - web framework for building websites using Python
- [Django Rest Framework](https://www.django-rest-framework.org) - is a powerful and flexible toolkit for building Web APIs.
- [Celery](www.celeryproject.org) - Celery is a task queue implementation for Python web applications used to asynchronously execute work outside the HTTP request-response cycle.
- [Docker](https://www.docker.com/) - Docker is a service products that uses OS-level virtualization to deliver software in packages called containers.
- [PostgreSQL](https://www.postgresql.org/) - Database management system used to persists the application's data.
- [Redis](https://redis.io/) - Redis is an open source (BSD licensed), in-memory data structure store, used as a database, cache, and message broker.
