#!/bin/bash

# Quick rebuild script - Simple wrapper for rebuild-services.sh
# This provides the simplest possible interface

cd "$(dirname "$0")/.."

# Just rebuild frontend and backend
./scripts/rebuild-services.sh --frontend --backend
