import pandas as pd
import numpy as np
import pandas_ta as ta
import google.generativeai as genai
import json
import os
from sklearn.ensemble import RandomForestClassifier

class SelfImprovingAgent:
    def __init__(self, initial_capital=1000):
        self.capital = initial_capital
        self.position = 0
        self.risk_per_trade = 0.01 # ریسک کمتر برای پایداری بیشتر
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.is_trained = False
        
    def prepare_features(self, df):
        # شاخص‌های تکنیکال پیشرفته
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['ADX'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # تفاوت قیمت با میانگین‌ها
        df['EMA_diff'] = (df['close'] - ta.ema(df['close'], length=20)) / df['close']
        
        # هدف برای یادگیری ماشین: آیا در ۱۰ کندل آینده قیمت ۵ درصد رشد میکند؟
        df['target'] = (df['close'].shift(-10) > df['close'] * 1.02).astype(int)
        return df.dropna()

    def train_model(self, df):
        features = ['RSI', 'ADX', 'EMA_diff']
        X = df[features]
        y = df['target']
        # تقسیم داده به آموزش و تست (ساده)
        split = int(len(df) * 0.8)
        self.model.fit(X.iloc[:split], y.iloc[:split])
        self.is_trained = True
        print("Model trained on historical data.")

    def decide(self, row):
        if not self.is_trained:
            return 'HOLD'
            
        # پیش‌بینی مدل ML
        features = np.array([[row['RSI'], row['ADX'], row['EMA_diff']]])
        ml_conf = self.model.predict_proba(features)[0][1]
        
        # استراتژی اصلاح شده: خرید فقط در زمان قدرت روند و تایید ML
        if ml_conf > 0.6 and row['ADX'] > 25:
            return 'BUY'
        elif row['RSI'] > 70 or (self.position == 1 and row['close'] < row['EMA_diff']):
            return 'SELL'
        return 'HOLD'

    def run(self, csv_path):
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().lower() for c in df.columns]
        df = self.prepare_features(df)
        
        # مرحله ۱: یادگیری از داده‌های گذشته
        self.train_model(df)
        
        # مرحله ۲: اجرای زنده (بک‌تست روی کل بازه برای مشاهده قدرت اصلاح)
        current_capital = self.capital
        trades = []
        equity = []
        
        for i in range(len(df)):
            row = df.iloc[i]
            decision = self.decide(row)
            
            if decision == 'BUY' and self.position == 0:
                self.position = 1
                entry_price = row['close']
                trades.append({'type': 'BUY', 'price': entry_price})
            elif decision == 'SELL' and self.position == 1:
                self.position = 0
                exit_price = row['close']
                profit = (exit_price - trades[-1]['price']) / trades[-1]['price']
                # کسر کارمزد صرافی (فرضی ۰.۱ درصد)
                current_capital *= (1 + profit - 0.002)
                trades.append({'type': 'SELL', 'price': exit_price, 'profit': profit})
            
            equity.append(current_capital)
            
        final_return = ((current_capital - self.capital) / self.capital) * 100
        return final_return, len(trades)

# اجرای نسخه اصلاح شده
agent = SelfImprovingAgent()
final_ret, trade_count = agent.run('data/cache/BTC_USDT_1h_365d.csv')
print(f"Final Return with ML: {final_ret:.2f}%")
print(f"Total Trades: {trade_count}")

