# CI Strategy V2: Centralized List for Custom Docker Builds

## Problem

Some experiments require dependencies not present in the base CI Docker image:
- **System dependencies**: `adaptive_test_catr` needs R and catR; `gibbs_video` needs ffmpeg
- **Idiosyncratic Python packages**: Some experiments may need specialized packages (e.g., rpy2, opencv-python)

## Rejected Approaches

1. **Marker files** (`.requires-docker-build`): Users will copy demos and forget to remove markers
2. **Auto-detection** (`prepare_docker_image.sh`): Too implicit, harder to control
3. **Hardcoded in Python**: Current approach, but scattered and hard to maintain

## Proposed Solution: Centralized List File

Create a configuration file that explicitly lists experiments requiring custom Docker builds.

### File Location

**Option A**: `ci/docker-build-experiments.txt` (preferred)
- Clear it's CI configuration
- Won't be copied when users create experiments

**Option B**: `.gitlab/docker-build-experiments.txt`
- Next to GitLab CI config
- GitLab-specific location

### File Format

Simple, line-based format with comments:

```txt
# Experiments requiring custom Docker builds
# Format: one path per line, relative to repository root
# Lines starting with # are comments

# System dependencies via prepare_docker_image.sh
demos/experiments/adaptive_test_catr  # Requires: R, catR, rpy2
demos/experiments/gibbs_video         # Requires: ffmpeg

# Add more experiments here as needed
# tests/experiments/opencv_demo       # Example: opencv-python
```

### Validation

The list should be validated to catch typos:

```python
def validate_docker_build_experiments_list(list_file):
    """
    Validate that all experiments in the list actually exist.
    Raises an error if any path doesn't exist or lacks experiment.py.
    """
    root = get_psynet_root()
    
    with open(list_file) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Remove inline comments
            path = line.split('#')[0].strip()
            
            # Validate path exists
            full_path = root / path
            if not full_path.exists():
                raise ValueError(
                    f"Error in {list_file} line {line_num}: "
                    f"Path does not exist: {path}"
                )
            
            # Validate it's an experiment
            if not (full_path / "experiment.py").exists():
                raise ValueError(
                    f"Error in {list_file} line {line_num}: "
                    f"Path is not an experiment (no experiment.py): {path}"
                )
    
    return True
```

### Integration

**In `psynet/utils.py`**:

```python
def list_docker_build_experiments(ci_node_total=None, ci_node_index=None):
    """
    List experiments requiring custom Docker builds.
    
    Reads from ci/docker-build-experiments.txt
    """
    root = get_psynet_root()
    list_file = root / "ci" / "docker-build-experiments.txt"
    
    if not list_file.exists():
        # No custom builds configured
        return []
    
    # Validate list
    validate_docker_build_experiments_list(list_file)
    
    # Parse experiments
    experiments = []
    with open(list_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                path = line.split('#')[0].strip()
                experiments.append(str(root / path))
    
    experiments = sorted(experiments)
    
    # Apply CI parallelization
    if ci_node_total is not None and ci_node_index is not None:
        experiments = with_parallel_ci(experiments, ci_node_total, ci_node_index)
    
    return experiments


def list_experiment_dirs(for_ci_tests=False, ci_node_total=None, ci_node_index=None):
    """Existing function, modified to exclude docker-build experiments"""
    demo_root = get_psynet_root() / "demos"
    test_experiments_root = get_psynet_root() / "tests/experiments"
    
    # Get list of experiments requiring custom Docker builds
    docker_build_experiments = set()
    if for_ci_tests:
        docker_build_experiments = set(list_docker_build_experiments())
    
    dirs = sorted([
        dir_
        for root in [demo_root, test_experiments_root]
        for dir_, sub_dirs, files in os.walk(root)
        if (
            "experiment.py" in files
            and not dir_.endswith("/develop")
            and (
                not for_ci_tests
                or not (
                    dir_ in docker_build_experiments
                    or "recruiters" in dir_
                    or "manual_recruiter_testing" in dir_
                )
            )
        )
    ])
    
    if ci_node_total is not None and ci_node_index is not None:
        dirs = with_parallel_ci(dirs, ci_node_total, ci_node_index)
    
    return dirs
```

**In `.gitlab-ci.yml`**:

```yaml
test_docker_experiments:
  stage: test
  <<: *default_rules
  script:
    - export PSYNET_WORKSPACE=/root/workspaces/PsyNet
    - |
      # Validate the docker-build experiments list
      docker run \
        -v "$PWD:$PSYNET_WORKSPACE" \
        -w $PSYNET_WORKSPACE \
        $DOCKER_LOCAL_TAG \
        python -c "from psynet.utils import validate_docker_build_experiments_list, get_psynet_root; \
                   validate_docker_build_experiments_list(get_psynet_root() / 'ci' / 'docker-build-experiments.txt')"
      
      # Get list of experiments
      EXPERIMENTS=$(docker run \
        -v "$PWD:$PSYNET_WORKSPACE" \
        -w $PSYNET_WORKSPACE \
        $DOCKER_LOCAL_TAG \
        psynet list-docker-experiments)
      
      if [ -z "$EXPERIMENTS" ]; then
        echo "No experiments require custom Docker builds"
        exit 0
      fi
      
      # Build and test each experiment
      for experiment in $EXPERIMENTS; do
        echo "========================================="
        echo "Building and testing: $experiment"
        echo "========================================="
        
        cd $PSYNET_WORKSPACE/$experiment
        
        # Build custom Docker image
        docker build -t test-$(basename $experiment) .
        
        # Run tests in custom image
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
          test-$(basename $experiment) \
          bash -c "pytest test.py --chrome --timeout=300 -q" || exit 1
      done
```

## Advantages

✅ **No demo pollution**: Users copying demos won't get irrelevant files  
✅ **Explicit and centralized**: One place to see all special-case experiments  
✅ **Validated**: Catches typos and missing experiments early  
✅ **Easy to maintain**: Add/remove experiments by editing one file  
✅ **Self-documenting**: Comments explain why each experiment is listed  
✅ **No magic**: Clear, explicit configuration  

## Implementation Steps

1. Create `ci/docker-build-experiments.txt` with initial experiments
2. Add `validate_docker_build_experiments_list()` to `psynet/utils.py`
3. Modify `list_docker_build_experiments()` to read from file
4. Update `list_experiment_dirs()` to exclude listed experiments
5. Add `psynet list-docker-experiments` CLI command
6. Update `.gitlab-ci.yml` with new `test_docker_experiments` job
7. Add validation as pre-check in CI job
8. Update documentation

## File Template

```txt
# CI: Experiments Requiring Custom Docker Builds
#
# This file lists experiments that need their own Docker image for CI testing.
# These experiments are excluded from the standard CI test suite and instead
# tested in a separate job that builds their individual Dockerfiles.
#
# Use this for experiments that require:
# - System dependencies (via prepare_docker_image.sh): R, ffmpeg, sox, etc.
# - Idiosyncratic Python packages: rpy2, opencv-python, tensorflow, etc.
# - Complex build requirements not in the base CI image
#
# Format:
# - One experiment path per line (relative to repository root)
# - Lines starting with # are comments
# - Inline comments (after #) are allowed and encouraged
#
# The list is validated on each CI run to catch typos.

demos/experiments/adaptive_test_catr  # R + catR package + rpy2
demos/experiments/gibbs_video         # ffmpeg for video processing
```

## Error Messages

Good error messages for validation failures:

```
Error in ci/docker-build-experiments.txt line 12: 
Path does not exist: demos/experiments/typo_demo
Did you mean: demos/experiments/adaptive_test_catr?

Error in ci/docker-build-experiments.txt line 15:
Path is not an experiment (no experiment.py): demos/features/video
```

## Documentation Update

Add to `docs/experiment_development/dependencies.rst`:

```rst
CI Testing with Custom Dependencies
""""""""""""""""""""""""""""""""""""

Most experiments are tested in CI using a shared base Docker image. However, if your
experiment requires system dependencies or idiosyncratic Python packages, it needs
to be tested using its own Dockerfile.

**For PsyNet contributors**: If you're adding a demo experiment that requires custom
dependencies, add it to ``ci/docker-build-experiments.txt`` in the repository root.

**For PsyNet users**: Your own experiments can use ``prepare_docker_image.sh`` freely.
The CI configuration only applies to experiments in the PsyNet repository itself.
```
