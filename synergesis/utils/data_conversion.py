# synergesis/utils/data_conversion.py
"""
Utility functions for converting data between different formats.
"""
from typing import Any, Dict
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

def pydantic_to_neo4j(p_model: BaseModel) -> Dict[str, Any]:
    """
    Converts a Pydantic model into a dictionary suitable for Neo4j properties.
    It handles common Pydantic features like enums and nested models.
    Note: Neo4j's Python driver can handle native datetime objects, so they
    are passed through directly.
    """
    # Use .model_dump() for Pydantic V2
    model_dict = p_model.model_dump()

    # Neo4j doesn't handle Enum objects directly, so convert them to their values.
    # A recursive approach can be taken, but for now, we handle the top level.
    # A more robust implementation would traverse the entire dict.
    for key, value in model_dict.items():
        if isinstance(value, Enum):
            model_dict[key] = value.value
        # The driver handles datetimes, so no special handling needed.

    return model_dict
