
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.models.enums import ModelStatus, ModelType


@dataclass
class ModelConfiguration:

    model_name: str
    model_type: ModelType
    version: str = "1.0.0"
    embedding_dimension: int = 384
    max_sequence_length: int = 256
    device: str = "cpu"
    normalize_embeddings: bool = True
    status: ModelStatus = ModelStatus.REGISTERED
    error_message: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.model_name or not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")
        if not isinstance(self.model_type, ModelType):
            if isinstance(self.model_type, str):
                self.model_type = ModelType(self.model_type.upper())
            else:
                raise ValueError(f"Invalid model_type: {self.model_type}")
        if not isinstance(self.status, ModelStatus):
            if isinstance(self.status, str):
                self.status = ModelStatus(self.status.upper())
            else:
                self.status = ModelStatus.REGISTERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_type": self.model_type.value,
            "version": self.version,
            "embedding_dimension": self.embedding_dimension,
            "max_sequence_length": self.max_sequence_length,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "status": self.status.value,
            "error_message": self.error_message,
            "parameters": self.parameters,
            "is_enabled": self.is_enabled,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfiguration":
        return cls(
            model_name=data["model_name"],
            model_type=ModelType(data["model_type"]),
            version=data.get("version", "1.0.0"),
            embedding_dimension=int(data.get("embedding_dimension", 384)),
            max_sequence_length=int(data.get("max_sequence_length", 256)),
            device=data.get("device", "cpu"),
            normalize_embeddings=bool(data.get("normalize_embeddings", True)),
            status=ModelStatus(data.get("status", ModelStatus.REGISTERED.value)),
            error_message=data.get("error_message"),
            parameters=data.get("parameters", {}),
            is_enabled=data.get("is_enabled", True),
            notes=data.get("notes"),
        )
