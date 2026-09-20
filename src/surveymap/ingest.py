from __future__ import annotations

from pathlib import Path

from surveymap.detect import EmptySurveyError, UnsupportedSurveyError, sniff_format
from surveymap.graph import GraphBuilder
from surveymap.models import SurveyGraph
from surveymap.parsers import parse_into

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def ingest_bytes(data: bytes, filename: str, builder: GraphBuilder | None = None) -> GraphBuilder:
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsupportedSurveyError("File is larger than the 50 MB preview limit.")
    kind = sniff_format(data, filename)
    builder = builder or GraphBuilder()
    parse_into(builder, data, filename, kind)
    return builder


def ingest_files(files: list[tuple[str, bytes]]) -> SurveyGraph:
    builder = GraphBuilder()
    for filename, data in files:
        ingest_bytes(data, filename, builder)
    graph = builder.finalize()
    if not graph.nodes:
        raise EmptySurveyError("No hosts, access points, or links were found in this survey.")
    return graph


def ingest_paths(paths: list[Path]) -> SurveyGraph:
    files = [(path.name, path.read_bytes()) for path in paths]
    return ingest_files(files)
