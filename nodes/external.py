# SPDX-License-Identifier: GPL-3.0-or-later
"""Character upload/download nodes and their browser transfer routes."""

import asyncio
import io
import re
import uuid
from pathlib import Path
from urllib.parse import quote

import folder_paths
from omnichar_sdk import Character, CharError, safe_output_name

from .common import CATEGORY, CHARACTER, CHARACTER_INPUT


def upload_root():
    return Path(folder_paths.get_input_directory()) / "omnichar_uploads"


def download_root():
    return Path(folder_paths.get_temp_directory()) / "omnichar_downloads"


def stored_path(root, token, filename):
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise CharError("Choose a character file to upload first.")
    if not filename or safe_output_name(filename, ".char") != filename:
        raise CharError("Invalid character filename.")
    root = root.resolve()
    path = (root / token / filename).resolve()
    if not path.is_relative_to(root):
        raise CharError("Invalid character location.")
    return path


class OmnicharLoadCharacterExternal:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "filename": ("STRING", {"default": "", "tooltip": "Use choose file to upload."}),
            "upload_id": ("STRING", {"default": "", "advanced": True}),
        }}

    RETURN_TYPES = (CHARACTER,)
    RETURN_NAMES = ("char",)
    FUNCTION = "load"
    CATEGORY = CATEGORY
    DESCRIPTION = "Choose a .char file on your computer and upload it through the browser."

    @classmethod
    def IS_CHANGED(cls, filename, upload_id):
        try:
            stat = stored_path(upload_root(), upload_id, filename).stat()
            return (stat.st_mtime_ns, stat.st_size)
        except (CharError, OSError, ValueError):
            return float("nan")

    @classmethod
    def VALIDATE_INPUTS(cls, filename, upload_id):
        try:
            cls().load(filename, upload_id)
        except (CharError, OSError, ValueError) as error:
            return str(error)
        return True

    def load(self, filename, upload_id):
        return (Character.open(stored_path(upload_root(), upload_id, filename)),)


class OmnicharSaveCharacterExternal:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "char": CHARACTER_INPUT,
            "filename": ("STRING", {"default": "model.char"}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename",)
    FUNCTION = "save"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True
    DESCRIPTION = "Run the workflow, then click download character to save the .char in your browser."

    @classmethod
    def IS_CHANGED(cls, char, filename):
        return float("nan")

    def save(self, char, filename):
        filename = safe_output_name(filename, ".char")
        token = uuid.uuid4().hex
        target = stored_path(download_root(), token, filename)
        data = char.to_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_bytes(data)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {
            "ui": {"omnichar_download": [{"id": token, "filename": filename}]},
            "result": (filename,),
        }


def register_routes(routes):
    from aiohttp import web

    @routes.get("/omnichar/preview/{token}/{filename}")
    async def preview(request):
        def render():
            from PIL import Image

            target = stored_path(upload_root(), request.match_info["token"], request.match_info["filename"])
            refs = Character.open(target).get_references()
            if not refs:
                raise CharError("This character has no reference images.")
            with refs[0].open() as image:
                image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()

        try:
            data = await asyncio.to_thread(render)
        except (CharError, OSError, ValueError) as error:
            raise web.HTTPNotFound(text=str(error)) from error
        return web.Response(body=data, content_type="image/png", headers={"Cache-Control": "no-store"})

    @routes.post("/omnichar/upload")
    async def upload(request):
        target = None
        completed = False
        try:
            reader = await request.multipart()
            field = await reader.next()
            if field is None or field.name != "file" or not field.filename:
                raise CharError("Choose a .char file to upload.")
            if not field.filename.lower().endswith(".char"):
                raise CharError("Choose a .char file.")
            filename = safe_output_name(field.filename, ".char")
            token = uuid.uuid4().hex
            target = stored_path(upload_root(), token, filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            # Stream large characters, including LoRAs, within ComfyUI's upload limit.
            with target.open("xb") as stream:
                while chunk := await field.read_chunk(size=1024 * 1024):
                    size += len(chunk)
                    if request.client_max_size and size > request.client_max_size:
                        raise web.HTTPRequestEntityTooLarge(
                            max_size=request.client_max_size, actual_size=size
                        )
                    stream.write(chunk)
            await asyncio.to_thread(Character.open, target)
            completed = True
            return web.json_response({"filename": filename, "upload_id": token})
        except (CharError, ValueError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except OSError:
            return web.json_response({"error": "Unable to store the uploaded character."}, status=500)
        finally:
            if target is not None and not completed:
                target.unlink(missing_ok=True)

    @routes.get("/omnichar/download/{token}/{filename}")
    async def download(request):
        try:
            filename = request.match_info["filename"]
            target = stored_path(download_root(), request.match_info["token"], filename)
            if not target.is_file():
                raise CharError("Download expired. Run the Save Character node again.")
        except (CharError, OSError, ValueError) as error:
            raise web.HTTPNotFound(text=str(error)) from error
        return web.FileResponse(target, headers={
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "no-store",
        })
