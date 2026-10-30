USD_PER_MILLION_TOKENS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}

FALLBACK = {"input": 2.50, "output": 10.00}



def rates_for(model: str) -> dict:
    if model.startswith("ollama:"):
        return {"input": 0.0, "output": 0.0}
    if model in USD_PER_MILLION_TOKENS:
        return USD_PER_MILLION_TOKENS[model]
    matches = [name for name in USD_PER_MILLION_TOKENS if model.startswith(name)]
    if matches:
        return USD_PER_MILLION_TOKENS[max(matches, key=len)]
    return FALLBACK


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = rates_for(model)
    return round(
        input_tokens / 1_000_000 * rates["input"]
        + output_tokens / 1_000_000 * rates["output"],
        6,
    )
