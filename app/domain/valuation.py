def investment_amount(investment: dict) -> float:
    """Resolve o valor da posição: saldo, quantidade X preço, amount ou zero."""
    balance = investment.get("balance")
    if balance is not None:
        return float(balance)

    quantity = investment.get("quantity")
    price = investment.get("price")
    if quantity is not None and price is not None:
        return float(quantity) * float(price)

    amount = investment.get("amount")
    return float(amount) if amount is not None else 0.0
