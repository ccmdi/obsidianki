"""Obsidian vault access via the Obsidian CLI (Obsidian 1.12+)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List

from obsidianki.cli.models import Note
from obsidianki.api.obsidian import OBSIDIAN_TIMEOUT_LENGTH
from obsidianki.api.obsidian_jsonlogic import eval_jsonlogic
from obsidianki.api.obsidian_ops import ObsidianVaultOpsMixin

# List all markdown files with metadata from the running Obsidian app (metadata cache).
_EVAL_LIST_MARKDOWN = (
    "JSON.stringify(app.vault.getMarkdownFiles().map(function(f){"
    "var c=app.metadataCache.getFileCache(f);var t=[];"
    "if(c&&c.tags){for(var i=0;i<c.tags.length;i++){"
    "t.push(c.tags[i].tag.replace(/^#/,''));}}"
    "return {path:f.path,filename:f.name,tags:t,size:f.stat.size,mtime:f.stat.mtime};"
    "}))"
)


class ObsidianCLIAPI(ObsidianVaultOpsMixin):
    """Same operations as ObsidianAPI, backed by ``obsidian`` CLI subprocess calls."""

    def __init__(self) -> None:
        configured = (os.getenv("OBSIDIAN_CLI_PATH") or "").strip()
        self._executable = configured or self._resolve_executable()
        self._vault = (os.getenv("OBSIDIAN_VAULT") or "").strip() or None
        self.timeout = int(os.getenv("OBSIDIAN_CLI_TIMEOUT", str(OBSIDIAN_TIMEOUT_LENGTH)))

    @staticmethod
    def _resolve_executable() -> str:
        path = shutil.which("obsidian")
        return path or "obsidian"

    def _command_prefix(self) -> List[str]:
        cmd = [self._executable]
        if self._vault:
            cmd.append(f"vault={self._vault}")
        return cmd

    _CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

    def _run(self, *args: str) -> str:
        cmd = self._command_prefix() + list(args)
        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=self._CREATE_NO_WINDOW,
            )
            stdout, stderr = proc.communicate(timeout=self.timeout)
        except FileNotFoundError as e:
            raise RuntimeError(
                "Obsidian CLI executable not found. Install Obsidian 1.12.7+, enable "
                "Settings -> General -> Command line interface, and ensure `obsidian` is on PATH."
            ) from e
        except subprocess.TimeoutExpired:
            if proc is not None:
                proc.kill()
                proc.wait()
            raise RuntimeError("Obsidian CLI command timed out.")

        if proc.returncode != 0:
            err = (stderr or "").strip() or (stdout or "").strip()
            raise RuntimeError(err or f"Obsidian CLI failed (exit {proc.returncode})")

        return stdout

    @staticmethod
    def _parse_json_array(stdout: str) -> List[Dict[str, Any]]:
        s = stdout.strip()
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            start = s.find("[")
            end = s.rfind("]")
            if start < 0 or end <= start:
                raise
            data = json.loads(s[start : end + 1])
        if not isinstance(data, list):
            raise ValueError("Expected JSON array from Obsidian eval")
        return data

    def _fetch_vault_contexts(self) -> List[Dict[str, Any]]:
        raw = self._run("eval", f"code={_EVAL_LIST_MARKDOWN}")
        return self._parse_json_array(raw)

    def search(self, query: Dict[str, Any]) -> List[Note]:
        contexts = self._fetch_vault_contexts()
        notes: List[Note] = []
        for row in contexts:
            if not isinstance(row, dict):
                continue
            path = row.get("path")
            if not path:
                continue
            note_data: Dict[str, Any] = {
                "path": path,
                "tags": row.get("tags") or [],
                "stat": {
                    "mtime": row.get("mtime"),
                    "size": row.get("size", 0),
                },
            }
            try:
                matched = eval_jsonlogic(query, note_data)
            except ValueError:
                raise
            if matched is None or matched is False:
                continue
            notes.append(
                Note.from_jsonlogic_result(
                    {"filename": path, "result": note_data},
                )
            )
        return notes

    def get_note_content(self, note_path: str) -> str:
        return self._run("read", f"path={note_path}").rstrip("\n")

    def test_connection(self) -> bool:
        try:
            self._run("version")
            return True
        except (RuntimeError, OSError):
            return False
