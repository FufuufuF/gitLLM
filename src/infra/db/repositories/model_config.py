from src.infra.db.repositories.base import BaseRepository
from src.domain.models import ModelConfig
from src.infra.db.models.model_config import ModelConfig as ModelConfigModel

class ModelConfigRepository(BaseRepository[ModelConfigModel, ModelConfig]):
    model = ModelConfigModel
    schema_class = ModelConfig
