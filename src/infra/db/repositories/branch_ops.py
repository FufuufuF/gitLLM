from src.infra.db.repositories.base import BaseRepository
from src.infra.db.models.branch_ops import BranchOp as BranchOpModel
from src.domain.models import BranchOp


class BranchOpRepository(BaseRepository[BranchOpModel, BranchOp]):
    model = BranchOpModel
    schema_class = BranchOp
