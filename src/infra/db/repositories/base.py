from __future__ import annotations
from typing import Any, Generic, Sequence, Type, TypeVar
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from src.infra.db.models.base import MyORMBase
    
TModel = TypeVar("TModel", bound=MyORMBase)

class BaseRepository(BaseModel,Generic[TModel]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: AsyncSession
    model: Type[TModel]

    async def get(self, id: int) -> TModel | None:
        return await self.session.get(self.model, id)

    def list_stmt(self) -> Select[tuple[TModel]]:
        return select(self.model)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[TModel]:
        stmt = self.list_stmt().offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, obj: TModel) -> TModel:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: TModel) -> None:
        await self.session.delete(obj)

    async def delete_by_id(self, id: int) -> int:
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0) # type: ignore
