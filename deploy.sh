#!/bin/bash

docker build -t test-acutracer . && docker run -v ~/.metagpt/config2.yaml:/root/.metagpt/config2.yaml -p 7860:7860 test-acutracer
