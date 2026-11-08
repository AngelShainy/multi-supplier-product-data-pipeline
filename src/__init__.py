"""Multi-Supplier Product Data Integration Pipeline source package."""
from src.pipeline import run_pipeline
from src.data_generator import generate_synthetic_data
from src.database import DuckDBManager

__all__ = [
    "run_pipeline",
    "generate_synthetic_data",
    "DuckDBManager",
]
