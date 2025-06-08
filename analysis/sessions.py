# Session logic (Killzones)

import pytz
from datetime import datetime, time

def get_trading_session():
    """
    ICT Killzone Detection
    """
    utc_now = datetime.now(pytz.UTC)
    london_time = utc_now.astimezone(pytz.timezone('Europe/London')).time()
    
    # London Killzone: 02:00-05:00 EST (07:00-10:00 GMT)
    london_open = time(7, 0)
    london_close = time(10, 0)
    
    # New York Killzone: 07:00-10:00 EST (12:00-15:00 GMT)  
    ny_open = time(12, 0)
    ny_close = time(15, 0)
    
    if london_open <= london_time <= london_close:
        return "LONDON_KILLZONE"
    elif ny_open <= london_time <= ny_close:
        return "NY_KILLZONE"
    else:
        return "OUTSIDE_KILLZONE"

def session_bias_multiplier(session, base_bias_score):
    """
    Adjust bias strength based on ICT session concept
    """
    multipliers = {
        "LONDON_KILLZONE": 1.5,  # Higher probability
        "NY_KILLZONE": 1.3,     # Good probability  
        "OUTSIDE_KILLZONE": 0.7  # Lower probability
    }
    
    return base_bias_score * multipliers.get(session, 1.0)