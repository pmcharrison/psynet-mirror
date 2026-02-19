# CI Implementation Summary: Custom Docker Builds

## What Was Implemented

A centralized configuration system for CI testing of experiments requiring custom Docker builds (system dependencies or idiosyncratic Python packages).

## Key Design Decision

**Centralized list file** instead of marker files in demo directories:
- ✅ Demos remain clean (users won't copy irrelevant files)
- ✅ Explicit configuration in one place
- ✅ Easy to review what's special
- ✅ Validated on each CI run

## Files Created/Modified

### New Files

1. **`ci/docker-build-experiments.txt`** - The configuration file
   ```
   # Comments explain requirements
   demos/experiments/adaptive_test_catr  # R + catR + rpy2
   demos/experiments/gibbs_video         # ffmpeg
   ```

2. **`CI_STRATEGY_V2.md`** - Design documentation

### Modified Files

1. **`psynet/utils.py`**
   - Added `validate_docker_build_experiments_list()` - catches typos
   - Added `list_docker_build_experiments()` - reads and validates list
   - Modified `list_experiment_dirs()` - excludes listed experiments from base CI
   - Removed hardcoded `gibbs_video` exclusion

2. **`psynet/command_line.py`**
   - Added `psynet list-docker-experiments` command

3. **`.gitlab-ci.yml`**
   - Added `test_docker_experiments` job that:
     - Validates the list file
     - Builds each experiment's Dockerfile
     - Runs tests in custom images

4. **`docs/experiment_development/dependencies.rst`**
   - Added "CI Testing with Custom Dependencies" section

5. **`CHANGELOG.md`**
   - Documented new feature

## How It Works

### For Standard Experiments
```
CI runs → Base Docker image → Tests most experiments ✓
```

### For Special Experiments
```
CI runs → test_docker_experiments job:
  ├─ Validates ci/docker-build-experiments.txt
  ├─ Builds demos/experiments/adaptive_test_catr Dockerfile
  ├─ Tests adaptive_test_catr in its image ✓
  ├─ Builds demos/experiments/gibbs_video Dockerfile
  └─ Tests gibbs_video in its image ✓
```

## Adding a New Custom-Build Experiment

1. Create experiment with `prepare_docker_image.sh` and/or special requirements
2. Add one line to `ci/docker-build-experiments.txt`:
   ```
   demos/experiments/your_experiment  # Brief reason
   ```
3. CI automatically picks it up and tests it properly

## Validation

The list is validated on every CI run:

```python
# Catches typos
demos/experiments/typo_demo  # ERROR: Path does not exist

# Catches non-experiments
demos/features/video  # ERROR: Not an experiment (no experiment.py)
```

## Use Cases Covered

✅ **System dependencies** (R, ffmpeg, sox)  
✅ **Idiosyncratic Python packages** (rpy2, opencv, tensorflow)  
✅ **Complex build requirements**  
✅ **No demo pollution** (centralized config)  
✅ **Explicit over implicit** (no auto-detection magic)  

## Benefits for Tim's Use Case

The `adaptive_test_catr` demo:
- ✅ Listed in `ci/docker-build-experiments.txt`
- ✅ Tested in CI with R and catR installed
- ✅ Demo directory stays clean for users to copy
- ✅ Clear documentation of special requirements

## Testing

The implementation can be verified by:

```bash
# List experiments requiring custom builds
psynet list-docker-experiments

# List standard experiments (should exclude custom ones)
psynet list-experiment-dirs --for-ci-tests
```

## Next Steps

The CI will now:
1. Run standard tests (excluding adaptive_test_catr and gibbs_video)
2. Run custom Docker build tests (for adaptive_test_catr and gibbs_video)
3. Validate the list file on each run

If CI fails, it will show clear error messages about which validation failed.
