# fers_core/cloud/__init__.py
"""
FersCloud integration — authenticate with your FersCloud account
and save/load FERS models to the cloud.
"""

from .client import FersCloudClient

__all__ = ["FersCloudClient"]
