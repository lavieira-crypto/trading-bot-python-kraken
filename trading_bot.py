# ============================================================================
# Want the full architecture and cloud deployment guide?
# Get the book and the complete repository at: https://forms.gle/HnGyPnvg4zsLietW7
# ============================================================================

import requests
import time
import hashlib
import hmac
import base64
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from urllib.parse import urlencode
import sys

# ============================================================================
# CONFIGURAÇÕES PRINCIPAIS
# ============================================================================
BITCOIN_PAIR = "XXBTZUSD"
CHECK_INTERVAL_MINUTES = 60
EMA_SHORT = 9
EMA_LONG = 21
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD_DEV = 2
MIN_BALANCE_USD = 10

# CONFIGURAÇÕES DE TRADING AUTOMÁTICO
TRADING_MODE = "PAPER"  # PAPER, LIVE, ANALYZE_ONLY
PAPER_TRADING_BALANCE = 1000  # Saldo inicial para paper trading
RISK_PER_TRADE = 0.05  # 5% do saldo por trade
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.04  # 4% take profit

# Configuração da API
# from google.colab import userdata
# api_key = userdata.get('API_GC_Public_Key')
# api_secret = userdata.get('API_GC_Private_Key')

import os
api_key = os.environ.get('KRAKEN_API_KEY')
api_secret = os.environ.get('KRAKEN_API_SECRET')

if not api_key or not api_secret:
    print("ERRO: API keys não configuradas!")
    print("Execute: export KRAKEN_API_KEY='sua_chave' && export KRAKEN_API_SECRET='seu_secreto'")
    exit(1)

# ============================================================================
# SISTEMA DE TRADING AUTOMÁTICO
# ============================================================================

class AutoTradingSystem:
    def __init__(self):
        self.trade_mode = TRADING_MODE
        self.paper_balance = {"USD": PAPER_TRADING_BALANCE, "BTC": 0.0}
        self.active_positions = []
        self.trade_history = []
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0

    def execute_trade(self, signal, current_price, analysis_data, real_balance):
        """Executa um trade baseado no sinal"""

        if signal == "hold":
            return {"status": "no_action", "message": "Hold signal"}

        # Obter saldo baseado no modo
        if self.trade_mode == "PAPER":
            usd_balance = self.paper_balance["USD"]
            btc_balance = self.paper_balance["BTC"]
        else:
            usd_balance = real_balance.get("ZUSD", 0) + real_balance.get("USD", 0)
            btc_balance = real_balance.get("XXBT", 0) + real_balance.get("BTC", 0)

        trade_result = {
            "id": f"trade_{int(time.time())}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": signal,
            "price": current_price,
            "status": "pending"
        }

        if signal == "buy" and usd_balance >= MIN_BALANCE_USD:
            # Calcular quanto comprar (RISK_PER_TRADE do saldo)
            amount_to_spend = usd_balance * RISK_PER_TRADE
            btc_to_buy = amount_to_spend / current_price

            trade_result.update({
                "type": "BUY",
                "amount_usd": amount_to_spend,
                "amount_btc": btc_to_buy,
                "stop_loss": current_price * (1 - STOP_LOSS_PERCENT),
                "take_profit": current_price * (1 + TAKE_PROFIT_PERCENT)
            })

            if self.trade_mode == "PAPER":
                # Paper trading - simulação
                self.paper_balance["USD"] -= amount_to_spend
                self.paper_balance["BTC"] += btc_to_buy

                self.active_positions.append({
                    "id": trade_result["id"],
                    "type": "buy",
                    "entry_price": current_price,
                    "amount_btc": btc_to_buy,
                    "amount_usd": amount_to_spend,
                    "entry_time": datetime.now(),
                    "stop_loss": current_price * (1 - STOP_LOSS_PERCENT),
                    "take_profit": current_price * (1 + TAKE_PROFIT_PERCENT)
                })

                trade_result.update({
                    "new_usd_balance": self.paper_balance["USD"],
                    "new_btc_balance": self.paper_balance["BTC"],
                    "status": "executed_paper"
                })

                print(f"\n[PAPER TRADE] ✅ COMPRA EXECUTADA")
                print(f"  Quantidade: {btc_to_buy:.8f} BTC")
                print(f"  Preço: ${current_price:,.2f}")
                print(f"  Total: ${amount_to_spend:.2f}")
                print(f"  Stop Loss: ${trade_result['stop_loss']:,.2f} (-{STOP_LOSS_PERCENT*100}%)")
                print(f"  Take Profit: ${trade_result['take_profit']:,.2f} (+{TAKE_PROFIT_PERCENT*100}%)")

            elif self.trade_mode == "LIVE":
                # Trading real (comentado por segurança)
                trade_result["status"] = "would_execute_live"
                print(f"\n[LIVE TRADE] ⚠️  SIMULAÇÃO DE COMPRA (LIVE desativado)")
                print(f"  Quantidade: {btc_to_buy:.8f} BTC")
                print(f"  Preço: ${current_price:,.2f}")
                print(f"  Total: ${amount_to_spend:.2f}")

        elif signal == "sell" and btc_balance >= 0.0001:
            # Vender posição aberta ou parte do BTC
            if self.active_positions:
                # Vender posição aberta
                position = self.active_positions[0]
                btc_to_sell = position["amount_btc"]
                usd_received = btc_to_sell * current_price

                # Calcular P&L
                pl = (current_price - position["entry_price"]) * btc_to_sell
                pl_percent = (current_price - position["entry_price"]) / position["entry_price"] * 100

                trade_result.update({
                    "type": "SELL",
                    "amount_btc": btc_to_sell,
                    "amount_usd": usd_received,
                    "entry_price": position["entry_price"],
                    "profit_loss": pl,
                    "profit_loss_percent": pl_percent
                })

                if self.trade_mode == "PAPER":
                    self.paper_balance["BTC"] -= btc_to_sell
                    self.paper_balance["USD"] += usd_received

                    self.active_positions.pop(0)
                    self.total_trades += 1

                    if pl > 0:
                        self.winning_trades += 1
                        trade_result["status"] = "win"
                    else:
                        self.losing_trades += 1
                        trade_result["status"] = "loss"

                    self.total_profit += pl

                    trade_result.update({
                        "new_usd_balance": self.paper_balance["USD"],
                        "new_btc_balance": self.paper_balance["BTC"],
                        "status": "executed_paper"
                    })

                    print(f"\n[PAPER TRADE] ✅ VENDA EXECUTADA")
                    print(f"  Quantidade: {btc_to_sell:.8f} BTC")
                    print(f"  Preço: ${current_price:,.2f}")
                    print(f"  Total: ${usd_received:.2f}")
                    print(f"  P&L: ${pl:.2f} ({pl_percent:.1f}%)")
                    print(f"  {'✅ LUCRO' if pl > 0 else '❌ PREJUÍZO'}")

                elif self.trade_mode == "LIVE":
                    trade_result["status"] = "would_execute_live"
                    print(f"\n[LIVE TRADE] ⚠️  SIMULAÇÃO DE VENDA (LIVE desativado)")

            else:
                # Vender BTC disponível (não de uma posição específica)
                btc_to_sell = btc_balance * 0.5  # Vender 50%
                usd_received = btc_to_sell * current_price

                trade_result.update({
                    "type": "SELL_BALANCE",
                    "amount_btc": btc_to_sell,
                    "amount_usd": usd_received
                })

                if self.trade_mode == "PAPER":
                    self.paper_balance["BTC"] -= btc_to_sell
                    self.paper_balance["USD"] += usd_received
                    trade_result["status"] = "executed_paper_balance"

                    print(f"\n[PAPER TRADE] ✅ VENDA DE SALDO EXECUTADA")
                    print(f"  Quantidade: {btc_to_sell:.8f} BTC")
                    print(f"  Preço: ${current_price:,.2f}")
                    print(f"  Total: ${usd_received:.2f}")

        else:
            trade_result["status"] = "insufficient_balance"
            print(f"\n[TRADE] ❌ Saldo insuficiente para {signal}")

        self.trade_history.append(trade_result)
        return trade_result

    def check_positions(self, current_price):
        """Verifica stop loss e take profit das posições abertas"""
        if not self.active_positions:
            return

        for position in self.active_positions[:]:  # Cópia para permitir remoção
            pl_percent = (current_price - position["entry_price"]) / position["entry_price"] * 100

            # Verificar STOP LOSS
            if current_price <= position["stop_loss"]:
                print(f"\n[STOP LOSS] ⚠️  Ativado para posição {position['id'][-6:]}")
                print(f"  Preço entrada: ${position['entry_price']:,.2f}")
                print(f"  Preço atual: ${current_price:,.2f}")
                print(f"  P&L: {pl_percent:.1f}%")

                # Simular venda por stop loss
                self.execute_trade("sell", current_price, None, {})
                if position in self.active_positions:
                    self.active_positions.remove(position)

            # Verificar TAKE PROFIT
            elif current_price >= position["take_profit"]:
                print(f"\n[TAKE PROFIT] ✅ Ativado para posição {position['id'][-6:]}")
                print(f"  Preço entrada: ${position['entry_price']:,.2f}")
                print(f"  Preço atual: ${current_price:,.2f}")
                print(f"  P&L: {pl_percent:.1f}%")

                # Simular venda por take profit
                self.execute_trade("sell", current_price, None, {})
                if position in self.active_positions:
                    self.active_positions.remove(position)

    def get_stats(self):
        """Retorna estatísticas de trading"""
        total_balance = self.paper_balance["USD"] + self.paper_balance["BTC"] * self.get_current_price()

        return {
            "paper_balance_usd": self.paper_balance["USD"],
            "paper_balance_btc": self.paper_balance["BTC"],
            "paper_total_balance": total_balance,
            "initial_balance": PAPER_TRADING_BALANCE,
            "total_profit": self.total_profit,
            "profit_percentage": ((total_balance - PAPER_TRADING_BALANCE) / PAPER_TRADING_BALANCE) * 100,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            "active_positions": len(self.active_positions)
        }

    def get_current_price(self):
        """Obtém preço atual para cálculos"""
        try:
            response = requests.get(
                f"https://api.kraken.com/0/public/Ticker?pair={BITCOIN_PAIR}",
                timeout=10
            ).json()

            if not response.get('error'):
                result = response.get('result', {})
                pair_data = result.get(BITCOIN_PAIR, {})
                ask = float(pair_data.get('a', [0])[0])
                bid = float(pair_data.get('b', [0])[0])
                return (ask + bid) / 2
        except:
            pass
        return 87000  # Valor padrão se falhar

    def show_trading_dashboard(self):
        """Mostra dashboard completo de trading"""
        stats = self.get_stats()

        print(f"\n{'='*60}")
        print("📊 DASHBOARD DE TRADING")
        print(f"{'='*60}")

        print(f"\n💰 SALDO PAPER:")
        print(f"  USD: ${stats['paper_balance_usd']:,.2f}")
        print(f"  BTC: {stats['paper_balance_btc']:.8f}")
        print(f"  Total: ${stats['paper_total_balance']:,.2f}")

        print(f"\n📈 PERFORMANCE:")
        print(f"  Saldo inicial: ${stats['initial_balance']:,.2f}")
        print(f"  Lucro total: ${stats['total_profit']:,.2f}")
        print(f"  Retorno: {stats['profit_percentage']:.1f}%")

        print(f"\n🎯 ESTATÍSTICAS:")
        print(f"  Trades totais: {stats['total_trades']}")
        print(f"  Trades vencedores: {stats['winning_trades']}")
        print(f"  Trades perdedores: {stats['losing_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Posições ativas: {stats['active_positions']}")

        if self.active_positions:
            print(f"\n🔄 POSIÇÕES ATIVAS:")
            for pos in self.active_positions:
                current_price = self.get_current_price()
                pl = (current_price - pos["entry_price"]) * pos["amount_btc"]
                pl_percent = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
                print(f"  ID: {pos['id'][-6:]} | Compra: ${pos['entry_price']:,.2f}")
                print(f"    Atual: ${current_price:,.2f} | P&L: ${pl:.2f} ({pl_percent:.1f}%)")
                print(f"    Stop: ${pos['stop_loss']:,.2f} | Take: ${pos['take_profit']:,.2f}")

        if self.trade_history:
            print(f"\n📝 ÚLTIMOS TRADES:")
            for trade in self.trade_history[-3:]:  # Últimos 3 trades
                print(f"  {trade['timestamp'][11:]} | {trade.get('type', 'N/A')} | ${trade['price']:,.2f}")

# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================

def log_message(message, level="INFO"):
    """Registra mensagens com timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Cores para diferentes níveis
    colors = {
        "INFO": "\033[94m",     # Azul
        "SUCCESS": "\033[92m",  # Verde
        "WARNING": "\033[93m",  # Amarelo
        "ERROR": "\033[91m",    # Vermelho
        "TRADE": "\033[95m",    # Magenta
        "RESET": "\033[0m"
    }

    color = colors.get(level, colors["INFO"])
    print(f"{color}[{timestamp}] [{level}] {message}{colors['RESET']}")

def log_separator():
    """Imprime separador visual"""
    print("=" * 80)

def log_header(title):
    """Imprime cabeçalho de seção"""
    print(f"\n{'='*40} {title} {'='*40}")

# ============================================================================
# FUNÇÕES DE AUTENTICAÇÃO E API
# ============================================================================

def get_nonce():
    """Gera um nonce baseado no timestamp atual"""
    return str(int(time.time() * 1000))

def generate_signature(url_path, data, secret):
    """Gera assinatura HMAC para autenticação"""
    post_data = urlencode(data)
    encoded = (str(data['nonce']) + post_data).encode()
    sha256_hash = hashlib.sha256(encoded).digest()
    signature = hmac.new(base64.b64decode(secret),
                        url_path.encode() + sha256_hash,
                        hashlib.sha512)
    return base64.b64encode(signature.digest()).decode()

def query_public(endpoint, params=None):
    """Consulta endpoint público da API Kraken"""
    url = f"https://api.kraken.com/0/public/{endpoint}"

    try:
        response = requests.get(url, params=params or {}, timeout=30)
        return response.json()
    except Exception as e:
        log_message(f"Erro na requisição: {e}", "ERROR")
        return {"error": [str(e)]}

def query_private(endpoint, data):
    """Consulta endpoint privado da API Kraken"""
    url = f"https://api.kraken.com/0/private/{endpoint}"
    data['nonce'] = get_nonce()

    headers = {
        'API-Key': api_key,
        'API-Sign': generate_signature(f'/0/private/{endpoint}', data, api_secret)
    }

    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        return response.json()
    except Exception as e:
        log_message(f"Erro na requisição privada: {e}", "ERROR")
        return {"error": [str(e)]}

# ============================================================================
# FUNÇÕES DE DADOS
# ============================================================================

def get_bitcoin_data_1day(pair_name, days_back=180):
    """Obtém dados diários (velas de 1 dia)"""
    params = {
        'pair': pair_name,
        'interval': 1440,  # 1 dia em minutos
    }

    response = query_public('OHLC', params)

    if response.get('error'):
        log_message(f"Erro ao obter dados: {response['error']}", "ERROR")
        return pd.DataFrame(), None

    result = response.get('result', {})

    # Encontrar a chave correta
    data_key = None
    for key in result.keys():
        if key != 'last':
            data_key = key
            break

    if not data_key or not result[data_key]:
        log_message("Nenhum dado encontrado", "ERROR")
        return pd.DataFrame(), None

    # Criar DataFrame
    df = pd.DataFrame(result[data_key], columns=[
        'timestamp', 'open', 'high', 'low', 'close',
        'vwap', 'volume', 'count'
    ])

    # Converter tipos
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    numeric_cols = ['open', 'high', 'low', 'close', 'vwap', 'volume']
    df[numeric_cols] = df[numeric_cols].astype(float)

    df.set_index('timestamp', inplace=True)
    
    # Filtrar para o número de dias desejado
    if days_back:
        end_date = df.index[-1]
        start_date = end_date - pd.Timedelta(days=days_back)
        df = df[df.index >= start_date]

    return df, 1440  # Retorna candles de 1 dia (1440 minutos)

# ============================================================================
# FUNÇÕES DE INDICADORES
# ============================================================================

def calculate_ema(df, period, column='close'):
    """Calcula Média Móvel Exponencial (EMA)"""
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_sma(df, period, column='close'):
    """Calcula Média Móvel Simples (SMA)"""
    return df[column].rolling(window=period).mean()

def calculate_rsi(df, period=RSI_PERIOD):
    """Calcula Relative Strength Index (RSI)"""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

def calculate_bollinger_bands(df, period=BB_PERIOD, std_dev=BB_STD_DEV):
    """Calcula Bandas de Bollinger"""
    sma = calculate_sma(df, period)
    std = df['close'].rolling(window=period).std()

    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)

    return upper_band, sma, lower_band

def calculate_volume_profile(df, period=20):
    """Calcula perfil de volume (Volume SMA)"""
    return df['volume'].rolling(window=period).mean()

# ============================================================================
# FUNÇÃO DE ANÁLISE COM TRADING
# ============================================================================

def analyze_bitcoin_with_trading(df, candle_interval_days, trader, real_balance):
    """Analisa Bitcoin e executa trades automáticos"""
    if df.empty or len(df) < 50:
        log_message(f"Dados insuficientes: {len(df)} candles", "WARNING")
        return "hold", {}

    # Ajustar períodos baseado no intervalo das candles
    if candle_interval_days >= 7:
        ema_short = max(3, EMA_SHORT // 2)
        ema_long = max(7, EMA_LONG // 2)
        rsi_period = max(7, RSI_PERIOD // 2)
        bb_period = max(10, BB_PERIOD // 2)
    else:
        ema_short = EMA_SHORT
        ema_long = EMA_LONG
        rsi_period = RSI_PERIOD
        bb_period = BB_PERIOD

    # Calcular todos os indicadores
    df['ema_short'] = calculate_ema(df, ema_short)
    df['ema_long'] = calculate_ema(df, ema_long)
    df['rsi'] = calculate_rsi(df, rsi_period)

    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(df, bb_period)
    df['volume_sma'] = calculate_volume_profile(df)

    # Obter valores atuais
    current_price = df['close'].iloc[-1]
    ema_short_val = df['ema_short'].iloc[-1]
    ema_long_val = df['ema_long'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    bb_upper = df['bb_upper'].iloc[-1]
    bb_lower = df['bb_lower'].iloc[-1]
    volume_current = df['volume'].iloc[-1]
    volume_avg = df['volume_sma'].iloc[-1]

    # Análise de tendência com EMAs
    ema_bullish = ema_short_val > ema_long_val
    price_above_ema = current_price > ema_short_val

    # Análise de RSI
    rsi_oversold = rsi < 50
    rsi_overbought = rsi > 50

    # Análise de Bandas de Bollinger
    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) * 100
    near_bb_lower = bb_position < 20
    near_bb_upper = bb_position > 80

    # Análise de volume
    high_volume = volume_current > volume_avg * 1.5

    # Lógica de decisão FORTE para trading
    buy_signals = 0
    sell_signals = 0

    log_message(f"\n🔍 ANÁLISE DETALHADA:", "INFO")

    # Sinais FORTES de COMPRA
    if rsi_oversold:
        buy_signals += 2
        log_message(f"  ✅ RSI OVERSOLD: {rsi:.1f} (<30)", "INFO")

    if near_bb_lower:
        buy_signals += 2
        log_message(f"  ✅ PRÓXIMO BB INFERIOR: {bb_position:.1f}% (<20%)", "INFO")

    if high_volume and rsi_oversold:
        buy_signals += 1
        log_message(f"  ✅ VOLUME ALTO COM RSI BAIXO", "INFO")

    # Cruzamento de EMAS bullish
    if len(df) > 1:
        ema_short_prev = df['ema_short'].iloc[-2]
        ema_long_prev = df['ema_long'].iloc[-2]
        if ema_short_prev <= ema_long_prev and ema_short_val > ema_long_val:
            buy_signals += 3
            log_message(f"  ✅ CRUZAMENTO BULLISH DAS EMAS", "INFO")

    # Sinais FORTES de VENDA
    if rsi_overbought:
        sell_signals += 2
        log_message(f"  ❌ RSI OVERBOUGHT: {rsi:.1f} (>70)", "INFO")

    if near_bb_upper:
        sell_signals += 2
        log_message(f"  ❌ PRÓXIMO BB SUPERIOR: {bb_position:.1f}% (>80%)", "INFO")

    # Cruzamento de EMAS bearish
    if len(df) > 1:
        ema_short_prev = df['ema_short'].iloc[-2]
        ema_long_prev = df['ema_long'].iloc[-2]
        if ema_short_prev >= ema_long_prev and ema_short_val < ema_long_val:
            sell_signals += 3
            log_message(f"  ❌ CRUZAMENTO BEARISH DAS EMAS", "INFO")

    # Tomada de decisão
    signal = "hold"

    if buy_signals >= 3:  # Limite mais alto para evitar falsos positivos
        signal = "buy"
        log_message(f"\n🎯 SINAL FORTE DE COMPRA: {buy_signals}/8 pontos", "SUCCESS")

        # Executar trade automático
        if trader:
            trade_result = trader.execute_trade(signal, current_price, None, real_balance)

    elif sell_signals >= 3:
        signal = "sell"
        log_message(f"\n🎯 SINAL FORTE DE VENDA: {sell_signals}/8 pontos", "WARNING")

        # Executar trade automático
        if trader:
            trade_result = trader.execute_trade(signal, current_price, None, real_balance)
    else:
        log_message(f"\n⏸️  SINAIS FRACOS: BUY={buy_signals}, SELL={sell_signals}", "INFO")

    # Preparar dados para retorno
    analysis_data = {
        'price': current_price,
        'ema_short': ema_short_val,
        'ema_long': ema_long_val,
        'rsi': rsi,
        'bb_upper': bb_upper,
        'bb_lower': bb_lower,
        'volume_current': volume_current,
        'volume_avg': volume_avg,
        'bb_position': bb_position,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals
    }

    return signal, analysis_data

# ============================================================================
# FUNÇÕES DE TRADING
# ============================================================================

def get_balance():
    """Obtém saldo da conta"""
    response = query_private('Balance', {})

    if response.get('error'):
        log_message(f"Erro ao obter saldo: {response['error']}", "ERROR")
        return {}

    balance = response.get('result', {})

    # Formatar saldo
    formatted_balance = {}
    for currency, amount in balance.items():
        if float(amount) > 0:
            formatted_balance[currency] = float(amount)

    return formatted_balance

def get_ticker(pair_name):
    """Obtém ticker atual"""
    response = query_public('Ticker', {'pair': pair_name})

    if response.get('error'):
        log_message(f"Erro ao obter ticker: {response['error']}", "ERROR")
        return {}

    result = response.get('result', {})
    return result.get(pair_name, {})

# ============================================================================
# FUNÇÃO PRINCIPAL COM TRADING AUTOMÁTICO
# ============================================================================

def run_continuous_trading_bot_with_auto_trade():
    """Executa o bot de trading com negociação automática"""

    # Verificar credenciais
    if not api_key or not api_secret:
        log_message("API keys não configuradas. Configure no Google Colab.", "ERROR")
        return

    # Inicializar sistema de trading
    trader = AutoTradingSystem()

    log_separator()
    log_message("🤖 INICIANDO BOT DE TRADING AUTOMÁTICO", "INFO")
    log_message(f"📊 Modo: {TRADING_MODE}", "INFO")
    log_message(f"⏰ Intervalo: {CHECK_INTERVAL_MINUTES} minutos", "INFO")
    log_message(f"💰 Par: {BITCOIN_PAIR}", "INFO")
    log_message(f"🎯 Risco por trade: {RISK_PER_TRADE*100}%", "INFO")
    log_message(f"🛑 Stop Loss: {STOP_LOSS_PERCENT*100}%", "INFO")
    log_message(f"✅ Take Profit: {TAKE_PROFIT_PERCENT*100}%", "INFO")
    log_separator()

    if TRADING_MODE == "LIVE":
        log_message("⚠️  ATENÇÃO: MODO LIVE ATIVADO - ORDENS REAIS!", "WARNING")
        log_message("⚠️  Certifique-se de entender os riscos!", "WARNING")
    else:
        log_message("📝 Modo PAPER: Trades simulados apenas", "INFO")

    # Contadores de estatísticas
    analysis_count = 0
    buy_signals_count = 0
    sell_signals_count = 0
    hold_signals_count = 0
    start_time = datetime.now()

    try:
        while True:
            analysis_count += 1

            log_header(f"ANÁLISE #{analysis_count}")
            log_message(f"Iniciando análise... (Hora: {datetime.now().strftime('%H:%M:%S')})")

            # 1. Verificar conexão
            test_response = query_public('Time', {})
            if test_response.get('error'):
                log_message(f"Erro na conexão: {test_response['error']}", "ERROR")
                time.sleep(60)
                continue

            # 2. Obter saldo real
            real_balance = get_balance()
            usd_balance = 0
            btc_balance = 0

            if real_balance:
                for currency, amount in real_balance.items():
                    if 'USD' in currency or 'ZUSD' in currency:
                        usd_balance += amount
                    elif 'XBT' in currency or 'BTC' in currency:
                        btc_balance += amount

            log_message(f"💰 Saldo REAL: USD=${usd_balance:,.2f}, BTC={btc_balance:.8f}", "INFO")

            # 3. Obter dados do Bitcoin
            df, interval_minutes = get_bitcoin_data_1day(BITCOIN_PAIR, days_back=180)

            if df.empty:
                log_message("Não foi possível obter dados. Tentando novamente...", "ERROR")
                time.sleep(60)
                continue

            candle_interval_days = 1  # Fixo para 1 dia, em vez de interval_minutes // 1440

            # 4. Verificar posições ativas (stop loss / take profit)
            current_price = df['close'].iloc[-1] if not df.empty else 87000
            trader.check_positions(current_price)

            # 5. Análise técnica com trading
            signal, analysis_data = analyze_bitcoin_with_trading(df, candle_interval_days, trader, real_balance)

            # Atualizar contadores
            if signal == "buy":
                buy_signals_count += 1
            elif signal == "sell":
                sell_signals_count += 1
            else:
                hold_signals_count += 1

            # 6. Obter preço atual
            ticker = get_ticker(BITCOIN_PAIR)
            current_price = analysis_data['price']

            if ticker:
                ask_price = float(ticker.get('a', [0])[0]) if 'a' in ticker else 0
                bid_price = float(ticker.get('b', [0])[0]) if 'b' in ticker else 0
                if ask_price and bid_price:
                    current_price = (ask_price + bid_price) / 2

            # 7. Exibir análise
            log_header("RESULTADO DA ANÁLISE")

            log_message(f"📈 Preço atual: ${current_price:,.2f}", "INFO")
            log_message(f"📊 EMA{EMA_SHORT}: ${analysis_data['ema_short']:,.2f}", "INFO")
            log_message(f"📊 EMA{EMA_LONG}: ${analysis_data['ema_long']:,.2f}", "INFO")
            log_message(f"📉 RSI: {analysis_data['rsi']:.1f}", "INFO")
            log_message(f"📏 BB Posição: {analysis_data['bb_position']:.1f}%", "INFO")
            log_message(f"📦 Volume: {analysis_data['volume_current']:.0f} BTC", "INFO")
            log_message(f"📊 Volume vs Média: {analysis_data['volume_current']/analysis_data['volume_avg']:.1f}x", "INFO")

            # 8. Mostrar dashboard de trading periodicamente
            if analysis_count % 2 == 0:  # A cada 2 análises (30 minutos)
                trader.show_trading_dashboard()

            # 9. Mostrar estatísticas gerais
            log_header("ESTATÍSTICAS GERAIS")

            runtime = datetime.now() - start_time
            hours = runtime.seconds // 3600
            minutes = (runtime.seconds % 3600) // 60

            log_message(f"⏱️  Tempo de execução: {hours}h {minutes}m", "INFO")
            log_message(f"📊 Análises realizadas: {analysis_count}", "INFO")
            log_message(f"🟢 Sinais BUY: {buy_signals_count}", "INFO")
            log_message(f"🔴 Sinais SELL: {sell_signals_count}", "INFO")
            log_message(f"🟡 Sinais HOLD: {hold_signals_count}", "INFO")

            # 10. Mostrar últimos candles
            if len(df) >= 3:
                log_header("ÚLTIMOS 3 CANDLES")
                recent = df.tail(3).copy()

                for idx, row in recent.iterrows():
                    change_pct = ((row['close'] - row['open']) / row['open']) * 100
                    vol_ratio = row['volume'] / df['volume'].mean()
                    vol_icon = "📈" if vol_ratio > 1.2 else "📉" if vol_ratio < 0.8 else "➡️"

                    log_message(f"{idx.date()}: ${row['open']:,.0f} → ${row['close']:,.0f} ({change_pct:+.1f}%) {vol_icon}", "INFO")

            log_separator()

            # 11. Aguardar próximo ciclo
            next_check = datetime.now() + timedelta(minutes=CHECK_INTERVAL_MINUTES)
            log_message(f"⏰ Próxima análise: {next_check.strftime('%H:%M:%S')}", "INFO")

            # Contagem regressiva com logs
            for i in range(CHECK_INTERVAL_MINUTES * 60, 0, -60):
                if i % 300 == 0:  # A cada 5 minutos
                    minutes_left = i // 60
                    log_message(f"⏳ Aguardando... {minutes_left} minutos restantes", "INFO")
                time.sleep(60)

            log_separator()

    except KeyboardInterrupt:
        log_message("\n🛑 Bot interrompido pelo usuário", "INFO")

        # Resumo final
        log_header("RESUMO FINAL DO BOT")

        runtime = datetime.now() - start_time
        hours = runtime.seconds // 3600
        minutes = (runtime.seconds % 3600) // 60

        log_message(f"⏱️  Tempo total: {hours}h {minutes}m", "INFO")
        log_message(f"📊 Total de análises: {analysis_count}", "INFO")
        log_message(f"🟢 BUY signals: {buy_signals_count}", "INFO")
        log_message(f"🔴 SELL signals: {sell_signals_count}", "INFO")
        log_message(f"🟡 HOLD signals: {hold_signals_count}", "INFO")

        # Dashboard final de trading
        trader.show_trading_dashboard()

        # Último saldo real
        balance = get_balance()
        if balance:
            log_message("💰 SALDO REAL FINAL:", "INFO")
            for currency, amount in balance.items():
                if float(amount) > 0:
                    log_message(f"  {currency}: {amount}", "INFO")

        log_separator()
        log_message("👋 BOT ENCERRADO", "INFO")

    except Exception as e:
        log_message(f"❌ Erro não esperado: {e}", "ERROR")
        log_message("🔄 Reiniciando em 5 minutos...", "INFO")
        time.sleep(300)
        run_continuous_trading_bot_with_auto_trade()

# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    # Configurações para Google Colab
    print("🤖 Configurando ambiente para execução contínua...")

    # Para evitar timeout no Colab
    import warnings
    warnings.filterwarnings('ignore')

    # Verificar modo de trading
    if TRADING_MODE == "LIVE" and (not api_key or not api_secret):
        print("⚠️  ERRO: API keys não configuradas para modo LIVE")
        print("📝 Alternando para modo PAPER...")
        TRADING_MODE = "PAPER"

    # Iniciar bot com trading automático
    run_continuous_trading_bot_with_auto_trade()
