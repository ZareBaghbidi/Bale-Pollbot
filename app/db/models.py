from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    users = relationship("UserClass", cascade="all, delete",
                         back_populates="class_")


class User(Base):
    __tablename__ = "users"

    chat_id = Column(Integer, primary_key=True)
    name = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    classes = relationship(
        "UserClass", cascade="all, delete", back_populates="user")


class UserClass(Base):
    __tablename__ = "user_classes"
    user_id = Column(Integer, ForeignKey(
        "users.chat_id", ondelete="CASCADE"), primary_key=True)
    class_id = Column(Integer, ForeignKey(
        "classes.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="classes")
    class_ = relationship("Class", back_populates="users")


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Text, nullable=False)
    class_name = Column("class", Text)
    active = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    questions = relationship(
        "Question", cascade="all, delete", back_populates="poll")
    votes = relationship("Vote", cascade="all, delete", back_populates="poll")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey(
        "polls.id", ondelete="CASCADE"), nullable=False)
    index = Column("index", Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    poll = relationship("Poll", back_populates="questions")
    votes = relationship("Vote", cascade="all, delete",
                         back_populates="question")

    __table_args__ = (UniqueConstraint(
        "poll_id", "index", name="uq_questions_poll_index"),)


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey(
        "polls.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey(
        "questions.id", ondelete="CASCADE"), nullable=False)
    value = Column(Text, nullable=False)
    user_id = Column(Integer, nullable=False)
    username = Column(Text)
    name = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp())

    poll = relationship("Poll", back_populates="votes")
    question = relationship("Question", back_populates="votes")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_at = Column(DateTime, nullable=False)
    poll_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    payload = Column(Text)
    name = Column(Text)
    phone = Column(Text)
    email = Column(Text)
    telegram_charge_id = Column(Text)
    provider_charge_id = Column(Text)
    timestamp = Column(Integer)
    status = Column(Text, default="completed")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    class_name = Column(Text)
    amount = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    payload = Column(Text)
    provider_token = Column(Text)
    sent_at = Column(Integer)
    status = Column(Text, default="sent")
    paid_at = Column(Integer)
    payment_id = Column(Integer, ForeignKey(
        "payments.id", ondelete="SET NULL"))
