"""
Cost Calculator Utility

Calculates estimated costs for OpenAI API usage based on token counts.
"""

# OpenAI Pricing (as of late 2024)
# These are approximations - actual pricing may vary
PRICING = {
    "gpt-4": {
        "prompt": 0.03 / 1000,      # $0.03 per 1K prompt tokens
        "completion": 0.06 / 1000   # $0.06 per 1K completion tokens
    },
    "gpt-4-turbo": {
        "prompt": 0.01 / 1000,
        "completion": 0.03 / 1000
    },
    "gpt-4o": {
        "prompt": 0.005 / 1000,
        "completion": 0.015 / 1000
    },
    "gpt-4o-mini": {
        "prompt": 0.00015 / 1000,   # $0.15 per 1M tokens
        "completion": 0.0006 / 1000  # $0.60 per 1M tokens
    },
    "gpt-3.5-turbo": {
        "prompt": 0.0005 / 1000,
        "completion": 0.0015 / 1000
    }
}


def calculate_cost(
    total_tokens: int,
    model: str = "gpt-4o-mini",
    prompt_tokens: int = None,
    completion_tokens: int = None
) -> float:
    """
    Calculate cost based on OpenAI pricing.
    
    Args:
        total_tokens: Total tokens used (prompt + completion)
        model: Model name (default: gpt-4o-mini)
        prompt_tokens: Optional prompt tokens (if known)
        completion_tokens: Optional completion tokens (if known)
    
    Returns:
        Estimated cost in USD
    """
    if model not in PRICING:
        # Default to gpt-4o-mini pricing if unknown model
        model = "gpt-4o-mini"
    
    pricing = PRICING[model]
    
    if prompt_tokens is not None and completion_tokens is not None:
        # Use specific token counts if available
        cost = (prompt_tokens * pricing["prompt"]) + (completion_tokens * pricing["completion"])
    else:
        # Estimate using average (assume 30% prompt, 70% completion)
        estimated_prompt = int(total_tokens * 0.3)
        estimated_completion = total_tokens - estimated_prompt
        cost = (estimated_prompt * pricing["prompt"]) + (estimated_completion * pricing["completion"])
    
    return round(cost, 6)


def get_model_pricing(model: str = "gpt-4o-mini") -> dict:
    """
    Get pricing information for a model.
    
    Args:
        model: Model name
    
    Returns:
        Dictionary with prompt and completion pricing
    """
    return PRICING.get(model, PRICING["gpt-4o-mini"])
