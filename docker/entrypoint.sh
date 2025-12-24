#!/bin/bash
set -e

# Check if GPU-dependent packages need to be installed
GPU_SETUP_FLAG="/workspace/.gpu_setup_complete"

if [ ! -f "$GPU_SETUP_FLAG" ]; then
    echo "==================================="
    echo "First run detected - setting up GPU-dependent packages..."
    echo "==================================="
    
    cd /workspace/libs/trellis2
    
    # Run setup with GPU-dependent packages
    if bash setup.sh --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --flexgemm --o-voxel; then
        echo "==================================="
        echo "GPU setup completed successfully"
        echo "==================================="
        touch "$GPU_SETUP_FLAG"
    else
        echo "==================================="
        echo "Warning: GPU setup failed, but continuing..."
        echo "==================================="
    fi
    
    cd /workspace
fi

# Start the application
exec python serve.py
