from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from surveymap.detect import EmptySurveyError, UnsupportedSurveyError
from surveymap.exporters import (
    device_csv,
    device_pdf,
    device_plain_text,
    device_xml,
    export_drawio,
    export_vdx,
    export_vsdx,
    map_report_pdf,
    safe_filename,
)
from surveymap.exporters.reports import device_properties
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


def _node_from_body(body: dict):
    graph, title = _graph_from_body(body)
    node_id = body.get("node_id")
    node = next((n for n in graph.nodes if n.id == node_id), None)
    if node is None:
        raise HTTPException(status_code=404, detail="Unknown device on this map.")
    return graph, node, title


@app.post("/api/device/properties")
def device_properties_api(body: dict):
    graph, node, _title = _node_from_body(body)
    return {
        "id": node.id,
        "label": node.label,
        "kind": node.kind,
        "properties": device_properties(graph, node),
    }


@app.post("/api/export/device/{fmt}")
def export_device_api(fmt: str, body: dict):
    graph, node, title = _node_from_body(body)
    stem = safe_filename(node.label or node.id, "")
    if fmt == "txt":
        return Response(
            content=device_plain_text(graph, node),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{stem}-device.txt"'},
        )
    if fmt == "csv":
        return Response(
            content=device_csv(graph, node),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{stem}-device.csv"'},
        )
    if fmt == "xml":
        return Response(
            content=device_xml(graph, node),
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{stem}-device.xml"'},
        )
    if fmt == "pdf":
        return Response(
            content=device_pdf(graph, node, title=f"{title} — {node.label}"),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stem}-device.pdf"'},
        )
    raise HTTPException(status_code=404, detail="Use txt, csv, xml, or pdf.")


@app.post("/api/export/report.pdf")
def export_report_pdf(body: dict):
    graph, title = _graph_from_body(body)
    blob = map_report_pdf(graph, title=f"{title} report")
    name = safe_filename(title, "-report.pdf")
    return Response(
        content=blob,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"error": "Web UI missing"}, status_code=500)
    return FileResponse(index_path)


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
