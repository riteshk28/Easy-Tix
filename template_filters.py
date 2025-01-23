def format_duration(minutes):
    """Format minutes into a human-readable duration."""
    if not minutes:
        return "Not set"
    
    days = minutes // 1440  # minutes in a day
    remaining_minutes = minutes % 1440
    hours = remaining_minutes // 60
    mins = remaining_minutes % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if mins > 0:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
    
    return ", ".join(parts) if parts else "0 minutes" 