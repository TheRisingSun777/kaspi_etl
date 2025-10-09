"""
SQLAlchemy ORM models for the transactional store.

Designed against SQLite first but with column types compatible with Postgres for
the upcoming migration.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    sku_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(80))
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    weight_kg: Mapped[Optional[Float]] = mapped_column(Float)
    base_cost_cny: Mapped[Optional[Float]] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    offers: Mapped[list["Offer"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("account_id", "offer_id", name="uq_offers_account_offer"),
        Index("ix_offers_sku_key", "sku_key"),
    )

    offer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_key: Mapped[str] = mapped_column(ForeignKey("products.sku_key", ondelete="CASCADE"), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(64))
    size_label: Mapped[Optional[str]] = mapped_column(String(32))
    kaspi_product_code: Mapped[Optional[str]] = mapped_column(String(64))

    product: Mapped["Product"] = relationship(back_populates="offers")
    stock_snapshots: Mapped[list["StockSnapshot"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="offer")


class StockSnapshot(Base):
    __tablename__ = "stock_snapshots"
    __table_args__ = (Index("ix_stock_snapshots_ts_utc", "ts_utc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.offer_id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ts_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=False, default=utcnow
    )

    offer: Mapped["Offer"] = relationship(back_populates="stock_snapshots")


class SalesDaily(Base):
    __tablename__ = "sales_daily"
    __table_args__ = (Index("ix_sales_daily_date", "date"),)

    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    revenue_kzt: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_orders_order_id"),
        Index("ix_orders_order_ts", "order_ts"),
    )

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(64))
    offer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("offers.offer_id", ondelete="SET NULL"))
    sku_key: Mapped[Optional[str]] = mapped_column(ForeignKey("products.sku_key", ondelete="SET NULL"))
    ordered_size: Mapped[Optional[str]] = mapped_column(String(32))
    final_size: Mapped[Optional[str]] = mapped_column(String(32))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[Optional[str]] = mapped_column(String(32))
    price_kzt: Mapped[Optional[Numeric]] = mapped_column(Numeric(14, 2))
    delivery_cost_kzt: Mapped[Optional[Numeric]] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    kaspi_fee_pct: Mapped[Optional[Float]] = mapped_column(Float, default=0.12, server_default="0.12")

    offer: Mapped[Optional["Offer"]] = relationship(back_populates="orders")
    product: Mapped[Optional["Product"]] = relationship()


class SizeMix(Base):
    __tablename__ = "size_mix"

    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), primary_key=True
    )
    size_label: Mapped[str] = mapped_column(String(32), primary_key=True)
    share: Mapped[float] = mapped_column(Float, nullable=False)


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), primary_key=True
    )
    scenario: Mapped[str] = mapped_column(String(32), primary_key=True, default="current", server_default="current")
    D_current: Mapped[Optional[Float]] = mapped_column(Float)
    sigma_90: Mapped[Optional[Float]] = mapped_column(Float)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), primary_key=True
    )
    good_days_total: Mapped[Optional[int]] = mapped_column(Integer)
    good_days_90: Mapped[Optional[int]] = mapped_column(Integer)
    data_rating_9mo: Mapped[Optional[Float]] = mapped_column(Float)
    data_rating_12mo: Mapped[Optional[Float]] = mapped_column(Float)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class InventoryPolicy(Base):
    __tablename__ = "inventory_policy"
    __table_args__ = (CheckConstraint("id = 1", name="ck_inventory_policy_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default="1")
    L_days: Mapped[int] = mapped_column(Integer, nullable=False)
    R_days: Mapped[int] = mapped_column(Integer, nullable=False)
    B_days: Mapped[int] = mapped_column(Integer, nullable=False)
    z_service: Mapped[float] = mapped_column(Float, nullable=False)
    tv_floor: Mapped[float] = mapped_column(Float, nullable=False)
    vat_pct: Mapped[float] = mapped_column(Float, nullable=False)
    platform_pct: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_blend_city: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_blend_country: Mapped[float] = mapped_column(Float, nullable=False)


class DesiredAllocation(Base):
    __tablename__ = "desired_allocations"

    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), primary_key=True
    )
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alloc_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class POPlan(Base):
    __tablename__ = "po_plan"

    po_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sku_key: Mapped[str] = mapped_column(
        ForeignKey("products.sku_key", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(String(32))
    t_post_days: Mapped[Optional[int]] = mapped_column(Integer)
    alloc_json_by_size: Mapped[Optional[dict]] = mapped_column(JSON)
    pre_json: Mapped[Optional[dict]] = mapped_column(JSON)
    post_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DeliveryBand(Base):
    __tablename__ = "delivery_bands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    price_min: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    price_max: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    weight_min_kg: Mapped[Float] = mapped_column(Float, nullable=False)
    weight_max_kg: Mapped[Float] = mapped_column(Float, nullable=False)
    fee_city_kzt: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2), nullable=True)
    fee_country_kzt: Mapped[Optional[Numeric]] = mapped_column(Numeric(10, 2), nullable=True)
    fee_city_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 4), nullable=True)
    fee_country_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 4), nullable=True)
    platform_fee_pct: Mapped[Optional[Numeric]] = mapped_column(Numeric(6, 4), nullable=True)
    currency_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    fx_rate_kzt: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 4), nullable=True)
    vat_rate: Mapped[Optional[Numeric]] = mapped_column(Numeric(5, 4), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
