# Response to Tim Schäfer's Question about Using R/catR in PsyNet

Hi Tim! Great question about integrating the catR R package for adaptive testing in PsyNet. The answer is **yes, this is absolutely possible** using PsyNet's `prepare_docker_image.sh` mechanism. Here's how:

## Quick Answer

You can use R packages like catR in PsyNet experiments by:

1. **Adding `rpy2` to your `requirements.txt`** - This Python package provides the Python-R interface
2. **Creating a `prepare_docker_image.sh` script** - This installs R and R packages into your Docker image
3. **Using rpy2 in your experiment code** - Call R functions directly from Python

When you deploy with Docker (the default for `psynet deploy` to custom servers), everything is handled automatically!

## Step-by-Step

### 1. Add rpy2 to requirements.txt

```text
psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet
rpy2
```

### 2. Create prepare_docker_image.sh in your experiment directory

```bash
#!/bin/sh
apt-get update
apt-get install -y r-base r-base-dev
R -e "install.packages('catR', repos='https://cloud.r-project.org/')"
```

### 3. Use catR in your experiment.py

```python
from rpy2.robjects.packages import importr
import rpy2.robjects as robjects

catr = importr('catR')

# Use catR functions for adaptive testing
def estimate_ability(responses, item_params):
    r_responses = robjects.IntVector(responses)
    r_item_bank = robjects.r.matrix(...)
    result = catr.thetaEst(r_item_bank, r_responses, method="ML")
    return float(result[0][0])
```

## How It Works

- **With Docker deployment** (default): The `prepare_docker_image.sh` script runs during Docker image build, installing R and catR. Your experiment then has full access to these packages.

- **Without Docker**: You'd need to manually install R and catR on the server before deploying.

- **For local testing** (`psynet debug local`): Install R and catR on your development machine first.

## Complete Working Example

I've created a full demo experiment showing this in action:

📁 `demos/experiments/adaptive_test_catr/`

This includes:
- Complete `prepare_docker_image.sh` script
- Working example using catR for adaptive item selection and ability estimation
- Documentation and README

## Documentation

I've also updated the PsyNet documentation with a section on using R packages via rpy2:

📖 `docs/experiment_development/dependencies.rst` (new "Using R packages with rpy2" section)

## Summary

✅ **Yes, you can use catR with PsyNet via rpy2**  
✅ **Docker deployment handles R installation automatically via `prepare_docker_image.sh`**  
✅ **Full access to catR's adaptive testing algorithms from Python**  
✅ **Working demo available in the repository**

The `prepare_docker_image.sh` mechanism is designed exactly for this use case - installing system dependencies like R that aren't Python packages. It's a clean, straightforward solution that works seamlessly with PsyNet's deployment workflow.

Let me know if you have any questions about implementing this in your experiment!
