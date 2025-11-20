def account_id_to_name() -> dict:
    return {
        "U4297056": "undergrad",
        "U12702120": "quant",
        "U10797691": "brigham_capital",
        "U12702064": "grad",
        "DU8843649": "quant_paper"
    }


def get_account_id_from_name(name: str) -> str:
    account_map = {
        "undergrad": "U4297056",
        "quant": "U12702120",
        "brigham_capital": "U10797691",
        "grad": "U12702064",
        "quant_paper": "DU8843649"
    }

    if name in account_map:
        return account_map[name]
    else:
        raise ValueError(f"Name not supported: {name}")
