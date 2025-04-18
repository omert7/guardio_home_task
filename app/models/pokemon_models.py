from pydantic import BaseModel, Field, RootModel
from typing import List, Optional, Dict, Any, Union

class PokemonModel(BaseModel):
    number: int = Field(0, ge=0)
    name: str = ""
    type_one: str = ""
    type_two: str = ""
    total: int = Field(0, ge=0)
    hit_points: int = Field(0, ge=0)
    attack: int = Field(0, ge=0)
    defense: int = Field(0, ge=0)
    special_attack: int = Field(0, ge=0)
    special_defense: int = Field(0, ge=0)
    speed: int = Field(0, ge=0)
    generation: int = Field(0, ge=0)
    legendary: bool = False

    model_config = {
        "extra": "ignore"  # Allow extra fields to handle faulty data
    }


class RuleModel(BaseModel):
    url: str
    reason: str
    match: List[str] = []


class ConfigModel(BaseModel):
    rules: List[RuleModel] = []


class StatsModel(BaseModel):
    request_count: int = 0
    error_count: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    error_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    uptime_seconds: float = 0.0


class AllStatsModel(RootModel):
    root: Dict[str, StatsModel]
    
    # For backward compatibility
    def dict(self):
        return self.root
    
    def keys(self):
        return self.root.keys()
    
    def values(self):
        return self.root.values()
    
    def items(self):
        return self.root.items()
    
    def __getitem__(self, key):
        return self.root[key] 