#!/usr/bin/env bash
cd lambdas/forex-trader-v1
cp ../unzip_requirements.py .
npm i
./node_modules/serverless/bin/serverless.js deploy