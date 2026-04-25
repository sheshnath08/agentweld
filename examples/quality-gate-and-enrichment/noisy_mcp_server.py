"""Noisy stdio MCP server used to demonstrate AgentWeld quality gates."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agentweld-noisy-demo")


@mcp.tool()
def get(customer_id: str) -> dict[str, str]:
    """Gets."""
    return {"customer_id": customer_id, "name": "Example Customer"}


@mcp.tool()
def post(payload: str) -> str:
    return f"accepted:{payload[:24]}"


@mcp.tool()
def list_customer_orders(customer_id: str, status: str = "open") -> list[dict[str, str]]:
    """List customer orders by status.

    Returns an empty list when no orders are found and raises an invalid status
    error for unsupported statuses.
    """
    allowed = {"open", "paid", "cancelled"}
    if status not in allowed:
        raise ValueError(f"invalid status: {status}")
    return [
        {
            "order_id": "ord_1001",
            "customer_id": customer_id,
            "status": status,
            "total": "49.00",
        }
    ]


@mcp.tool()
def send_invoice_reminder(invoice_id: str, email: str, dry_run: bool = True) -> dict[str, str]:
    """Prepare an invoice reminder message.

    Fails when the invoice id is invalid or email is unavailable.
    """
    if not invoice_id.startswith("inv_"):
        raise ValueError("invalid invoice id")
    return {
        "invoice_id": invoice_id,
        "email": email,
        "mode": "dry_run" if dry_run else "send",
        "status": "prepared",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
