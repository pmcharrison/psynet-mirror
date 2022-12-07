# The purpose of this code is to come as close as possible to running the CI tests
# as they would be run on the CI server. This workflow shares the disadvantage
# of the CI tests in that they have to pull the Docker images each time,
# which is slow. In fact, because the data transfer now happens over the internet,
# it seems to take even longer than the CI hosted version.
#
# Note -- this script is still incomplete -- AWS credentials are not passed, and CI test node is not passed either.
#
# Note -- maybe a better approach for debugging would be to remove one layer of wrapping and not use Docker-in-Docker,
# but instead just use one layer of Docker?
#
# You need to install the following first:
# - docker - https://docs.docker.com/install/
# - gitlab-runner - https://docs.gitlab.com/runner/install/

CI_REGISTRY="registry.gitlab.com/computational-audition-lab/psynet"
BRANCH_NAME="$(git rev-parse --abbrev-ref HEAD)"

printf "\n"
echo "Please enter your GitLab username:"
read -r CI_REGISTRY_USER

printf "\n"
echo "Please enter your GitLab password:"
read -r CI_REGISTRY_PASSWORD

# This approach would wrap the whole process in Docker and mean that you wouldn't have to install gitlab-runner
# docker run --entrypoint bash --rm -w $PWD -v $PWD:$PWD -v /var/run/docker.sock:/var/run/docker.sock \
#   gitlab/gitlab-runner:latest -c \
#   'git config --global --add safe.directory "*";gitlab-runner exec docker tests --env DOCKER_TAG="$BRANCH_NAME" --env CI_REGISTRY="$CI_REGISTRY" --env CI_REGISTRY_USER="$CI_REGISTRY_USER" --env CI_REGISTRY_PASSWORD="$CI_REGISTRY_PASSWORD"'

gitlab-runner exec docker tests \
  --docker-privileged \
  --env CI_REGISTRY="$CI_REGISTRY" \
  --env DOCKER_TAG="$BRANCH_NAME" \
  --env CI_REGISTRY_USER="$CI_REGISTRY_USER" \
  --env CI_REGISTRY_PASSWORD="$CI_REGISTRY_PASSWORD" \
  --env CI_REGISTRY_IMAGE="$CI_REGISTRY"
