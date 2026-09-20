from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from surveymap.detect import EmptySurveyError, UnsupportedSurveyError
from surveymap.exporters import export_drawio, export_vdx, export_vsdx
from surveymap.ingest import ingest_files
from surveymap.samples import SAMPLES, files_for_sample
from surveymap.serialize import graph_from_dict

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="SurveyMap", version="0.1.0")


def _http_error(exc: Exception, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "name": "SurveyMap"}


@app.get("/api/samples")
def list_samples() -> list[dict]:
    return SAMPLES


@app.get("/api/samples/{sample_id}/graph")
def sample_graph(sample_id: str):
    try:
        files = files_for_sample(sample_id)
        graph = ingest_files(files)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown sample '{sample_id}'.") from None
    except EmptySurveyError as exc:
        raise _http_error(exc, 422) from exc
    except (UnsupportedSurveyError, ValueError, OSError) as exc:
        raise _http_error(exc) from exc
    return graph.to_dict()


@app.post("/api/parse")
async def parse_upload(file: UploadFile = File(...)):
    data = await file.read()
    name = file.filename or "upload"
    try:
        graph = ingest_files([(name, data)])
    except EmptySurveyError as exc:
        raise _http_error(exc, 422) from exc
    except (UnsupportedSurveyError, ValueError, OSError) as exc:
        raise _http_error(exc) from exc
    return graph.to_dict()


def _graph_from_body(body: dict):
    if "nodes" not in body:
        raise HTTPException(status_code=400, detail="Export body must include a graph with nodes and links.")
    return graph_from_dict(body), body.get("title") or "Survey map"


@app.post("/api/export/drawio")
def export_drawio_api(body: dict):
    graph, title = _graph_from_body(body)
    xml = export_drawio(graph, title=title)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="survey-map.drawio"'},
    )


@app.post("/api/export/vdx")
def export_vdx_api(body: dict):
    graph, title = _graph_from_body(body)
    xml = export_vdx(graph, title=title)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="survey-map.vdx"'},
    )


@app.post("/api/export/vsdx")
def export_vsdx_api(body: dict):
    graph, title = _graph_from_body(body)
    blob = export_vsdx(graph, title=title)
    return Response(
        content=blob,
        media_type="application/vnd.visio",
        headers={"Content-Disposition": 'attachment; filename="survey-map.vsdx"'},
    )


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"error": "Web UI missing"}, status_code=500)
    return FileResponse(index_path)


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
