import datetime
from sqlalchemy import func, INT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class MyORMBase(Base):
    __abstract__ = True
    
    # id 使用 Mapped[int] 对应数据库的 BigInt
    # primary_key=True 且不指定 default 时，MySQL 默认会将其设为 AUTO_INCREMENT
    id: Mapped[int] = mapped_column(
        INT, 
        primary_key=True, 
        autoincrement=True,
        comment="自增主键"
    )
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(),
        comment="创建时间"
    )