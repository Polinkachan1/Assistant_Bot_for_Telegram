import sqlalchemy
from sqlalchemy import orm

from .db_session import SqlAlchemyBase


class Notes(SqlAlchemyBase):
    __tablename__ = 'notes'
    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    chat_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    note_text = sqlalchemy.Column(sqlalchemy.String, nullable=True)
