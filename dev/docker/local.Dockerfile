FROM python:3.7-slim

# Set up a safe working directory to put the code in
WORKDIR /root/work

# Do not copy anything other than reqs because this is a dev container and so we are using Docker volumes instead.
COPY requirements-dev.txt .
COPY requirements.txt .
# NOTE: this is a dev container so we should use a docker volume mount instead of copying in files

RUN apt-get update && \
    apt-get install -y gcc git libc-dev libpq-dev
# RUN pip install psycopg2
# Install python deps, both dev and regular
RUN pip install -r requirements-dev.txt

EXPOSE 8000

# We are using the same thing as PROD here but with the --reload option enabled, so it can be used as a dev server.
CMD ["gunicorn", "--reload", "--worker-tmp-dir", "/dev/shm", "--workers=2", "--threads=4", "--worker-class=gthread", "--log-file=-", "-b", ":8000", "app"]
# CMD ["sleep", "999999"]