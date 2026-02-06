from __future__ import annotations
from typing import Any, Generic, Sequence, Type, TypeVar
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.infra.db.models.base import MyORMBase
    
TModel = TypeVar("TModel", bound=MyORMBase)
TEntity = TypeVar("TEntity", bound=BaseModel)

class PaginatedResult(BaseModel, Generic[TEntity]):
    items: list[TEntity]
    total: int
    page: int
    page_size: int
    total_pages: int

class BaseRepository(Generic[TModel, TEntity]):
    model: Type[TModel]
    schema_class: Type[TEntity]

    def __init__(self, session: AsyncSession):
        self.session = session

    def to_entity(self, obj: TModel | None) -> TEntity | None:
        if obj is None:
            return None
        return self.schema_class.model_validate(obj)

    async def get(self, id: int) -> TEntity | None:
        orm_obj = await self.session.get(self.model, id)
        return self.to_entity(orm_obj)

    def list_stmt(self) -> Select[tuple[TModel]]:
        return select(self.model)

    async def add(self, entity: TEntity) -> TEntity:
        data = entity.model_dump(exclude={'id', 'created_at'}, exclude_unset=True)
        orm_obj = self.model(**data)
        
        self.session.add(orm_obj)
        await self.session.flush()
        await self.session.refresh(orm_obj)
        
        return self.to_entity(orm_obj) # type: ignore

    async def delete(self, obj: TModel) -> None:
        await self.session.delete(obj)

    async def delete_by_id(self, id: int) -> int:
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0) # type: ignore
        
        
