import sqlalchemy

from .db_session import SqlAlchemyBase


class Notes(SqlAlchemyBase):
    __tablename__ = 'notes'
    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    chat_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, unique=True)
    note_text = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    reminder_time = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    date = sqlalchemy.Column(sqlalchemy.String, nullable=True)
