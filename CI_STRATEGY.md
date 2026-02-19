# CI Strategy for Testing Experiments with Custom Docker Images

## Problem

Some experiments require dependencies not present in the base CI Docker image:
- **System dependencies**: `adaptive_test_catr` needs R and catR; `gibbs_video` needs ffmpeg
- **Idiosyncratic Python packages**: Some experiments may need specialized packages with complex build requirements (e.g., rpy2, opencv-python, tensorflow)

Currently, these experiments are skipped in CI tests because they would fail due to missing dependencies.

## Current Architecture

1. **GitLab CI** builds one base Docker image for all tests (`.gitlab-ci.yml` line 36)
2. Tests run inside this single image via `run-ci-tests.sh`
3. Experiments with special dependencies are manually excluded in `psynet/utils.py::list_experiment_dirs()`

## Proposed Strategy

### Option A: Marker-Based Approach (Recommended)

**Concept**: Add a marker file to experiments that need their own Docker build (either for system dependencies or idiosyncratic Python packages), then handle them separately in CI.

**Implementation**:

1. **Marker file**: Add `.requires-docker-build` file to experiments needing their own Docker image
   ```bash
   # In experiment directory
   # Use this for experiments with:
   # - prepare_docker_image.sh (system dependencies like R, ffmpeg)
   # - Specialized Python packages not in base image (rpy2, opencv, etc.)
   # - Complex build requirements
   touch .requires-docker-build
   ```

2. **Modify `list_experiment_dirs()`**:
   ```python
   def list_experiment_dirs(for_ci_tests=False, ci_node_total=None, ci_node_index=None):
       # ... existing code ...
       dirs = sorted([
           dir_ for root in [demo_root, test_experiments_root]
           for dir_, sub_dirs, files in os.walk(root)
           if (
               "experiment.py" in files
               and not dir_.endswith("/develop")
               and (
                   not for_ci_tests
                   or not (
                       # Skip experiments requiring custom Docker builds
                       # (either system dependencies or idiosyncratic Python packages)
                       os.path.exists(os.path.join(dir_, ".requires-docker-build"))
                       or "recruiters" in dir_
                       or "manual_recruiter_testing" in dir_
                   )
               )
           )
       ])
   ```

3. **Add separate CI job** for Docker-build experiments:
   ```yaml
   test_docker_experiments:
     parallel:
       matrix:
         - EXPERIMENT: ["adaptive_test_catr", "gibbs_video"]
     stage: test
     script:
       - cd demos/experiments/$EXPERIMENT
       - docker build -t test-$EXPERIMENT .
       - docker run
           --add-host=postgres:$POSTGRES_IP
           --add-host=redis:$REDIS_IP
           -e HEADLESS=TRUE -e REDIS_URL -e DATABASE_URL
           -v "$PWD:/experiment"
           -w /experiment
           test-$EXPERIMENT
           pytest test.py --chrome --timeout=300
   ```

**Pros**:
- ✅ Simple, explicit marker
- ✅ Minimal code changes
- ✅ Easy to add new experiments
- ✅ Each experiment uses its own Dockerfile

**Cons**:
- ⚠️ Separate CI job (more CI time)
- ⚠️ Need to maintain matrix list

---

### Option B: Auto-Detection Approach

**Concept**: Automatically detect experiments with `prepare_docker_image.sh` and test them differently.

**Implementation**:

1. **Add helper function**:
   ```python
   def list_docker_build_experiments():
       """List experiments that have prepare_docker_image.sh"""
       dirs = list_experiment_dirs(for_ci_tests=False)
       return [d for d in dirs if os.path.exists(os.path.join(d, "prepare_docker_image.sh"))]
   ```

2. **Modify `list_experiment_dirs()`**:
   ```python
   # Skip experiments with prepare_docker_image.sh when for_ci_tests=True
   or (for_ci_tests and os.path.exists(os.path.join(dir_, "prepare_docker_image.sh")))
   ```

3. **Add dynamic CI job**:
   ```yaml
   test_docker_experiments:
     stage: test
     script:
       - |
         for experiment in $(psynet list-docker-experiments --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
           echo "Building and testing $experiment"
           cd $experiment
           docker build -t test-$(basename $experiment) .
           docker run ... test-$(basename $experiment) pytest test.py
           cd -
         done
   ```

**Pros**:
- ✅ Fully automatic - no manual list maintenance
- ✅ Any experiment with `prepare_docker_image.sh` gets tested

**Cons**:
- ⚠️ Less explicit (magic behavior)
- ⚠️ Harder to opt-out if needed

---

### Option C: Extended Base Image Approach

**Concept**: Add R and other common dependencies to the base CI image.

**Implementation**:

1. **Modify root `Dockerfile`**:
   ```dockerfile
   # Install common optional dependencies
   RUN apt-get update && apt-get install -y \
       ffmpeg \
       r-base \
       r-base-dev \
       && rm -rf /var/lib/apt/lists/*
   ```

2. **Install common R packages**:
   ```dockerfile
   RUN R -e "install.packages('catR', repos='https://cloud.r-project.org/')"
   ```

**Pros**:
- ✅ No CI changes needed
- ✅ Fastest test execution
- ✅ Works for all experiments

**Cons**:
- ❌ Bloated base image (~200MB+ for R)
- ❌ Longer image build times for ALL jobs
- ❌ Not scalable (can't include every possible dependency)
- ❌ Defeats the purpose of `prepare_docker_image.sh`

---

## Recommendation

**Use Option A (Marker-Based Approach)** because:

1. **Explicit and clear**: Developers know which experiments need special handling
2. **Scalable**: Easy to add experiments with any system dependency
3. **Clean separation**: Base image stays lean, custom images stay custom
4. **Low maintenance**: Just add experiment names to matrix

## Implementation Steps

1. **Add `.requires-docker-build` marker** to experiments:
   - `demos/experiments/adaptive_test_catr/.requires-docker-build` (needs R + rpy2)
   - `demos/experiments/gibbs_video/.requires-docker-build` (needs ffmpeg)

2. **Update `psynet/utils.py::list_experiment_dirs()`** to skip marked experiments in base CI
   - Replace hardcoded `gibbs_video` check with marker detection
   - Use hybrid approach: check both marker file and `prepare_docker_image.sh`

3. **Add `test_docker_experiments` job** to `.gitlab-ci.yml`
   - Builds each experiment's Dockerfile
   - Runs tests in the custom image
   - Parallel matrix for efficiency

4. **Document in experiment development docs**:
   - When to use `.requires-docker-build`
   - How it works (skips base CI, uses custom Docker job)
   - Examples of both system dependencies and idiosyncratic packages

5. **Optional: Add command** `psynet list-docker-experiments`
   - Lists experiments requiring custom Docker builds
   - Useful for debugging and CI

## Alternative: Option A-Plus (Hybrid)

Combine Option A with auto-detection for better UX:

```python
def requires_custom_docker_build(dir_):
    """
    Check if experiment requires custom Docker build.
    
    This includes experiments that need:
    - System dependencies (via prepare_docker_image.sh)
    - Idiosyncratic Python packages with complex builds
    """
    return (
        os.path.exists(os.path.join(dir_, ".requires-docker-build"))
        or os.path.exists(os.path.join(dir_, "prepare_docker_image.sh"))
    )
```

This way:
- Experiments with `.requires-docker-build` are explicitly marked (useful for idiosyncratic Python packages)
- Experiments with `prepare_docker_image.sh` are auto-detected (system dependencies)
- Best of both worlds!

## When to Use `.requires-docker-build`

Use this marker for experiments that need:

1. **System dependencies** (via `prepare_docker_image.sh`):
   - R packages (rpy2 + R + catR)
   - ffmpeg, sox, or other media tools
   - System libraries (libsndfile, imagemagick, etc.)

2. **Idiosyncratic Python packages**:
   - Packages requiring compilation (rpy2, opencv-python)
   - Packages with complex C/C++ dependencies
   - Packages not in the base image that would slow down all CI jobs if added

3. **Complex build requirements**:
   - Experiments needing specific library versions
   - Custom build flags or environment variables
