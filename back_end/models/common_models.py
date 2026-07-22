from sqlalchemy import (
    Column,
    JSON,
    Table,
    UUID,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

try:
    from back_end.database_common import Base
except ModuleNotFoundError:
    from database_common import Base


# Existing common_db tables used only for foreign key resolution.
users_table = Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    extend_existing=True,
)

equipment_groups_table = Table(
    "equipment_groups",
    Base.metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    extend_existing=True,
)

equipment_table = Table(
    "equipment",
    Base.metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("group_id", UUID(as_uuid=False), nullable=True),
    extend_existing=True,
)


class Factory(Base):
    __tablename__ = "factory"

    factory_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    factory_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RecorderIp(Base):
    __tablename__ = "recorder_ip"

    recorder_ip_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    port_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=502,
        server_default="502",
    )
    group_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "ip_address",
            "group_no",
            name="uq_recorder_ip_ip_address_group_no",
        ),
    )


class FurnaceRecorderMap(Base):
    __tablename__ = "furnace_recorder_map"

    furnace_recorder_map_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    equipment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    factory_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("factory.factory_id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorder_ip_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("recorder_ip.recorder_ip_id", ondelete="RESTRICT"),
        nullable=False,
    )
    csv_file_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "equipment_id",
            "recorder_ip_id",
            "csv_file_name",
            name="uq_furnace_recorder_map_equipment_ip_csv",
        ),
    )


class CheckRecord(Base):
    __tablename__ = "check_record"

    check_record_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    factory_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("factory.factory_id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    recorder_ip_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("recorder_ip.recorder_ip_id", ondelete="SET NULL"),
        nullable=True,
    )
    record_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    check_type: Mapped[str] = mapped_column(String(10), nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CsvSendRecord(Base):
    __tablename__ = "csv_send_record"

    csv_send_record_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    equipment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    factory_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("factory.factory_id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorder_ip_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("recorder_ip.recorder_ip_id", ondelete="SET NULL"),
        nullable=True,
    )
    instruction_no: Mapped[str] = mapped_column(String(100), nullable=False)
    instruction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_status: Mapped[str] = mapped_column(String(20), nullable=False)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0, server_default="0")
    sent_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommentRecord(Base):
    __tablename__ = "comment_record"

    comment_record_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    equipment_group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("equipment_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    factory_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("factory.factory_id", ondelete="RESTRICT"),
        nullable=False,
    )
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
