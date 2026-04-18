import json
import logging
from pathlib import Path
from typing import Optional

from tools.fault_injection import call_with_retry

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"

def _load_json(filename: str) -> list:
    with open(_DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

# Module-level data loaded once at startup
_customers: list = []
_orders: list = []
_products: list = []

def init_data():
    global _customers, _orders, _products
    _customers = _load_json("customers.json")
    _orders = _load_json("orders.json")
    _products = _load_json("products.json")


async def get_customer(email: str, state: dict) -> Optional[dict]:
    async def _lookup():
        for c in _customers:
            if c.get("email", "").lower() == email.lower():
                return dict(c)
        return None

    # Patch tool_call input before retry wrapper logs it
    result = await call_with_retry("get_customer", _lookup, state)
    # Stamp input on the last tool_call entry for this tool
    for entry in reversed(state["tool_calls"]):
        if entry["tool"] == "get_customer" and entry.get("input") == {}:
            entry["input"] = {"email": email}
            break
    return result


async def get_order(order_id: str, state: dict) -> Optional[dict]:
    async def _lookup():
        for o in _orders:
            if o.get("order_id") == order_id:
                return dict(o)
        return None

    result = await call_with_retry("get_order", _lookup, state)
    for entry in reversed(state["tool_calls"]):
        if entry["tool"] == "get_order" and entry.get("input") == {}:
            entry["input"] = {"order_id": order_id}
            break
    return result


async def get_product(product_id: str, state: dict) -> Optional[dict]:
    async def _lookup():
        for p in _products:
            if p.get("product_id") == product_id:
                return dict(p)
        return None

    result = await call_with_retry("get_product", _lookup, state)
    for entry in reversed(state["tool_calls"]):
        if entry["tool"] == "get_product" and entry.get("input") == {}:
            entry["input"] = {"product_id": product_id}
            break
    return result


def get_orders_for_customer(customer_id: str) -> list:
    """Utility: get all orders for a customer by ID (used internally)."""
    return [o for o in _orders if o.get("customer_id") == customer_id]
