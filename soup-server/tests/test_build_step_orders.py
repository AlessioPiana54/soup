"""
------------------------------------------------------------------------
File : test_build_step_orders.py
Description: The EKG build pipeline sorts its steps by `order`: the steps
             of the ekg package (100-500) and every step the default
             packages contribute to "ekg.build_steps" (causal_df 450,
             ocel 420) have distinct orders, so their sequence never
             depends on the loading order of the packages.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.packages import bundled_module

steps = bundled_module("ekg", "steps")


def test_every_build_step_of_the_default_packages_has_its_own_order():
    engine = build_engine(Settings.from_env({}))
    contributed = engine.ctx.contributions("ekg.build_steps")

    every = [(step.key, step.order) for step in (*steps.core_steps(), *contributed)]
    orders = [order for _key, order in every]

    assert {key for key, _order in every} >= {"correlation", "causal_directly_follows", "ocel_relationships"}
    assert len(orders) == len(set(orders)), sorted(every, key=lambda item: item[1])
