"""Background worker for local/SFTP deployment. (Phase 6-7)"""
from __future__ import annotations

# Placeholder — Phase 6 will implement a QThread subclass:
#
# class DeployWorker(QThread):
#     progress = Signal(int, int, str)   # current, total, filename
#     finished = Signal(bool, str)       # success, message
#
#     def __init__(self, source_root, dest_config, event_slug, mode): ...
#     def run(self): ...
#     def stop(self): ...
