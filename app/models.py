"""SQLAlchemy models; no guest-facing serializers in this module."""
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EventSettings(Base):
    __tablename__ = 'event_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue: Mapped[str | None] = mapped_column(String(240), nullable=True)
    edit_deadline_utc: Mapped[object | None] = mapped_column(DateTime(timezone=False), nullable=True)
    buffet_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=40)


class Family(Base):
    __tablename__ = 'families'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False)
    attending: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submission_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    edit_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    participants: Mapped[list['Participant']] = relationship(
        back_populates='family', cascade='all, delete-orphan',
        order_by='Participant.position', lazy='selectin')


class Participant(Base):
    __tablename__ = 'participants'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey('families.id', ondelete='CASCADE'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    family: Mapped[Family] = relationship(back_populates='participants')
    __table_args__ = (UniqueConstraint('family_id', 'position', name='uq_family_position'),)
