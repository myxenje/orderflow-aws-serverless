#!/bin/sh
set -e

exec /lambda-entrypoint.sh "$LAMBDA_HANDLER"