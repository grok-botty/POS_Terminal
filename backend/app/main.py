import sys
import os
from pathlib import Path
from django.http import FileResponse, Http404
from django.views.decorators.http import require_http_methods


def get_dist_dir() -> Path:
    # В PyInstaller onefile файлы оказываются в sys._MEIPASS
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "app" / "dist"
    # В обычном запуске
    return Path(__file__).resolve().parent / "dist"


DIST_DIR = get_dist_dir()


@require_http_methods(["GET"])
def serve_frontend(request, path=""):
    # Если путь начинается с api/, возвращаем 404
    if path.startswith("api/"):
        raise Http404("API endpoint not found")

    # Если запрашивается конкретный файл (с расширением), пытаемся его отдать
    if "." in path.split("/")[-1]:
        file_path = DIST_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(open(file_path, "rb"))
        raise Http404("File not found")

    # Для всех остальных путей (SPA роутинг) отдаём index.html
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(open(index_path, "rb"))

    raise Http404("Frontend not built. Run: cd frontend && npm run build")
