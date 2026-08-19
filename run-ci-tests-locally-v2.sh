# Note -- AWS tests will fail without setting AWS keys

AWS_ACCESS_KEY_ID=TODO
AWS_DEFAULT_REGION=TODO
AWS_SECRET_ACCESS_KEY=TODO

POSTGRES_HOST_AUTH_METHOD=trust
HEADLESS=TRUE
DOCKER_IMAGE=psynet-ci-local
DOCKER_HOST=tcp://docker:2375
DOCKER_DRIVER=overlay2
DOCKER_TLS_CERTDIR=""

# Sets up required services (postgres, redis etc) on the Dallinger Docker network.
echo "Checking Docker access..."
if [[ "$(docker network ls | grep "could not be found in this WSL 2 distro")" != "" ]]
then
  echo "Docker installation could not be found in this WSL 2 distro. Did you remember to launch Docker Desktop?"
  exit 1
fi

echo "Confirming that the Dallinger network exists..."
if [[ "$(docker network ls | grep dallinger)" = "" ]]
then
  echo "...no. Creating now..."
  docker network create dallinger
else
  echo "...yes."
fi

echo "Confirming that dallinger_redis is running..."
docker start dallinger_redis || true
if [[ "$(docker ps | grep dallinger_redis)" = "" ]]
then
  echo "...no. Creating now..."
  docker run -d --name dallinger_redis --network=dallinger \
    -v dallinger_redis:/data \
    redis redis-server \
    --appendonly yes
else
  echo "...yes."
fi

echo "Confirming that dallinger_postgres is running..."
docker start dallinger_postgres || true
if [[ "$(docker ps | grep dallinger_postgres)" = "" ]]
then
  echo "...no. Creating now..."
  docker run -d --name dallinger_postgres --network=dallinger \
  -e POSTGRES_USER=dallinger \
  -e POSTGRES_PASSWORD=dallinger \
  -e POSTGRES_DB=dallinger \
  -v dallinger_postgres:/var/lib/postgresql/data \
  postgres:12
else
  echo "...yes."
fi

# Builds the Docker image
docker build --tag "$DOCKER_IMAGE" .

# Runs the automated tests
docker run \
  -e HEADLESS=TRUE \
  -e AWS_ACCESS_KEY_ID -e AWS_DEFAULT_REGION -e AWS_SECRET_ACCESS_KEY \
  -e REDIS_URL=redis://dallinger_redis:6379 \
  -e DATABASE_URL=postgresql://dallinger:dallinger@dallinger_postgres/dallinger \
  --network dallinger \
  $DOCKER_IMAGE bash -c \
  "pytest --ignore=tests/local_only --ignore=tests/isolated --chrome --exitfirst tests"

# --existfirst flag stops tests on first error

# Run the following code to enter a terminal in the Docker image. This can be very helpful for debugging failures.
#docker run \
#  -e HEADLESS=TRUE \
#  -e AWS_ACCESS_KEY_ID -e AWS_DEFAULT_REGION -e AWS_SECRET_ACCESS_KEY \
#  -e REDIS_URL=redis://dallinger_redis:6379 \
#  -e DATABASE_URL=postgresql://dallinger:dallinger@dallinger_postgres/dallinger \
#  --network dallinger \
#  --rm -it \
#  psynet-ci-local bash
