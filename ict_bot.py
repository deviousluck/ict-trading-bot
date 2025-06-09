# Main entry point for the ICT Trading Bot

import requests
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os

config = {
    "api_keys": {
        "twelve_data": os.getenv("TWELVE_DATA_API"),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "screenshot_api": os.getenv("SCREENSHOT_API")
    },
    "notifications": {
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        "email_to": os.getenv("EMAIL_TO"),
        "email_from": os.getenv("EMAIL_FROM"),
        "email_password": os.getenv("EMAIL_PASSWORD")
    },
}


TELEGRAM_COMMANDS = {
    '/analyze': 'Run ICT Analysis Now',
    '/status': 'Show Bot Status', 
    '/settings': 'View Current Settings',
    '/help': 'Show Available Commands'
}

class ICTTradingBot:
    async def handle_telegram_command(self, command):
        if command == '/analyze':
            await self.run_analysis(SYMBOLS)
        elif command == '/status':
            status_msg = f"🤖 ICT Bot Status: Online\n📊 Symbols: {', '.join(SYMBOLS)}\n⏰ Last Run: {self.last_run_time}"
            await self.send_telegram_message(status_msg)

    def __init__(self, config):
        self.config = config
        self.api_key = config['twelve_data_api']
        self.telegram_token = config['telegram_bot_token']
        self.chat_id = config['telegram_chat_id']
        
    async def fetch_market_data(self, symbol, interval, outputsize=100):
        """
        Fetch OHLC data from TwelveData (Free: 800 calls/day)
        """
        url = f"https://api.twelvedata.com/time_series"
        params = {
            'symbol': symbol,
            'interval': interval,
            'outputsize': outputsize,
            'apikey': self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if 'values' not in data:
                    return None
                    
                df = pd.DataFrame(data['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
                
                # Convert to numeric
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = pd.to_numeric(df[col])
                    
                return df.sort_index()
    
    def detect_liquidity_zones(self, df, lookback=20):
        """
        ICT Liquidity Detection - Previous Day High/Low, Weekly Levels
        """
        zones = []
        
        # Previous Day High/Low (PDH/PDL)
        if len(df) > 24:  # Assuming H1 data
            prev_day_high = df['high'][-48:-24].max()  # Previous 24H
            prev_day_low = df['low'][-48:-24].min()
            
            zones.extend([
                {'type': 'PDH', 'level': prev_day_high, 'strength': 'high'},
                {'type': 'PDL', 'level': prev_day_low, 'strength': 'high'}
            ])
        
        # Weekly High/Low (if available)
        if len(df) > 168:  # 1 week of H1 data
            weekly_high = df['high'][-168:].max()
            weekly_low = df['low'][-168:].min()
            
            zones.extend([
                {'type': 'Weekly_High', 'level': weekly_high, 'strength': 'very_high'},
                {'type': 'Weekly_Low', 'level': weekly_low, 'strength': 'very_high'}
            ])
            
        return zones
    
    def calculate_comprehensive_bias(self, daily_df, h4_df, h1_df):
        """
        Comprehensive ICT Bias Calculation
        """
        bias_factors = {
            'structure_score': 0,
            'liquidity_score': 0, 
            'session_score': 0,
            'momentum_score': 0
        }
        
        signals = []
        
        # 1. Market Structure Analysis
        daily_structure = detect_market_structure(
            daily_df['high'].values, 
            daily_df['low'].values, 
            daily_df['close'].values
        )
        
        if daily_structure['trend'] == 'bullish':
            bias_factors['structure_score'] += 4
            signals.append("📈 D1: Bullish Market Structure")
        elif daily_structure['trend'] == 'bearish':
            bias_factors['structure_score'] -= 4
            signals.append("📉 D1: Bearish Market Structure")
            
        # 2. Liquidity Zone Analysis
        h1_zones = self.detect_liquidity_zones(h1_df)
        current_price = h1_df['close'].iloc[-1]
        
        nearby_zones = [z for z in h1_zones 
                       if abs(z['level'] - current_price) / current_price < 0.005]  # 0.5%
        
        for zone in nearby_zones:
            if zone['type'] in ['PDH', 'Weekly_High'] and current_price < zone['level']:
                bias_factors['liquidity_score'] -= 1  # Resistance above
                signals.append(f"🔴 {zone['type']} Resistance: {zone['level']:.5f}")
            elif zone['type'] in ['PDL', 'Weekly_Low'] and current_price > zone['level']:
                bias_factors['liquidity_score'] += 1  # Support below
                signals.append(f"🟢 {zone['type']} Support: {zone['level']:.5f}")
        
        # 3. Session Analysis
        current_session = get_trading_session()
        session_multiplier = session_bias_multiplier(current_session, 1)
        
        if current_session in ["LONDON_KILLZONE", "NY_KILLZONE"]:
            bias_factors['session_score'] += 1
            signals.append(f"⏰ Active Session: {current_session}")
        
        # 4. Momentum Analysis (RSI-like)
        h1_closes = h1_df['close'].values[-14:]  # Last 14 periods
        price_changes = np.diff(h1_closes)
        avg_gain = np.mean([x for x in price_changes if x > 0] or [0])
        avg_loss = abs(np.mean([x for x in price_changes if x < 0] or [0]))
        
        if avg_loss == 0:
            momentum_score = 2
        else:
            rs = avg_gain / avg_loss
            rsi_like = 100 - (100 / (1 + rs))
            
            if rsi_like > 70:
                bias_factors['momentum_score'] -= 1
                signals.append("⚠️ Momentum: Overbought")
            elif rsi_like < 30:
                bias_factors['momentum_score'] += 1
                signals.append("🚀 Momentum: Oversold")
        
        # Calculate Final Bias
        total_score = sum(bias_factors.values()) * session_multiplier
        
        if total_score >= 3:
            final_bias = "BULLISH"
            bias_emoji = "🟢"
        elif total_score <= -3:
            final_bias = "BEARISH" 
            bias_emoji = "🔴"
        else:
            final_bias = "NEUTRAL"
            bias_emoji = "🟡"
            
        return {
            'bias': final_bias,
            'score': total_score,
            'factors': bias_factors,
            'signals': signals,
            'emoji': bias_emoji,
            'session': current_session
        }
    
    async def send_telegram_message(self, message):
        """
        Send formatted message to Telegram
        """
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                return await response.json()
    
    def format_bias_message(self, symbol, bias_result, current_price):
        """
        Format ICT Bias Message for Telegram
        """
        message = f"""
<b>🎯 ICT BIAS ALERT - {symbol}</b>

{bias_result['emoji']} <b>BIAS: {bias_result['bias']}</b>
💰 <b>Price:</b> {current_price:.5f}
📊 <b>Score:</b> {bias_result['score']:.1f}
⏰ <b>Session:</b> {bias_result['session']}

<b>📈 Analysis:</b>
{chr(10).join(bias_result['signals'])}

<b>🔍 Bias Breakdown:</b>
- Structure: {bias_result['factors']['structure_score']}  
- Liquidity: {bias_result['factors']['liquidity_score']}
- Session: {bias_result['factors']['session_score']}
- Momentum: {bias_result['factors']['momentum_score']}

<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>
        """
        
        return message.strip()
    
    async def analyze_symbol(self, symbol):
        """
        Complete Analysis Pipeline for One Symbol
        """
        try:
            # Fetch multi-timeframe data
            print(f"📊 Analyzing {symbol}...")
            
            daily_data = await self.fetch_market_data(symbol, '1day', 30)
            h4_data = await self.fetch_market_data(symbol, '4h', 100) 
            h1_data = await self.fetch_market_data(symbol, '1h', 200)
            
            if not all([daily_data is not None, h4_data is not None, h1_data is not None]):
                print(f"❌ Failed to fetch data for {symbol}")
                return None
            
            # Run ICT Analysis
            bias_result = self.calculate_comprehensive_bias(daily_data, h4_data, h1_data)
            current_price = h1_data['close'].iloc[-1]
            
            # Format and send message
            message = self.format_bias_message(symbol, bias_result, current_price)
            await self.send_telegram_message(message)
            
            print(f"✅ {symbol}: {bias_result['bias']} (Score: {bias_result['score']})")
            
            return bias_result
            
        except Exception as e:
            error_msg = f"❌ Error analyzing {symbol}: {str(e)}"
            print(error_msg)
            await self.send_telegram_message(error_msg)
            return None
    
    async def run_analysis(self, symbols):
        """
        Run analysis on multiple symbols
        """
        print("🚀 Starting ICT Analysis...")
        
        start_message = f"""
<b>🤖 ICT Trading Bot Started</b>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
📊 <b>Analyzing:</b> {', '.join(symbols)}
⚡ <b>Method:</b> ICT 2022 Multi-Timeframe Analysis

<i>Fetching data and calculating bias...</i>
        """
        
        await self.send_telegram_message(start_message.strip())
        
        results = {}
        for symbol in symbols:
            result = await self.analyze_symbol(symbol)
            if result:
                results[symbol] = result
            
            # Rate limiting (Free API: 8 calls/minute)
            await asyncio.sleep(8)
        
        # Summary message
        summary_lines = [f"• {sym}: {res['bias']} ({res['score']:.1f})" 
                        for sym, res in results.items()]
        
        summary_message = f"""
<b>📋 ANALYSIS COMPLETE</b>

{chr(10).join(summary_lines)}

<i>Next analysis in 4 hours or send /analyze</i>
        """
        
        await self.send_telegram_message(summary_message.strip())
        
        return results

# Configuration
config = {
    'twelve_data_api': 'YOUR_TWELVEDATA_API_KEY',  # Free: twelvedata.com
    'telegram_bot_token': 'YOUR_TELEGRAM_BOT_TOKEN',
    'telegram_chat_id': 'YOUR_CHAT_ID'
}

# Trading pairs to analyze
SYMBOLS = ['GBPUSD', 'EURUSD', 'USDJPY', 'AUDUSD']

# Initialize and run
async def main():
    bot = ICTTradingBot(config)
    await bot.run_analysis(SYMBOLS)

if __name__ == "__main__":
    asyncio.run(main())