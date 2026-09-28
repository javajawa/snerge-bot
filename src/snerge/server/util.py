# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import dataclasses
import json
import logging

import prosegen.prosegen


class SetEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, set):
            return list(o)
        if isinstance(o, prosegen.prosegen.Fact):
            return {"id": o.source, "text": o.original}
        if isinstance(o, logging.LogRecord):
            return {"time": o.created, "level": o.levelname, "message": o.getMessage()}
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return json.JSONEncoder.default(self, o)
