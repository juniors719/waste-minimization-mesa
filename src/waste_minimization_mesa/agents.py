"""Mesa agents for inventory, pricing, supplier, analysis, and consumer behavior."""

from __future__ import annotations

import random
from dataclasses import dataclass

try:
    import mesa
except Exception:  # pragma: no cover - keep the simulation runnable in broken Mesa installs
    mesa = None

from sqlmodel import Session, select

from .db import Product


AgentBase = mesa.Agent if mesa is not None else object  # type: ignore[attr-defined]


class CompatAgent(AgentBase):  # type: ignore[misc]
    """Compatibility wrapper for different Mesa agent signatures."""

    def __init__(self, unique_id, model):
        if mesa is None:
            self.unique_id = unique_id
            self.model = model
            return

        try:
            super().__init__(unique_id, model)
        except TypeError:
            super().__init__(model)
            self.unique_id = unique_id


@dataclass(frozen=True)
class ConsumerProfile:
    """Behavioral profile used to diversify consumer demand."""

    name: str
    base_purchase_probability: float
    discount_sensitivity: float
    category_preferences: dict[str, float]
    impulse: float = 0.0


class AnalysisAgent(CompatAgent):
    """Publishes daily operational indicators for the other agents."""

    def step(self):
        self.model.market_snapshot = self.model.collect_market_snapshot()
        self.model.sales_window = self.model.collect_sales_window(days=5)


class SupplierAgent(CompatAgent):
    """Replenishes inventory using recent sales, stock, and freshness signals."""

    def step(self):
        if not self.model.restock_enabled:
            return

        if not self.model.should_restock_today():
            return

        restock_plan = self.model.build_restock_plan()
        if not restock_plan:
            return

        with Session(self.model.engine) as session:
            session.add_all(Product(**item) for item in restock_plan)
            session.commit()

        self.model.restock_events += 1
        print(
            f"\n[Fornecedor] Novos lotes chegaram no tick {self.model.current_tick} "
            f"(pedido #{self.model.restock_events})."
        )


class InventoryAgent(CompatAgent):
    """Identifies critical products and shares them with pricing."""

    def step(self):
        with Session(self.model.engine) as session:
            statement = select(Product).where(
                Product.rsl <= self.model.critical_rsl,
                Product.estoque > 0,
            )
            critical_products = session.exec(statement).all()
            self.model.critical_product_ids = [product.id for product in critical_products if product.id is not None]


class PricingAgent(CompatAgent):
    """Applies a bounded, risk-based discount policy."""

    def _minimum_price(self, product: Product) -> float:
        return round(product.custo_unitario * (1 + self.model.minimum_margin), 2)

    def _risk_score(self, product: Product) -> float:
        snapshot = self.model.market_snapshot or self.model.collect_market_snapshot()
        window_sales = self.model.sales_window.get(product.nome, 0)

        avg_stock = max(float(snapshot["average_stock"]), 1.0)
        stock_pressure = min(1.0, product.estoque / max(avg_stock * 1.5, 1.0))
        freshness_pressure = max(0.0, 1.0 - (product.rsl / max(self.model.rsl_reference, 1)))
        demand_pressure = max(0.0, 1.0 - (window_sales / max(window_sales + product.estoque, 1)))

        risk = 100.0 * (
            0.30 * stock_pressure
            + 0.45 * freshness_pressure
            + 0.25 * demand_pressure
        )
        return max(0.0, min(100.0, risk))

    def _discount_rate(self, risk: float) -> float:
        if risk < 20:
            return 0.0
        if risk < 40:
            return 0.1
        if risk < 60:
            return 0.2
        if risk < 80:
            return 0.3
        return 0.40

    def _target_price(self, product: Product) -> float:
        risk = self._risk_score(product)
        discount_rate = self._discount_rate(risk)
        floor_price = self._minimum_price(product)
        target_price = product.preco_original * (1 - discount_rate)
        return round(max(floor_price, target_price), 2)

    def evaluate_discount(self, product_id: int) -> None:
        if not self.model.pricing_enabled:
            return

        with Session(self.model.engine) as session:
            product = session.get(Product, product_id)
            if product is None:
                return

            target_price = self._target_price(product)
            if target_price >= product.preco_atual:
                return

            product.preco_atual = target_price
            session.add(product)
            session.commit()

    def step(self):
        if not self.model.pricing_enabled:
            return

        targets = list(self.model.critical_product_ids)
        if not targets and self.model.fallback_pricing_enabled:
            with Session(self.model.engine) as session:
                products = session.exec(select(Product).where(Product.estoque > 0)).all()
                targets = [product.id for product in products if product.id is not None]

        for product_id in targets:
            self.evaluate_discount(product_id)


class ConsumerAgent(CompatAgent):
    """Simulates a consumer archetype with distinct purchase preferences."""

    def __init__(self, unique_id, model, profile: ConsumerProfile):
        super().__init__(unique_id, model)
        self.profile = profile

    def _score_product(self, product: Product) -> float:
        discount_ratio = 0.0
        if product.preco_atual < product.preco_original:
            discount_ratio = 1.0 - (product.preco_atual / max(product.preco_original, 0.01))

        freshness = 1.0 / max(product.rsl + 1, 1)
        category_bias = self.profile.category_preferences.get(product.categoria, 1.0)
        price_signal = max(0.15, 1.0 - (product.preco_atual / max(product.preco_original, 0.01)))
        day_multiplier = self.model.daily_demand_multiplier() if hasattr(self.model, "daily_demand_multiplier") else 1.0

        score = self.profile.base_purchase_probability
        score += discount_ratio * (self.profile.discount_sensitivity + 0.55)
        score += freshness * 0.20
        score += price_signal * 0.20
        score += self.profile.impulse
        if discount_ratio > 0.50:
            score *= 2.5
        elif discount_ratio > 0.30:
            score *= 1.8
        elif discount_ratio > 0.15:
            score *= 1.2
        score *= day_multiplier
        score *= category_bias
        return max(0.01, score)

    def step(self):
        with Session(self.model.engine) as session:
            products = session.exec(select(Product).where(Product.estoque > 0)).all()
            if not products:
                return

            weights = [self._score_product(product) for product in products]
            buy_probability = min(0.95, sum(weights) / len(weights))

            if self.model.rng.random() >= buy_probability:
                return

            product = self.model.rng.choices(products, weights=weights, k=1)[0]
            product.estoque -= 1
            self.model.record_sale(product)
            session.add(product)
            session.commit()


def build_consumer_profiles() -> list[ConsumerProfile]:
    """Return the default set of heterogeneous consumer archetypes."""

    return [
        ConsumerProfile(
            name="economico",
            base_purchase_probability=0.22,
            discount_sensitivity=1.10,
            category_preferences={"padaria": 1.05, "perecivel": 1.20, "saudavel": 1.10},
        ),
        ConsumerProfile(
            name="tradicional",
            base_purchase_probability=0.18,
            discount_sensitivity=0.60,
            category_preferences={"padaria": 1.00, "perecivel": 1.00, "saudavel": 1.00},
        ),
        ConsumerProfile(
            name="premium",
            base_purchase_probability=0.20,
            discount_sensitivity=0.30,
            category_preferences={"padaria": 0.90, "perecivel": 0.95, "saudavel": 1.05},
        ),
        ConsumerProfile(
            name="saudavel",
            base_purchase_probability=0.19,
            discount_sensitivity=0.55,
            category_preferences={"padaria": 0.85, "perecivel": 0.95, "saudavel": 1.40},
        ),
        ConsumerProfile(
            name="impulsivo",
            base_purchase_probability=0.16,
            discount_sensitivity=0.45,
            category_preferences={"padaria": 1.10, "perecivel": 1.05, "saudavel": 0.95},
            impulse=0.18,
        ),
    ]
