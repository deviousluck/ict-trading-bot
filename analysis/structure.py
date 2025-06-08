# Market structure and FVG detection

def detect_market_structure(highs, lows, closes):
    """
    ICT Market Structure Analysis
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Internal Structure
    """
    structure = {
        'trend': 'neutral',
        'bos_detected': False,
        'choch_detected': False,
        'internal_liquidity': []
    }
    
    # Higher High/Lower Low detection
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    prev_high = max(highs[-40:-20])
    prev_low = min(lows[-40:-20])
    
    # BOS Detection (Bullish)
    if recent_high > prev_high and closes[-1] > recent_high * 0.995:
        structure['bos_detected'] = True
        structure['trend'] = 'bullish'
    
    # BOS Detection (Bearish)  
    if recent_low < prev_low and closes[-1] < recent_low * 1.005:
        structure['bos_detected'] = True
        structure['trend'] = 'bearish'
        
    return structure

def detect_fair_value_gaps(opens, highs, lows, closes):
    """
    Fair Value Gap Detection (ICT PD Array)
    """
    fvgs = []
    
    for i in range(2, len(closes)):
        # Bullish FVG: Gap between candle[i-2].low and candle[i].high
        if lows[i-2] > highs[i] and closes[i-1] > opens[i-1]:
            fvgs.append({
                'type': 'bullish_fvg',
                'top': lows[i-2],
                'bottom': highs[i],
                'index': i
            })
        
        # Bearish FVG: Gap between candle[i-2].high and candle[i].low  
        if highs[i-2] < lows[i] and closes[i-1] < opens[i-1]:
            fvgs.append({
                'type': 'bearish_fvg',
                'top': lows[i],
                'bottom': highs[i-2],
                'index': i
            })
    
    return fvgs[-5:]  # Last 5 FVGs

def calculate_ict_bias(daily_data, h4_data, h1_data):
    """
    ICT 2022 Multi-Timeframe Bias Calculation
    """
    bias_score = 0
    signals = []
    
    # Daily Bias (Highest weight)
    daily_structure = detect_market_structure(
        daily_data['high'], daily_data['low'], daily_data['close']
    )
    
    if daily_structure['trend'] == 'bullish':
        bias_score += 3
        signals.append("D1: Bullish Structure")
    elif daily_structure['trend'] == 'bearish':
        bias_score -= 3
        signals.append("D1: Bearish Structure")
    
    # H4 Confirmation
    h4_structure = detect_market_structure(
        h4_data['high'], h4_data['low'], h4_data['close']
    )
    
    if h4_structure['trend'] == 'bullish':
        bias_score += 2
        signals.append("H4: Bullish Confirmation")
    elif h4_structure['trend'] == 'bearish':
        bias_score -= 2
        signals.append("H4: Bearish Confirmation")
    
    # H1 Entry Refinement
    h1_fvgs = detect_fair_value_gaps(
        h1_data['open'], h1_data['high'], h1_data['low'], h1_data['close']
    )
    
    bullish_fvgs = len([fvg for fvg in h1_fvgs if fvg['type'] == 'bullish_fvg'])
    bearish_fvgs = len([fvg for fvg in h1_fvgs if fvg['type'] == 'bearish_fvg'])
    
    if bullish_fvgs > bearish_fvgs:
        bias_score += 1
        signals.append(f"H1: {bullish_fvgs} Bullish FVGs")
    elif bearish_fvgs > bullish_fvgs:
        bias_score -= 1
        signals.append(f"H1: {bearish_fvgs} Bearish FVGs")
    
    # Final Bias Decision
    if bias_score >= 3:
        return "BULLISH", bias_score, signals
    elif bias_score <= -3:
        return "BEARISH", bias_score, signals
    else:
        return "NEUTRAL", bias_score, signals