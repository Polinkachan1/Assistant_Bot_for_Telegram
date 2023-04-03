import sqlalchemy

from .db_session import SqlAlchemyBase


class Users(SqlAlchemyBase):
    __tablename__ = 'users'
    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    chat_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, unique=True)
    send_weather = sqlalchemy.Column(sqlalchemy.Boolean, nullable=True)
    weather_time = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
