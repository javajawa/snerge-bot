#!/usr/bin/env python3
# vim: fileencoding=utf-8 expandtab ts=4 nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Create GitHub annotations from pylint output"""

from __future__ import annotations

from typing import List

import sys


def main() -> None:
    """Create GitHub annotations from pylint output"""

    gh_annotations: List[str] = []

    for line in sys.stdin.readlines():
        print(line, end="")

        if ":" not in line:
            continue

        try:
            file, line_no, col, error = line.strip().split(":", 3)
            gh_annotations.append(f"::error file={file},line={line_no},col={col}::{error}")
        except ValueError:
            pass

    for annotation in gh_annotations:
        print(annotation)

    sys.exit(len(gh_annotations) > 0)


if __name__ == "__main__":
    main()
