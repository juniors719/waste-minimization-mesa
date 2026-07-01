"""Command line entry point for the simulation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .model import RetailModel, run_scenario, summarize_metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the waste minimization simulation.")
    parser.add_argument("--days", type=int, default=10, help="Number of simulated days.")
    parser.add_argument("--consumers", type=int, default=80, help="Number of consumer agents.")
    parser.add_argument(
        "--restock-strategy",
        choices=("fixed", "demand"),
        default="demand",
        help="How the supplier decides replenishment.",
    )
    parser.add_argument(
        "--restock-interval",
        type=int,
        default=5,
        help="Days between supplier reviews.",
    )
    parser.add_argument(
        "--restock-threshold",
        type=int,
        default=15,
        help="Total stock level that triggers demand-based replenishment.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run the control and discounted scenarios side by side.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for reproducible comparisons.",
    )
    return parser


def _db_url_for(name: str) -> str:
    path = Path.cwd() / f"{name}.db"
    return f"sqlite:///{path.as_posix()}"


def _print_summary(title: str, summary: dict[str, float | int]) -> None:
    print(title)
    print(
        "  "
        f"stock_final={summary['total_stock']} "
        f"vendidos={summary['sold_units']} "
        f"receita={summary['revenue']:.2f} "
        f"desperdicio_unidades={summary['waste_units']} "
        f"desperdicio_valor={summary['waste_value']:.2f} "
        f"lucro={summary['profit']:.2f} "
        f"margem={summary['margin']:.4f}"
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.compare:
        control = run_scenario(
            name="sem_desconto",
            days=args.days,
            db_url=_db_url_for("sem_desconto"),
            num_consumers=args.consumers,
            pricing_enabled=False,
            restock_strategy=args.restock_strategy,
            restock_interval=args.restock_interval,
            restock_threshold=args.restock_threshold,
            seed=args.seed,
        )
        discounted = run_scenario(
            name="com_desconto",
            days=args.days,
            db_url=_db_url_for("com_desconto"),
            num_consumers=args.consumers,
            pricing_enabled=True,
            fallback_pricing_enabled=True,
            minimum_margin=0.08,
            rsl_reference=8,
            restock_strategy=args.restock_strategy,
            restock_interval=args.restock_interval,
            restock_threshold=args.restock_threshold,
            seed=args.seed,
        )

        print("tick | estoque_control | estoque_desconto | receita_control | receita_desconto | lucro_control | lucro_desconto")
        for control_item, discount_item in zip(control.metrics, discounted.metrics):
            print(
                f"{control_item.tick:>4} | "
                f"{control_item.total_stock:>15} | "
                f"{discount_item.total_stock:>16} | "
                f"{control_item.revenue:>14.2f} | "
                f"{discount_item.revenue:>15.2f} | "
                f"{control_item.profit:>12.2f} | "
                f"{discount_item.profit:>13.2f}"
            )

        print()
        _print_summary("Cenário sem desconto", summarize_metrics(control.metrics))
        _print_summary("Cenário com desconto", summarize_metrics(discounted.metrics))
        return 0

    model = RetailModel(
        db_url=_db_url_for("varejo_simulacao"),
        num_consumers=args.consumers,
        restock_strategy=args.restock_strategy,
        restock_interval=args.restock_interval,
        restock_threshold=args.restock_threshold,
        seed=args.seed,
    )
    metrics = model.run(days=args.days)

    for item in metrics:
        print(
            f"tick={item.tick} total_stock={item.total_stock} expired_items={item.expired_items} "
            f"sold_units={item.sold_units} revenue={item.revenue:.2f} waste_units={item.waste_units} "
            f"waste_value={item.waste_value:.2f} profit={item.profit:.2f} margin={item.margin:.4f}"
        )

    print()
    _print_summary("Resumo", summarize_metrics(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
