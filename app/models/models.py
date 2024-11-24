from sqlalchemy import Boolean, Column, DateTime, Integer, Interval, String, ForeignKey, Enum, UniqueConstraint, JSON
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import timedelta
from enum import Enum as PythonEnum
from ..settings.database import Base


class UserRole(str, PythonEnum):
    super_admin = "super_admin"
    admin =  "admin"
    user = "user"


class ChatMessages(Base):
    __tablename__ = 'chat_messages'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    message = Column(String)
    fileUrl = Column(String)
    voiceUrl = Column(String)
    videoUrl = Column(String)
    receiver_id = Column(UUID, ForeignKey('users.id', ondelete='SET NULL'))
    rooms = Column(String, ForeignKey('rooms.name_room', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    room_id = Column(UUID, ForeignKey('rooms.id', ondelete='CASCADE'))
    id_return = Column(UUID, nullable=True)

    edited = Column(Boolean, server_default='false')
    return_message = Column(JSON, server_default=None)
    deleted = Column(Boolean, server_default='false')

    # # Relationships
    # reports = relationship("Report", back_populates="message")
    # notifications = relationship("Notification", back_populates="message")


class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'), nullable=False)
    email = Column(String, nullable=False, unique=True)
    user_name = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    avatar = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    verified = Column(Boolean, nullable=False, server_default='false')
    token_verify = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.user)
    blocked = Column(Boolean, nullable=False, server_default='false')
    password_changed = Column(TIMESTAMP(timezone=True), nullable=True)
    company_id = Column(UUID, ForeignKey('companies.id', ondelete="CASCADE"), nullable=True)
    active = Column(Boolean, nullable=False, server_default='True')
    description = Column(String)

    # company = relationship("Company", back_populates="users")
    bans = relationship("Ban", back_populates="users")
    # Relationships
    # reports = relationship("Report", back_populates="reported_by_user")
    # notifications = relationship("Notification", back_populates="moderator")

    __table_args__ = (
        UniqueConstraint('email', name='uq_user_email'),
        UniqueConstraint('user_name', name='uq_user_name'),
    )


class UserStatus(Base):
    __tablename__ = 'user_status'

    id = Column(Integer, primary_key=True, nullable=False, index=True, autoincrement=True)
    room_id = Column(UUID, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    name_room = Column(String, ForeignKey("rooms.name_room", ondelete="CASCADE", onupdate='CASCADE'), nullable=False)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_name = Column(String, nullable=False)
    status = Column(Boolean, server_default='True', nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))


class Rooms(Base):
    __tablename__ = 'rooms'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'), nullable=False)
    name_room = Column(String, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    image_room = Column(String, nullable=False)
    owner = Column(UUID, (ForeignKey("users.id", ondelete='SET NULL')), nullable=True)
    secret_room = Column(Boolean, default=False)
    block = Column(Boolean, nullable=False, server_default='false')
    delete_at = Column(TIMESTAMP(timezone=True), nullable=True)
    company_id = Column(UUID, ForeignKey('companies.id', ondelete="CASCADE"), nullable=True)
    description = Column(String(255), nullable=True)

    # Relationships
    # company = relationship("Company", back_populates="rooms")
    # invitations = relationship("RoomInvitation", back_populates="rooms")
    # notifications = relationship("Notification", back_populates="rooms")


class Ban(Base):
    __tablename__ = 'bans'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    room_id = Column(UUID, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)

    users = relationship("User", back_populates="bans")


class ChatMessageVote(Base):
    __tablename__ = 'chat_message_votes'

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    message_id = Column(UUID, ForeignKey("chat_messages.id", ondelete="CASCADE"), primary_key=True)
    dir = Column(Integer)
    
class UserOnlineTime(Base):
    __tablename__ = 'user_online_time'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    session_start = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    session_end = Column(TIMESTAMP(timezone=True), nullable=True)
    total_online_time = Column(Interval, nullable=True, default=timedelta())