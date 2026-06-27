"""SQLite persistence layer for the retail simulation."""

from __future__ import annotations

from typing import Iterable

from sqlmodel import Field, Session, SQLModel, create_engine, select


class Product(SQLModel, table=True):
    """Product stored in the simulated ERP."""

    id: int | None = Field(default=None, primary_key=True)
    nome: str
    categoria: str = "outros"
    rsl: int
    preco_original: float
    preco_atual: float
    custo_unitario: float
    estoque: int


def create_database(db_url: str = "sqlite:///varejo_simulacao.db", reset: bool = True):
    """Create the SQLite engine and initialize tables."""

    engine = create_engine(db_url)
    if reset:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def seed_products(engine, products: Iterable[dict] | None = None) -> None:
    """Insert a small starter catalog when the database is empty."""

    default_products = products or [
        {
            "nome": "Iogurte natural",
            "categoria": "perecivel",
            "rsl": 3,
            "preco_original": 6.90,
            "preco_atual": 6.90,
            "custo_unitario": 4.15,
            "estoque": 24,
        },
        {
            "nome": "Pao de forma",
            "categoria": "padaria",
            "rsl": 5,
            "preco_original": 8.50,
            "preco_atual": 8.50,
            "custo_unitario": 5.10,
            "estoque": 18,
        },
        {
            "nome": "Salada pronta",
            "categoria": "saudavel",
            "rsl": 2,
            "preco_original": 14.90,
            "preco_atual": 14.90,
            "custo_unitario": 8.95,
            "estoque": 12,
        },
    ]

    with Session(engine) as session:
        existing = session.exec(select(Product)).first()
        if existing is not None:
            return

        session.add_all(Product(**item) for item in default_products)
        session.commit()
