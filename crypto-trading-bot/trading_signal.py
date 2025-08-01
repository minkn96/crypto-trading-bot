# trading_signal.py - 메인 알림 스크립트
import requests
import numpy as np
import time
from datetime import datetime
import os

class TradingSignalBot:
    def __init__(self):
        # 텔레그램 봇 정보 (GitHub Secrets에서 가져오기)
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '8092280367:AAH3Do1RM4XsmV1JLJEiENfyIWpS4AjB2r8')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '1718223270')
        
        # 바이낸스 API
        self.binance_api = 'https://api.binance.com/api/v3'
        
        # 모니터링할 코인들 (여러 개 추가 가능)
        self.coins = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'LINKUSDT']
        self.timeframe = '15m'
        
        print(f"🚀 트레이딩 봇 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def get_market_data(self, symbol):
        """바이낸스에서 시장 데이터 가져오기"""
        try:
            # 24시간 통계
            ticker_url = f"{self.binance_api}/ticker/24hr?symbol={symbol}"
            ticker_response = requests.get(ticker_url, timeout=10)
            ticker_data = ticker_response.json()
            
            # 캔들 데이터
            klines_url = f"{self.binance_api}/klines?symbol={symbol}&interval={self.timeframe}&limit=200"
            klines_response = requests.get(klines_url, timeout=10)
            klines_data = klines_response.json()
            
            return ticker_data, klines_data
            
        except Exception as e:
            print(f"❌ {symbol} 데이터 가져오기 실패: {e}")
            return None, None

    def calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        if len(prices) < period + 1:
            return [50] * len(prices)
            
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        
        if len(gains) < period:
            return [50]
            
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        rsi_values = []
        
        for i in range(period, len(gains)):
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)
            
            # 지수 이동평균 업데이트
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        
        return rsi_values[-1] if rsi_values else 50

    def calculate_sma(self, prices, period):
        """단순 이동평균 계산"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return np.mean(prices[-period:])

    def calculate_bollinger_bands(self, prices, period=20, multiplier=2):
        """볼린저 밴드 계산"""
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return price, price, price
            
        sma = self.calculate_sma(prices, period)
        std = np.std(prices[-period:])
        
        upper = sma + (std * multiplier)
        lower = sma - (std * multiplier)
        
        return upper, lower, sma

    def analyze_signal(self, symbol, ticker_data, klines_data):
        """신호 분석"""
        try:
            # 가격 데이터 추출
            closes = [float(kline[4]) for kline in klines_data]
            volumes = [float(kline[5]) for kline in klines_data]
            
            current_price = float(ticker_data['lastPrice'])
            price_change_percent = float(ticker_data['priceChangePercent'])
            
            # 기술적 지표 계산
            rsi = self.calculate_rsi(closes)
            ma20 = self.calculate_sma(closes, 20)
            ma50 = self.calculate_sma(closes, 50)
            bb_upper, bb_lower, bb_middle = self.calculate_bollinger_bands(closes)
            
            # 거래량 비율
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 신호 체크
            signals = []
            
            # 슈퍼 시그널 체크
            super_conditions = [
                current_price <= bb_lower and rsi < 25,
                volume_ratio > 3.0,
                ma20 > ma50,
                price_change_percent < -15
            ]
            
            if sum(super_conditions) == 4:
                signals.append({
                    'type': '👑 슈퍼 시그널',
                    'confidence': '95%+',
                    'expected_return': '+15~30% (단기)',
                    'conditions_met': '4/4'
                })
            
            # 강력한 매수 신호
            strong_buy_conditions = [
                current_price <= bb_lower * 1.02 and 20 <= rsi <= 35,
                volume_ratio > 2.0,
                abs(current_price - ma20) / ma20 < 0.05,
                rsi < 40  # 반등 신호 대신 간단한 조건
            ]
            
            if sum(strong_buy_conditions) == 4:
                signals.append({
                    'type': '🟢 강력한 매수 신호',
                    'confidence': '85%',
                    'expected_return': '+8~20% (단기)',
                    'conditions_met': '4/4'
                })
            
            # 강력한 매도 신호
            strong_sell_conditions = [
                current_price >= bb_upper and rsi > 75,
                volume_ratio > 1.8,
                rsi > 70,  # 연속 양봉 대신 간단한 조건
                current_price > ma20 * 1.1
            ]
            
            if sum(strong_sell_conditions) == 4:
                signals.append({
                    'type': '🔴 강력한 매도 신호',
                    'confidence': '80%',
                    'expected_return': '+10~20% (숏)',
                    'conditions_met': '4/4'
                })
            
            # 황금십자
            golden_cross_conditions = [
                ma20 > ma50,
                45 <= rsi <= 65,
                volume_ratio > 1.0,
                current_price > ma20  # 고점 돌파 대신
            ]
            
            if sum(golden_cross_conditions) == 4:
                signals.append({
                    'type': '⭐ 황금십자 + 추세전환',
                    'confidence': '75%',
                    'expected_return': '+15~40% (중기)',
                    'conditions_met': '4/4'
                })
            
            return signals, {
                'current_price': current_price,
                'rsi': rsi,
                'volume_ratio': volume_ratio,
                'price_change_percent': price_change_percent,
                'ma20': ma20,
                'ma50': ma50,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower
            }
            
        except Exception as e:
            print(f"❌ {symbol} 신호 분석 실패: {e}")
            return [], {}

    def send_telegram_message(self, message):
        """텔레그램 메시지 전송"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                print("✅ 텔레그램 알림 전송 성공")
                return True
            else:
                print(f"❌ 텔레그램 전송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 텔레그램 전송 오류: {e}")
            return False

    def run_analysis(self):
        """전체 분석 실행"""
        total_signals = 0
        
        for symbol in self.coins:
            print(f"🔍 {symbol} 분석 중...")
            
            ticker_data, klines_data = self.get_market_data(symbol)
            
            if not ticker_data or not klines_data:
                continue
                
            signals, market_info = self.analyze_signal(symbol, ticker_data, klines_data)
            
            if signals:
                total_signals += len(signals)
                
                for signal in signals:
                    message = f"""
🚨 *최적 거래 신호 발생!* 🚨

📊 *코인:* {symbol.replace('USDT', '')}/USDT
💰 *현재가:* ${market_info['current_price']:,.2f}
🎯 *신호:* {signal['type']}
📈 *RSI:* {market_info['rsi']:.1f}
📊 *거래량 비율:* {market_info['volume_ratio']:.1f}x
📉 *24시간 변동:* {market_info['price_change_percent']:+.2f}%

✨ *신뢰도:* {signal['confidence']}
💎 *예상 수익:* {signal['expected_return']}
✅ *조건 만족:* {signal['conditions_met']}

⏰ *시간:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ *주의:* 이 신호는 참고용이며, 투자는 신중히 결정하세요!

🤖 *GitHub Actions 자동 알림*
                    """.strip()
                    
                    self.send_telegram_message(message)
                    time.sleep(1)  # 텔레그램 API 제한 방지
        
        # 실행 완료 로그
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if total_signals > 0:
            print(f"🎯 {current_time}: {total_signals}개 신호 발견 및 전송 완료")
        else:
            print(f"⏳ {current_time}: 신호 없음 - 모니터링 계속...")

if __name__ == "__main__":
    bot = TradingSignalBot()
    bot.run_analysis()