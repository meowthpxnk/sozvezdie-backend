from sqlalchemy.orm import DeclarativeBase, declared_attr

from app.utils.text import camel_to_snake
from .mixins import ReprStrMixin


class Base(DeclarativeBase, ReprStrMixin):
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    @declared_attr
    def __tablename__(cls) -> str:
        return camel_to_snake(cls.__name__)
