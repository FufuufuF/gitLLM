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

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[TEntity]:
        stmt = self.list_stmt().offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return [self.to_entity(obj) for obj in result.scalars().all()] # type: ignore

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

    async def get_paginated(self, *, page=1, page_size=20) -> PaginatedResult[TEntity]:
        offset_value = (page - 1) * page_size
        stmt = self.list_stmt().offset(offset_value).limit(page_size)
        results = (await self.session.execute(stmt)).scalars().all()

        count_stmt = select(func.count()).select_from(self.model)
        total_count = (await self.session.execute(count_stmt)).scalar_one()

        total_pages = (total_count + page_size - 1) // page_size

        return PaginatedResult(
            items=[self.to_entity(obj) for obj in results], # type: ignore
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        
        
