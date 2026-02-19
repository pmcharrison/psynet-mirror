# Implementation Plan: Custom Docker Build Support in CI

## Overview

Implement marker-based CI testing for experiments requiring custom Docker builds (system dependencies or idiosyncratic Python packages).

## Files to Modify

### 1. Add marker files (2 files)

**File**: `demos/experiments/adaptive_test_catr/.requires-docker-build`
```
This experiment requires a custom Docker build because:
- System dependency: R (r-base, r-base-dev)
- R package: catR
- Python package: rpy2 (requires R to be installed)
```

**File**: `demos/experiments/gibbs_video/.requires-docker-build`
```
This experiment requires a custom Docker build because:
- System dependency: ffmpeg
```

### 2. Update `psynet/utils.py`

**Function**: `list_experiment_dirs()`

**Current code** (lines ~1189-1191):
```python
# Skip the gibbs_video demo because it relies on ffmpeg which is not installed
# in the CI environment
or dir_.endswith("/gibbs_video")
```

**New code**:
```python
# Skip experiments requiring custom Docker builds
# (system dependencies via prepare_docker_image.sh or idiosyncratic Python packages)
or os.path.exists(os.path.join(dir_, ".requires-docker-build"))
or os.path.exists(os.path.join(dir_, "prepare_docker_image.sh"))
```

**Rationale**: 
- Removes hardcoded `gibbs_video` check
- Uses hybrid detection (explicit marker OR prepare_docker_image.sh)
- Covers both system dependencies and special Python packages

### 3. Add new function to `psynet/utils.py`

**New function**:
```python
def list_docker_build_experiments(ci_node_total=None, ci_node_index=None):
    """
    List experiments that require custom Docker builds.
    
    This includes experiments with:
    - .requires-docker-build marker file
    - prepare_docker_image.sh script
    
    These experiments need their own Dockerfile-based CI testing.
    """
    demo_root = get_psynet_root() / "demos"
    test_experiments_root = get_psynet_root() / "tests/experiments"
    
    dirs = sorted([
        dir_
        for root in [demo_root, test_experiments_root]
        for dir_, sub_dirs, files in os.walk(root)
        if (
            "experiment.py" in files
            and not dir_.endswith("/develop")
            and (
                os.path.exists(os.path.join(dir_, ".requires-docker-build"))
                or os.path.exists(os.path.join(dir_, "prepare_docker_image.sh"))
            )
            # Still skip recruiter tests - they're not meaningful in CI
            and "recruiters" not in dir_
            and "manual_recruiter_testing" not in dir_
        )
    ])
    
    if ci_node_total is not None and ci_node_index is not None:
        dirs = with_parallel_ci(dirs, ci_node_total, ci_node_index)
    
    return dirs
```

### 4. Add CLI command to `psynet/command_line.py`

**New command**:
```python
@main.command()
@click.option("--ci-node-total", type=int, default=None)
@click.option("--ci-node-index", type=int, default=None)
def list_docker_experiments(ci_node_total, ci_node_index):
    """
    List experiments requiring custom Docker builds.
    
    These experiments have either:
    - .requires-docker-build marker file
    - prepare_docker_image.sh script
    """
    from psynet.utils import list_docker_build_experiments
    
    dirs = list_docker_build_experiments(ci_node_total, ci_node_index)
    for dir_ in dirs:
        print(dir_)
```

### 5. Update `.gitlab-ci.yml`

**Add new job after `tests:` job**:
```yaml
test_docker_experiments:
  parallel:
    matrix:
      - EXPERIMENT_PATH: 
          - "demos/experiments/adaptive_test_catr"
          - "demos/experiments/gibbs_video"
  stage: test
  <<: *default_rules
  script:
    - cd $EXPERIMENT_PATH
    - echo "Building custom Docker image for $EXPERIMENT_PATH"
    - docker build -t test-experiment-$(basename $EXPERIMENT_PATH) .
    - |
      echo "Running tests in custom Docker image"
      docker run \
        --add-host=postgres:$POSTGRES_IP \
        --add-host=redis:$REDIS_IP \
        -e HEADLESS=TRUE \
        -e REDIS_URL=$REDIS_URL \
        -e DATABASE_URL=$DATABASE_URL \
        -e POSTGRES_DB=$POSTGRES_DB \
        -e POSTGRES_USER=$POSTGRES_USER \
        -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
        -e CI=$CI \
        -v "$PWD:/experiment" \
        -w /experiment \
        test-experiment-$(basename $EXPERIMENT_PATH) \
        bash -c "pytest test.py --chrome --timeout=300 -q"
```

**Alternative (dynamic discovery)**:
```yaml
test_docker_experiments:
  stage: test
  <<: *default_rules
  script:
    - export PSYNET_WORKSPACE=/root/workspaces/PsyNet
    - |
      # Get list of experiments needing Docker builds
      EXPERIMENTS=$(docker run \
        -v "$PWD:$PSYNET_WORKSPACE" \
        -w $PSYNET_WORKSPACE \
        $DOCKER_LOCAL_TAG \
        psynet list-docker-experiments)
      
      # Build and test each one
      for experiment in $EXPERIMENTS; do
        echo "Building and testing $experiment"
        cd $experiment
        
        docker build -t test-$(basename $experiment) .
        
        docker run \
          --add-host=postgres:$POSTGRES_IP \
          --add-host=redis:$REDIS_IP \
          -e HEADLESS=TRUE -e REDIS_URL -e DATABASE_URL \
          -e POSTGRES_DB -e POSTGRES_USER -e POSTGRES_PASSWORD -e CI \
          -v "$PWD:/experiment" \
          -w /experiment \
          test-$(basename $experiment) \
          pytest test.py --chrome --timeout=300 -q
        
        cd -
      done
```

### 6. Update documentation

**File**: `docs/experiment_development/dependencies.rst`

**Add section after "Using R packages with rpy2"**:

```rst
CI Testing with Custom Dependencies
""""""""""""""""""""""""""""""""""""

If your experiment requires system dependencies (via ``prepare_docker_image.sh``) or idiosyncratic
Python packages, it needs special handling in continuous integration (CI).

To mark your experiment for custom Docker CI testing, create an empty file named
``.requires-docker-build`` in your experiment directory:

.. code-block:: bash

    touch .requires-docker-build

When should you use this marker?

1. **System dependencies**: Your experiment uses ``prepare_docker_image.sh`` to install
   system packages like R, ffmpeg, sox, etc.

2. **Idiosyncratic Python packages**: Your experiment requires Python packages with complex
   build requirements that aren't in the base CI image (e.g., ``rpy2``, ``opencv-python``,
   packages requiring compilation).

3. **Complex build requirements**: Your experiment needs specific library versions or
   custom build configurations.

When this marker is present, CI will:

- Skip your experiment in the standard CI test suite (which uses a shared base image)
- Build your experiment's Dockerfile separately
- Run tests in your custom Docker image

This ensures your experiment is tested with its actual dependencies while keeping the
base CI image lean and fast.

.. note::

    Experiments with ``prepare_docker_image.sh`` are automatically detected and don't
    strictly need the marker, but adding it makes the requirement explicit.
```

## Testing Plan

1. **Local verification**:
   ```bash
   # Verify list commands work
   psynet list-experiment-dirs --for-ci-tests
   psynet list-docker-experiments
   
   # Verify adaptive_test_catr and gibbs_video are excluded from first, included in second
   ```

2. **CI verification**:
   - Push to branch
   - Check GitLab CI runs both `tests` and `test_docker_experiments` jobs
   - Verify `adaptive_test_catr` and `gibbs_video` tests pass in custom images

## Rollout Strategy

1. Implement marker files and `list_docker_build_experiments()` function
2. Update `list_experiment_dirs()` to use hybrid detection
3. Add CLI command
4. Test locally
5. Add GitLab CI job (initially with explicit matrix)
6. Update documentation
7. Monitor CI runs
8. Optionally switch to dynamic discovery later

## Future Considerations

- **Auto-generate matrix**: Could dynamically populate the matrix from `list-docker-experiments`
- **Caching**: Docker layer caching could speed up custom builds
- **Shared layers**: Common dependencies (R) could use a base image to avoid rebuilding
- **Local testing**: Update `docker/run` scripts to work consistently with CI approach
