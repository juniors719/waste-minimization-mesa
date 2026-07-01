"""Retail simulation model."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque
import random

try:
    import mesa
except Exception:  # pragma: no cover - keep the simulation runnable in broken Mesa installs
    mesa = None

from sqlmodel import Session, select

from .agents import (
    AnalysisAgent,
    ConsumerAgent,
    InventoryAgent,
    PricingAgent,
    SupplierAgent,
    build_consumer_profiles,
)
from .db import Product, create_database, seed_products


DEFAULT_RESTOCK_CATALOG = (
    {
        "nome": "Iogurte natural",
        "categoria": "perecivel",
        "rsl": 7,
        "preco_original": 6.90,
        "preco_atual": 6.90,
        "custo_unitario": 4.15,
        "estoque": 6,
    },
    {
        "nome": "Leite integral",
        "categoria": "perecivel",
        "rsl": 8,
        "preco_original": 5.00,
        "preco_atual": 5.00,
        "custo_unitario": 3.00,
        "estoque": 8,
    },
    {
        "nome": "Queijo Minas Frescal",
        "categoria": "perecivel",
        "rsl": 5,
        "preco_original": 25.00,
        "preco_atual": 25.00,
        "custo_unitario": 15.00,
        "estoque": 5,
    },
    {
        "nome": "Frango Desossado",
        "categoria": "perecivel",
        "rsl": 3,
        "preco_original": 18.00,
        "preco_atual": 18.00,
        "custo_unitario": 10.80,
        "estoque": 4,
    },
    {
        "nome": "Ovos Grandes",
        "categoria": "perecivel",
        "rsl": 14,
        "preco_original": 10.00,
        "preco_atual": 10.00,
        "custo_unitario": 6.00,
        "estoque": 10,
    },
    {
        "nome": "Pao de forma",
        "categoria": "padaria",
        "rsl": 10,
        "preco_original": 8.50,
        "preco_atual": 8.50,
        "custo_unitario": 5.10,
        "estoque": 5,
    },
    {
        "nome": "Bolo de Cenoura",
        "categoria": "padaria",
        "rsl": 3,
        "preco_original": 12.00,
        "preco_atual": 12.00,
        "custo_unitario": 7.20,
        "estoque": 4,
    },
    {
        "nome": "Sonho de Creme",
        "categoria": "padaria",
        "rsl": 2,
        "preco_original": 7.50,
        "preco_atual": 7.50,
        "custo_unitario": 4.50,
        "estoque": 3,
    },
    {
        "nome": "Broa de Milho",
        "categoria": "padaria",
        "rsl": 4,
        "preco_original": 6.00,
        "preco_atual": 6.00,
        "custo_unitario": 3.60,
        "estoque": 4,
    },
    {
        "nome": "Pao Integral",
        "categoria": "padaria",
        "rsl": 8,
        "preco_original": 9.90,
        "preco_atual": 9.90,
        "custo_unitario": 5.95,
        "estoque": 6,
    },
    {
        "nome": "Salada pronta",
        "categoria": "saudavel",
        "rsl": 4,
        "preco_original": 14.90,
        "preco_atual": 14.90,
        "custo_unitario": 8.95,
        "estoque": 4,
    },
    {
        "nome": "Suco verde",
        "categoria": "saudavel",
        "rsl": 5,
        "preco_original": 9.90,
        "preco_atual": 9.90,
        "custo_unitario": 5.95,
        "estoque": 5,
    },
    {
        "nome": "Mix de Castanhas",
        "categoria": "saudavel",
        "rsl": 60,
        "preco_original": 19.90,
        "preco_atual": 19.90,
        "custo_unitario": 11.95,
        "estoque": 6,
    },
    {
        "nome": "Barra de Cereal Integral",
        "categoria": "saudavel",
        "rsl": 90,
        "preco_original": 4.50,
        "preco_atual": 4.50,
        "custo_unitario": 2.70,
        "estoque": 8,
    },
    {
        "nome": "Água de Coco",
        "categoria": "saudavel",
        "rsl": 30,
        "preco_original": 6.00,
        "preco_atual": 6.00,
        "custo_unitario": 3.60,
        "estoque": 6,
    },
)


@dataclass
class SimulationMetrics:
    """Simple in-memory metrics for each tick."""

    tick: int
    total_stock: int
    expired_items: int
    sold_units: int
    revenue: float
    waste_units: int
    waste_value: float
    profit: float
    margin: float


@dataclass
class ScenarioResult:
    """Compact summary for comparing scenarios."""

    name: str
    metrics: list[SimulationMetrics]

    @property
    def final(self) -> SimulationMetrics:
        return self.metrics[-1]


ModelBase = mesa.Model if mesa is not None else object  # type: ignore[attr-defined]


class RetailModel(ModelBase):  # type: ignore[misc]
    """Orchestrates daily simulation steps."""

    def __init__(
        self,
        db_url: str = "sqlite:///varejo_simulacao.db",
        num_consumers: int = 80,
        critical_rsl: int = 3,
        minimum_margin: float = 0.10,
        rsl_reference: int = 6,
        pricing_enabled: bool = True,
        fallback_pricing_enabled: bool = False,
        reset_database: bool = True,
        restock_strategy: str = "demand",
        restock_interval: int = 5,
        restock_threshold: int = 15,
        restock_lead_time: int = 2,
        seed: int | None = None,
    ):
        if mesa is not None:
            super().__init__()

        self.rng = random.Random(seed)
        self.engine = create_database(db_url, reset=reset_database)
        seed_products(self.engine)

        self.critical_rsl = critical_rsl
        self.minimum_margin = minimum_margin
        self.rsl_reference = rsl_reference
        self.pricing_enabled = pricing_enabled
        self.fallback_pricing_enabled = fallback_pricing_enabled
        self.restock_strategy = restock_strategy
        self.restock_interval = restock_interval
        self.restock_threshold = restock_threshold
        self.restock_lead_time = max(1, restock_lead_time)
        self.restock_enabled = True
        self.current_tick = 0
        self.restock_events = 0
        self.market_snapshot: dict[str, float | int] = {}
        self.sales_window: dict[str, int] = {}
        self.critical_product_ids: list[int] = []
        self._pending_restock_orders: list[tuple[int, list[dict[str, float | int | str]]]] = []
        self._daily_sales = Counter()
        self._sales_history: Deque[Counter] = deque(maxlen=5)
        self._last_expired_units = 0
        self._last_sold_units = 0
        self._last_revenue = 0.0
        self._last_sold_cost = 0.0
        self._last_waste_units = 0
        self._last_waste_value = 0.0

        self.analysis_agent = AnalysisAgent(1, self)
        self.supplier_agent = SupplierAgent(2, self)
        self.inventory_agent = InventoryAgent(3, self)
        self.pricing_agent = PricingAgent(4, self)
        self.consumer_agents = self._build_consumers(num_consumers)
        self.agent_sequence = [
            self.analysis_agent,
            self.supplier_agent,
            self.inventory_agent,
            self.pricing_agent,
            *self.consumer_agents,
        ]
        self.metrics: list[SimulationMetrics] = []

    def _build_consumers(self, num_consumers: int) -> list[ConsumerAgent]:
        profiles = build_consumer_profiles()
        consumers: list[ConsumerAgent] = []
        for index in range(num_consumers):
            profile = profiles[index % len(profiles)]
            consumers.append(ConsumerAgent(5 + index, self, profile))
        return consumers

    def collect_market_snapshot(self) -> dict[str, float | int]:
        with Session(self.engine) as session:
            products = session.exec(select(Product).where(Product.estoque > 0)).all()

        if not products:
            return {
                "total_stock": 0,
                "average_stock": 0.0,
                "average_rsl": 0.0,
                "average_price": 0.0,
                "product_count": 0,
            }

        total_stock = sum(product.estoque for product in products)
        average_stock = total_stock / len(products)
        average_rsl = sum(product.rsl for product in products) / len(products)
        average_price = sum(product.preco_atual for product in products) / len(products)

        return {
            "total_stock": total_stock,
            "average_stock": round(average_stock, 2),
            "average_rsl": round(average_rsl, 2),
            "average_price": round(average_price, 2),
            "product_count": len(products),
        }

    def collect_sales_window(self, days: int = 5) -> dict[str, int]:
        # Converte o deque para list para permitir o slicing [-days:]
        history_list = list(self._sales_history)
        window = history_list[-days:] if days > 0 else history_list
        
        sales = Counter()
        for daily_sales in window:
            sales.update(daily_sales)
        return dict(sales)

    def _current_stock_by_name(self) -> dict[str, int]:
        with Session(self.engine) as session:
            products = session.exec(select(Product).where(Product.estoque > 0)).all()

        stock_by_name: dict[str, int] = {}
        for product in products:
            stock_by_name[product.nome] = stock_by_name.get(product.nome, 0) + product.estoque
        return stock_by_name

    def _pending_stock_by_name(self) -> dict[str, int]:
        pending_stock: Counter[str] = Counter()
        for _, items in self._pending_restock_orders:
            for item in items:
                pending_stock[str(item["nome"])] += int(item["estoque"])
        return dict(pending_stock)

    def daily_demand_multiplier(self) -> float:
        day_pattern = (0.8, 0.9, 1.0, 1.1, 1.3, 1.6, 1.2)
        return day_pattern[self.current_tick % len(day_pattern)]

    def schedule_restock_order(self, restock_plan: list[dict]) -> None:
        arrival_tick = self.current_tick + self.restock_lead_time
        self._pending_restock_orders.append((arrival_tick, restock_plan))

    def process_pending_restock_orders(self) -> None:
        if not self._pending_restock_orders:
            return

        due_orders = [order for order in self._pending_restock_orders if order[0] <= self.current_tick]
        if not due_orders:
            return

        remaining_orders = [order for order in self._pending_restock_orders if order[0] > self.current_tick]
        with Session(self.engine) as session:
            for _, restock_plan in due_orders:
                session.add_all(Product(**item) for item in restock_plan)
            session.commit()

        for _, restock_plan in due_orders:
            self.restock_events += 1
            print(
                f"\n[Fornecedor] Novos lotes chegaram no tick {self.current_tick} "
                f"(pedido #{self.restock_events})."
            )

        self._pending_restock_orders = remaining_orders

    def should_restock_today(self) -> bool:
        if self.current_tick <= 0:
            return False

        due_by_interval = self.current_tick % max(self.restock_interval, 1) == 0
        if self.restock_strategy == "fixed":
            return due_by_interval

        stock_by_name = self._current_stock_by_name()
        pending_by_name = self._pending_stock_by_name()
        for template in DEFAULT_RESTOCK_CATALOG:
            current_stock = stock_by_name.get(template["nome"], 0) + pending_by_name.get(template["nome"], 0)
            target_stock = max(2, int(template["estoque"] * 0.6))
            if current_stock <= target_stock:
                return True

        return due_by_interval

    def build_restock_plan(self) -> list[dict]:
        snapshot = self.market_snapshot or self.collect_market_snapshot()
        sales_window = self.sales_window or self.collect_sales_window(days=5)
        stock_by_name = self._current_stock_by_name()
        pending_by_name = self._pending_stock_by_name()
        average_rsl = float(snapshot["average_rsl"])
        freshness_gap = max(0.0, float(self.rsl_reference) - average_rsl)
        window_days = max(1, len(self._sales_history) or 5)

        plan: list[dict] = []
        for template in DEFAULT_RESTOCK_CATALOG:
            recent_sales = sales_window.get(template["nome"], 0)
            current_stock = stock_by_name.get(template["nome"], 0) + pending_by_name.get(template["nome"], 0)
            base_quantity = int(template["estoque"])
            safety_stock = max(2, int(round(base_quantity * 0.5)))
            expected_daily_sales = recent_sales / window_days

            if self.restock_strategy == "fixed":
                quantity = base_quantity
            else:
                target_stock = expected_daily_sales * self.restock_lead_time + safety_stock + freshness_gap * 0.5
                target_stock = max(float(base_quantity), target_stock)
                quantity = max(0, int(round(target_stock - current_stock)))

            if quantity <= 0:
                continue

            plan.append(
                {
                    "nome": template["nome"],
                    "categoria": template["categoria"],
                    "rsl": int(template["rsl"] + max(0, round(freshness_gap))),
                    "preco_original": template["preco_original"],
                    "preco_atual": template["preco_original"],
                    "custo_unitario": template["custo_unitario"],
                    "estoque": quantity,
                }
            )

        return plan

    def record_sale(self, product: Product) -> None:
        self._last_sold_units += 1
        self._last_revenue += product.preco_atual
        self._last_sold_cost += product.custo_unitario
        self._daily_sales[product.nome] += 1

    def record_waste(self, product: Product) -> None:
        self._last_waste_units += 1
        self._last_waste_value += product.custo_unitario

    def _age_products(self) -> int:
        expired = 0
        with Session(self.engine) as session:
            products = session.exec(select(Product).where(Product.estoque > 0)).all()

            for product in products:
                product.rsl -= 1
                if product.rsl < 0:
                    self.record_waste(product)
                    product.estoque = 0
                    expired += 1
                session.add(product)

            session.commit()

        return expired

    def total_stock(self) -> int:
        with Session(self.engine) as session:
            return sum(product.estoque for product in session.exec(select(Product)).all())

    def step(self):
        self._last_expired_units = 0
        self._last_sold_units = 0
        self._last_revenue = 0.0
        self._last_sold_cost = 0.0
        self._last_waste_units = 0
        self._last_waste_value = 0.0

        expired = self._age_products()
        self._last_expired_units = expired

        self.process_pending_restock_orders()

        self.analysis_agent.step()
        self.supplier_agent.step()
        self.inventory_agent.step()
        self.pricing_agent.step()

        for agent in self.consumer_agents:
            agent.step()

        total_stock = self.total_stock()
        gross_profit = self._last_revenue - self._last_sold_cost - self._last_waste_value
        margin = (gross_profit / self._last_revenue) if self._last_revenue > 0 else 0.0

        self.metrics.append(
            SimulationMetrics(
                tick=self.current_tick,
                total_stock=total_stock,
                expired_items=expired,
                sold_units=self._last_sold_units,
                revenue=round(self._last_revenue, 2),
                waste_units=self._last_waste_units,
                waste_value=round(self._last_waste_value, 2),
                profit=round(gross_profit, 2),
                margin=round(margin, 4),
            )
        )

        self._sales_history.append(self._daily_sales.copy())
        self._daily_sales.clear()
        self.market_snapshot = self.collect_market_snapshot()
        self.sales_window = self.collect_sales_window(days=5)
        self.current_tick += 1

    def run(self, days: int = 10):
        for _ in range(days):
            self.step()
        return self.metrics


def summarize_metrics(metrics: list[SimulationMetrics]) -> dict[str, float | int]:
    """Aggregate the full run into a single summary."""

    if not metrics:
        return {
            "ticks": 0,
            "total_stock": 0,
            "expired_items": 0,
            "sold_units": 0,
            "revenue": 0.0,
            "waste_units": 0,
            "waste_value": 0.0,
            "profit": 0.0,
            "margin": 0.0,
        }

    final = metrics[-1]
    total_revenue = sum(item.revenue for item in metrics)
    total_profit = sum(item.profit for item in metrics)
    return {
        "ticks": len(metrics),
        "total_stock": final.total_stock,
        "expired_items": sum(item.expired_items for item in metrics),
        "sold_units": sum(item.sold_units for item in metrics),
        "revenue": round(total_revenue, 2),
        "waste_units": sum(item.waste_units for item in metrics),
        "waste_value": round(sum(item.waste_value for item in metrics), 2),
        "profit": round(total_profit, 2),
        "margin": round((total_profit / total_revenue) if total_revenue > 0 else 0.0, 4),
    }


def run_scenario(
    *,
    name: str,
    days: int,
    db_url: str,
    num_consumers: int,
    pricing_enabled: bool,
    fallback_pricing_enabled: bool = False,
    minimum_margin: float = 0.10,
    rsl_reference: int = 6,
    restock_lead_time: int = 2,
    seed: int | None = None,
    restock_strategy: str = "demand",
    restock_interval: int = 5,
    restock_threshold: int = 15,
) -> ScenarioResult:
    """Run one scenario with a reproducible random seed."""

    model = RetailModel(
        db_url=db_url,
        num_consumers=num_consumers,
        minimum_margin=minimum_margin,
        rsl_reference=rsl_reference,
        pricing_enabled=pricing_enabled,
        fallback_pricing_enabled=fallback_pricing_enabled,
        restock_lead_time=restock_lead_time,
        restock_strategy=restock_strategy,
        restock_interval=restock_interval,
        restock_threshold=restock_threshold,
        seed=seed,
    )
    metrics = model.run(days=days)
    return ScenarioResult(name=name, metrics=metrics)
