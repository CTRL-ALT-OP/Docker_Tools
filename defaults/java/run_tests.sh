#!/bin/sh

mvn \
    --batch-mode \
    --no-transfer-progress \
    --offline \
    compile test "${@}"