#!/bin/sh

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

PATHS="src"

reuse lint
black $PATHS
python -m flake8 $PATHS
python -m mypy --strict $PATHS
python -m pylint $PATHS
