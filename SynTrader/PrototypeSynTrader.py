# -*- coding: utf-8 -*-
# File: syntraders_modular_v1.py
# Description: Refactored Modular Symbolic HFT System - SYNTRADERS
# Version: 1.0 (Refactored Structure with Placeholders)

import pandas as pd
import numpy as np
import pandas_ta as ta # Ensure pandas_ta is installed: pip install pandas_ta
import math
import random
import time
import logging
from collections import deque
from copy import deepcopy
from typing import Dict, Any, Optional, Tuple, List, Deque, TypedDict

# --- Optional Dependency Imports & Configuration ---
try:
    from hurst import compute_Hc # pip install hurst
    HURST_AVAILABLE = True
except ImportError:
    HURST_AVAILABLE = False
    print("WARN: Library 'hurst' not found. Hurst analysis disabled.")

# Placeholder for Entropy calculation (replace with actual implementation or library)
ENTROPY_AVAILABLE = True # Assume placeholder function exists
def calculate_sample_entropy(series, m=2, r_multiplier=0.2):
    """Placeholder for Sample Entropy calculation."""
    if series.empty or series.std() < 1e-9 or len(series) < m + 1: return 0.0
    # Simulate value based on normalized volatility for demo
    volatility = series.std()
    mean_val = series.mean()
    if abs(mean_val) < 1e-9 : mean_val = 1e-9 # Avoid division by zero
    norm_vol = max(0, min(1, (volatility / (abs(mean_val) * 0.05)) )) # Vol relative to mean (adjust factor)
    return norm_vol * 1.5 + random.uniform(-0.1, 0.1) # Range ~0 to 1.6

try:
    import numba
    NUMBA_AVAILABLE = True
    njit_decorator = numba.njit(fastmath=True, cache=True)
    print("INFO: Numba found. JIT compilation enabled (decorator available).")
except ImportError:
    NUMBA_AVAILABLE = False
    njit_decorator = lambda f: f # Identity decorator if Numba not found
    print("WARN: Library 'numba' not found. No JIT optimization.")

# --- Default Configuration ---
default_config = {
    "general": {"ticker": "BTC-USD", "interval": "15m", "history_period": "60d", "initial_capital": 10000, "api": "yahoo"},
    "symbolic": {
        "polarity_ema_short": 7, "polarity_ema_long": 18, "frequency_atr_period": 14,
        "frequency_entropy_window": 50, "weight_volume_ma_period": 20, "weight_rsi_period": 14,
        "alignment_ema_trend": 55, "hurst_period": 100, "divergence_macd_window": 20,
        "divergence_periods": [5, 13], "polarity_ema_slope_weight": 1.0, "polarity_price_vs_ema_weight": 0.7,
        "polarity_divergence_weight": 0.4, "polarity_sentiment_weight": 0.3, "polarity_threshold_strong": 0.55,
        "polarity_threshold_neutral": 0.18, "frequency_vol_norm_min": 0.3, "frequency_vol_norm_max": 3.0,
        "frequency_entropy_norm_min": 0.2, "frequency_entropy_norm_max": 1.8, "frequency_entropy_weight": 0.45,
        "frequency_sentiment_boost_factor": 0.1, "weight_vol_norm_min": 0.4, "weight_vol_norm_max": 4.0,
        "weight_rsi_strength_factor": 4.5, "weight_volume_factor": 3.5, "weight_polarity_bonus": 1.2,
        "weight_hurst_factor": 1.8, "weight_divergence_bonus": 0.6, "weight_event_impact_factor": 2.0,
        "alignment_high_freq_threshold": 100, "alignment_low_freq_threshold": 20, "alignment_hurst_trend_threshold": 0.58,
        "alignment_hurst_revert_threshold": 0.42, "alignment_entropy_void_threshold": 1.2,
        "alignment_sentiment_factor": 0.5, "alignment_event_factor": 1.5,
        "decision_long_entry_threshold": 0.65, "decision_short_entry_threshold": -0.65
    },
    "external_data": {"sentiment_smoothing_period": 5, "event_impact_decay_periods": 4},
    "ml": {"glyph_sequence_length": 7, "use_rnn_prediction": True, "rnn_confidence_threshold": 0.65,
           "use_rl_decision": True, "rl_confidence_threshold": 0.7,
           "rnn_model_path": "dummy", "rl_agent_path": "dummy"},
    "risk": {"base_position_sizing_method": "risk_percent", "risk_per_trade_percent": 0.01,
             "max_position_percent_of_capital": 0.10, "dynamic_sizing_vol_weight": 0.6,
             "dynamic_sizing_entropy_weight": 0.3, "dynamic_sizing_glyph_weight": 0.1,
             "use_dynamic_stops": True, "atr_stop_loss_multiplier": 1.8, "atr_take_profit_multiplier": 2.5,
             "trailing_stop_atr_multiplier": 1.5, "min_stop_distance_pips": 0.0005},
    "adaptation": {"enabled": False, "update_frequency_trades": 50, "lookback_period_trades": 200,
                   "sharpe_target": 0.8, "max_drawdown_target_percent": 15.0, "parameter_adjustment_step": 0.05},
    "logging": {"level": "INFO", "log_file": "syntraders_refactored_log.txt"}
}

# --- Type Definitions ---
Glyph = Dict[str, Any]
Features = Dict[str, float]
PortfolioState = TypedDict('PortfolioState', {'cash': float, 'position_size': float, 'entry_price': Optional[float], 'equity': float})
TradeParameters = TypedDict('TradeParameters', {'size': float, 'stop_loss': Optional[float], 'take_profit': Optional[float], 'entry_price': float})
Order = Dict[str, Any]
Fill = Dict[str, Any]

# --- Logging Setup ---
log_level = getattr(logging, default_config['logging']['level'].upper(), logging.INFO)
logger = logging.getLogger("SYNTRADERS_Modular")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    # More detailed format including agent name? Requires passing logger or context. Keep simple for now.
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Optional file handler
    # file_handler = logging.FileHandler(default_config['logging']['log_file'])
    # file_handler.setFormatter(formatter)
    # logger.addHandler(file_handler)
logger.setLevel(log_level)

# --- Helper Functions ---
def _normalize(value: float, min_val: float, max_val: float) -> float:
    if pd.isna(value) or pd.isna(min_val) or pd.isna(max_val) or max_val == min_val: return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

def _sigmoid(x: float, k: float = 1.0) -> float:
    return 1.0 / (1.0 + np.exp(-k * x))

# --- Placeholder ML/RL Models ---
class DummyModel:
    """General placeholder for ML/RL models."""
    def __init__(self, model_path: str):
        self.model_path = model_path
        logger.info(f"Initialized DummyModel (path: {model_path})")

    def predict(self, *args, **kwargs) -> Any:
        logger.warning(f"DummyModel predict called for {self.model_path} - returning None.")
        return None

    def get_action(self, *args, **kwargs) -> Tuple[str, float]:
        logger.warning(f"DummyModel get_action called for {self.model_path} - returning HOLD.")
        return "HOLD", 0.0

class DummyRNNPredictor(DummyModel):
    """Placeholder for SequenceForecaster model."""
    def predict(self, sequence: Deque[Glyph]) -> Tuple[Optional[Glyph], float, Optional[str]]:
        if not sequence or len(sequence) < default_config['ml']['glyph_sequence_length']: # Use config
             return None, 0.0, None
        # Simulate prediction
        pred_glyph = {
            'polarity': random.choice(['+', '-', '0', '±']), 'frequency': random.randint(1, 144),
            'weight': random.randint(1, 10), 'alignment': random.choice(ALIGNMENTS),
            'details': {'source': 'RNN_predicted'}, 'timestamp': None
        }
        confidence = random.uniform(0.4, 0.95)
        predicted_regime = random.choice(['Trending', 'Reverting', 'Volatile', 'Neutral', None])
        logger.debug(f"RNN Dummy Prediction: {pred_glyph['polarity']}|{pred_glyph['frequency']}|{pred_glyph['weight']}|{pred_glyph['alignment'][0]} (Conf: {confidence:.2f}), Regime: {predicted_regime}")
        return pred_glyph, confidence, predicted_regime

class DummyRLAgent(DummyModel):
    """Placeholder for CognitiveAgent model."""
    def get_action(self, state_vector: np.ndarray, portfolio_state: PortfolioState) -> Tuple[str, float]:
        # Simulate RL action based on state (vector ignored in dummy)
        action = random.choice(['BUY', 'SELL', 'HOLD', 'CLOSE'])
        confidence = random.uniform(0.5, 0.95)
        # Basic filtering based on current position
        position_size = portfolio_state['position_size']
        if action == "BUY" and position_size > 0: action = "HOLD"
        if action == "SELL" and position_size < 0: action = "HOLD"
        if action == "CLOSE" and position_size == 0: action = "HOLD"
        logger.debug(f"RL Dummy Action: {action} (Conf: {confidence:.2f}) for state (shape {state_vector.shape})")
        return action, confidence


# --- Micro-Agent Classes ---

class FeatureFabricator:
    """Extracts and normalizes technical indicators + external data placeholders."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg_s = config['symbolic']
        self.cfg_ext = config['external_data']
        logger.info("FeatureFabricator initialized.")

    # @njit_decorator # Example: Numba could potentially optimize divergence detection if complex
    def _detect_divergence_numpy(self, prices: np.ndarray, indicators: np.ndarray, window: int = 14) -> float:
        """Robust divergence detection needs careful implementation. Placeholder returns 0."""
        # Placeholder logic - returns 0
        # A real implementation would use algorithms like ZigZag or peak/trough detection
        # and compare price extrema with indicator extrema over the lookback window.
        if len(prices) < window or len(indicators) < window: return 0.0
        return 0.0 # Placeholder

    def detect_multi_period_divergence(self, history_context: pd.DataFrame) -> float:
        """Placeholder for multi-period divergence calculation."""
        # Placeholder - returns 0
        return 0.0

    def calculate_all_features(self, data: pd.DataFrame) -> pd.DataFrame:
        logger.info(f"Calculating features for {len(data)} rows...")
        df = data.copy()
        if df.empty: return df

        # --- Standard Indicators ---
        try:
            df.ta.ema(length=self.cfg_s['polarity_ema_short'], append=True, col_names=(f'EMA_{self.cfg_s["polarity_ema_short"]}',))
            df.ta.ema(length=self.cfg_s['polarity_ema_long'], append=True, col_names=(f'EMA_{self.cfg_s["polarity_ema_long"]}',))
            df.ta.ema(length=self.cfg_s['alignment_ema_trend'], append=True, col_names=(f'EMA_{self.cfg_s["alignment_ema_trend"]}',))
            df.ta.atr(length=self.cfg_s['frequency_atr_period'], append=True, col_names=(f'ATR_{self.cfg_s["frequency_atr_period"]}',))
            df[f'ATR_EMA'] = df[f'ATR_{self.cfg_s["frequency_atr_period"]}'].ewm(span=self.cfg_s['frequency_atr_period']*2, adjust=False).mean()
            df.ta.rsi(length=self.cfg_s['weight_rsi_period'], append=True, col_names=(f'RSI_{self.cfg_s["weight_rsi_period"]}',))
            df[f'Volume_MA_{self.cfg_s["weight_volume_ma_period"]}'] = df['Volume'].rolling(window=self.cfg_s['weight_volume_ma_period'], min_periods=5).mean()
            df['prev_EMA_short'] = df[f'EMA_{self.cfg_s["polarity_ema_short"]}'].shift(1)
            df.ta.macd(append=True)
            df.ta.bbands(append=True)
        except Exception as e:
            logger.error(f"Error calculating standard indicators: {e}", exc_info=True)
            # Continue if possible, some features might be missing

        # --- Advanced Indicators ---
        if HURST_AVAILABLE:
             try:
                 min_hurst_period = self.cfg_s.get('hurst_period', 100)
                 # Apply rolling Hurst - SLOW! Consider calculating less frequently or optimizing
                 df['hurst'] = df['Close'].rolling(window=min_hurst_period, min_periods=min_hurst_period).apply(lambda x: compute_Hc(x.values, kind='price', simplified=True)[0], raw=True)
                 df['hurst'].fillna(0.5, inplace=True) # Fill initial NaNs with neutral
             except Exception as he:
                 logger.warning(f"Hurst calculation failed: {he}. Setting to 0.5.")
                 df['hurst'] = 0.5
        else: df['hurst'] = 0.5

        if ENTROPY_AVAILABLE:
            try:
                 entropy_window=self.cfg_s.get('frequency_entropy_window', 50)
                 log_returns = np.log(df['Close'] / df['Close'].shift(1))
                 df['entropy'] = log_returns.rolling(window=entropy_window, min_periods=entropy_window//2).apply(lambda x: calculate_sample_entropy(x.dropna()), raw=True)
                 df['entropy'].fillna(0.5, inplace=True) # Fill initial NaNs with neutral
            except Exception as ee:
                 logger.warning(f"Entropy calculation failed: {ee}. Setting to 0.5.")
                 df['entropy'] = 0.5
        else: df['entropy'] = 0.5

        # Divergence (Using Placeholder)
        df['divergence_score'] = 0.0 # self.detect_multi_period_divergence(df) # Call real function here

        # --- External Data (Already Added in Orchestrator/Data Loader) ---
        # Ensure smoothing is applied if needed
        if 'sentiment_score' in df.columns:
             smooth_period = self.cfg_ext['sentiment_smoothing_period']
             if smooth_period > 0: df['sentiment_score_smoothed'] = df['sentiment_score'].rolling(window=smooth_period).mean().fillna(0.0)
             else: df['sentiment_score_smoothed'] = df['sentiment_score']
        else: df['sentiment_score_smoothed'] = 0.0

        if 'event_impact_score' not in df.columns: df['event_impact_score'] = 0.0

        # --- Normalization (Example) ---
        df['atr_normalized'] = df[f'ATR_{self.cfg_s["frequency_atr_period"]}'] / df['Close']

        logger.info(f"Feature calculation complete. Columns: {df.shape[1]}")
        # Drop initial NaNs - crucial after rolling calculations
        # Use a combination of key indicators to determine valid start
        key_indicators = [f'EMA_{self.cfg_s["alignment_ema_trend"]}',
                          f'Volume_MA_{self.cfg_s["weight_volume_ma_period"]}',
                          'entropy', 'hurst', 'prev_EMA_short']
        # Only keep rows where *all* these key indicators are valid
        valid_start_index = df.dropna(subset=key_indicators).index.min()
        if pd.notna(valid_start_index):
             df = df.loc[valid_start_index:]
             logger.info(f"DataFrame shape after NaN drop: {df.shape}")
        else:
             logger.error("Could not find valid starting point after feature calculation. DataFrame likely empty.")
             return pd.DataFrame()

        return df


class GlyphSynth:
    """Generates symbolic glyphs based on rich features."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg_s = config['symbolic']
        logger.info("GlyphSynth initialized.")

    def generate(self, features: pd.Series) -> Glyph:
        # --- Using the logic from AdvancedSymbolicEngine.create_glyph ---
        # (Ensure helper functions _normalize, _sigmoid are accessible or defined here)
        glyph = {'polarity': '0', 'frequency': 1, 'weight': 1, 'alignment': 'Void', 'details': {}, 'timestamp': features.name}
        try:
            # Extract features safely
            close=features.get('Close'); ema_short=features.get(f'EMA_{self.cfg_s["polarity_ema_short"]}'); ema_long=features.get(f'EMA_{self.cfg_s["polarity_ema_long"]}'); prev_ema_short=features.get('prev_EMA_short'); atr=features.get(f'ATR_{self.cfg_s["frequency_atr_period"]}'); atr_ema=features.get('ATR_EMA'); volume=features.get('Volume',0); volume_ma=features.get(f'Volume_MA_{self.cfg_s["weight_volume_ma_period"]}',1); rsi=features.get(f'RSI_{self.cfg_s["weight_rsi_period"]}',50); ema_trend=features.get(f'EMA_{self.cfg_s["alignment_ema_trend"]}'); hurst=features.get('hurst',0.5); entropy=features.get('entropy',0.5); divergence_score=features.get('divergence_score',0.0); sentiment_score=features.get('sentiment_score_smoothed',0.0); event_impact=features.get('event_impact_score',0.0)

            # --- Populate Details ---
            glyph['details'].update({ 'hurst': round(hurst,3) if pd.notna(hurst) else np.nan, 'entropy': round(entropy,3) if pd.notna(entropy) else np.nan, 'divergence_score': round(divergence_score,3), 'sentiment_score': round(sentiment_score,2), 'event_impact': round(event_impact,2), 'rsi': round(rsi,1) if pd.notna(rsi) else np.nan, 'atr': round(atr,5) if pd.notna(atr) else np.nan })

            # --- Polarity Calculation ---
            polarity_score = 0
            if pd.notna(ema_short) and pd.notna(prev_ema_short) and pd.notna(atr) and atr > 1e-9:
                polarity_score += _sigmoid(((ema_short - prev_ema_short) / atr), k=2) * self.cfg_s['polarity_ema_slope_weight'] - (0.5 * self.cfg_s['polarity_ema_slope_weight'])
            if pd.notna(close) and pd.notna(ema_long) and pd.notna(atr) and atr > 1e-9:
                polarity_score += _sigmoid(((close - ema_long) / atr), k=1.5) * self.cfg_s['polarity_price_vs_ema_weight'] - (0.5 * self.cfg_s['polarity_price_vs_ema_weight'])
            polarity_score += divergence_score * self.cfg_s['polarity_divergence_weight']
            polarity_score += sentiment_score * self.cfg_s['polarity_sentiment_weight']
            glyph['details']['polarity_raw_score'] = round(polarity_score, 3)
            if polarity_score > self.cfg_s['polarity_threshold_strong']: glyph['polarity'] = '+'
            elif polarity_score < -self.cfg_s['polarity_threshold_strong']: glyph['polarity'] = '-'
            elif abs(polarity_score) < self.cfg_s['polarity_threshold_neutral']: glyph['polarity'] = '0'
            else: glyph['polarity'] = '±'

            # --- Frequency Calculation ---
            norm_volatility = 0.5
            if pd.notna(atr) and pd.notna(atr_ema) and atr_ema > 1e-9: norm_volatility = _normalize(atr, atr_ema * self.cfg_s['frequency_vol_norm_min'], atr_ema * self.cfg_s['frequency_vol_norm_max'])
            vol_factor = norm_volatility ** 1.3
            glyph['details']['norm_volatility'] = round(norm_volatility, 3)
            norm_entropy = 0.5
            if pd.notna(entropy): norm_entropy = _normalize(entropy, self.cfg_s['frequency_entropy_norm_min'], self.cfg_s['frequency_entropy_norm_max'])
            entropy_factor = norm_entropy ** 1.6
            glyph['details']['norm_entropy'] = round(norm_entropy, 3)
            freq_blend = vol_factor * (1.0 - self.cfg_s['frequency_entropy_weight']) + entropy_factor * self.cfg_s['frequency_entropy_weight']
            freq_blend *= (1 + abs(sentiment_score) * self.cfg_s['frequency_sentiment_boost_factor'])
            glyph['frequency'] = max(1, min(144, int(1 + freq_blend * 143)))

            # --- Weight Calculation ---
            volume_weight, rel_volume = 0.0, np.nan
            if pd.notna(volume) and pd.notna(volume_ma) and volume_ma > 1:
                 rel_volume = volume / volume_ma; norm_rel_volume = _normalize(rel_volume, self.cfg_s['weight_vol_norm_min'], self.cfg_s['weight_vol_norm_max']); volume_weight = norm_rel_volume * self.cfg_s['weight_volume_factor']
            glyph['details']['relative_volume'] = round(rel_volume, 2) if pd.notna(rel_volume) else np.nan
            rsi_weight, rsi_strength = 0.0, np.nan
            if pd.notna(rsi): rsi_strength = abs(rsi - 50) / 50; rsi_weight = (rsi_strength ** 1.4) * self.cfg_s['weight_rsi_strength_factor']
            glyph['details']['rsi_strength'] = round(rsi_strength, 2) if pd.notna(rsi_strength) else np.nan
            base_weight = 1 + volume_weight + rsi_weight
            if pd.notna(hurst): base_weight += (hurst - 0.5) * self.cfg_s['weight_hurst_factor']
            if glyph['polarity'] in ['+', '-'] and abs(polarity_score) > self.cfg_s['polarity_threshold_strong']: base_weight += self.cfg_s['weight_polarity_bonus']
            if (divergence_score > 0.5 and glyph['polarity'] == '+') or (divergence_score < -0.5 and glyph['polarity'] == '-'): base_weight += self.cfg_s['weight_divergence_bonus']
            base_weight += abs(event_impact) * self.cfg_s['weight_event_impact_factor']
            glyph['weight'] = max(1, min(10, int(round(base_weight))))

            # --- Alignment Calculation ---
            # (Using the same logic as AdvancedSymbolicEngine for brevity)
            align_scores = {align: 0.1 for align in ALIGNMENTS}
            is_trending = pd.notna(hurst) and hurst > self.cfg_s['alignment_hurst_trend_threshold']
            is_reverting = pd.notna(hurst) and hurst < self.cfg_s['alignment_hurst_revert_threshold']
            is_high_entropy = pd.notna(entropy) and entropy > self.cfg_s['alignment_entropy_void_threshold']
            is_trend_up = pd.notna(close) and pd.notna(ema_trend) and close > ema_trend
            is_high_vol = glyph['frequency'] > self.cfg_s['alignment_high_freq_threshold']
            if is_trending: align_scores['Celestial' if is_trend_up else 'Chthonic'] += 1.2
            if is_reverting: align_scores['Harmonic'] += 1.0; align_scores['Elemental'] += 0.4
            if not is_trending and not is_reverting : align_scores['Void'] += 0.6
            if is_high_entropy: align_scores['Void'] += 1.0; align_scores['Elemental'] += 0.8
            if is_high_vol: align_scores['Elemental'] += 0.6
            align_scores['Celestial'] += max(0, sentiment_score * self.cfg_s['alignment_sentiment_factor'])
            align_scores['Chthonic'] += max(0, -sentiment_score * self.cfg_s['alignment_sentiment_factor'])
            if event_impact > 0.5: align_scores['Celestial'] += self.cfg_s['alignment_event_factor']
            if event_impact < -0.5: align_scores['Chthonic'] += self.cfg_s['alignment_event_factor']
            max_score = 0; candidates = []
            for align, score in align_scores.items():
                if score > max_score: max_score, candidates = score, [align]
                elif score == max_score: candidates.append(align)
            glyph['alignment'] = random.choice(candidates) if candidates else 'Void'
            glyph['details']['alignment_scores'] = {k: round(v, 2) for k, v in align_scores.items()}

        except Exception as e:
            logger.error(f"Error generating glyph for {features.name}: {e}", exc_info=True)
            glyph = {'polarity': '?', 'frequency': 0, 'weight': 0, 'alignment': 'Error', 'details': {'error': str(e)}, 'timestamp': features.name}

        # logger.debug(f"Generated Glyph: P:{glyph['polarity']} F:{glyph['frequency']} W:{glyph['weight']} A:{glyph['alignment']}")
        return glyph

class SequenceForecaster:
    """Transformer-based dummy model (placeholder)."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = DummyRNNPredictor(config['ml']['rnn_model_path']) # Use specific dummy
        logger.info("SequenceForecaster initialized (Dummy RNN).")

    def predict(self, glyph_sequence: Deque[Glyph]) -> Tuple[Optional[Glyph], float, Optional[str]]:
        # Pass sequence to the dummy model's predict method
        return self.model.predict(glyph_sequence)

class CognitiveAgent:
    """Dummy RL agent (placeholder)."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent = DummyRLAgent(config['ml']['rl_agent_path']) # Use specific dummy
        logger.info("CognitiveAgent initialized (Dummy RL).")

    def _build_state_vector(self, current_glyph: Glyph, predicted_glyph: Optional[Glyph],
                           indicators: pd.Series, portfolio_state: PortfolioState) -> np.ndarray:
        # --- Build state vector for RL Agent ---
        # (Simplified example - real implementation needs careful feature engineering & scaling)
        def encode_polarity(p):
            if p == '+': return 1.0;
            if p == '-': return -1.0;
            if p == '±': return 0.0;
            return 0.5 # for 0 or ?/Error

        def encode_alignment(a):
             try: return ALIGNMENTS.index(a) / len(ALIGNMENTS)
             except ValueError: return 0.5 # Neutral if unknown

        state = [
            encode_polarity(current_glyph['polarity']),
            current_glyph['frequency'] / 144.0,
            current_glyph['weight'] / 10.0,
            encode_alignment(current_glyph['alignment']),
            encode_polarity(predicted_glyph['polarity']) if predicted_glyph else 0.5,
            predicted_glyph['frequency'] / 144.0 if predicted_glyph else 0.5,
            predicted_glyph['weight'] / 10.0 if predicted_glyph else 0.5,
            encode_alignment(predicted_glyph['alignment']) if predicted_glyph else 0.5,
            _normalize(indicators.get(f'RSI_{self.config["symbolic"]["weight_rsi_period"]}', 50), 0, 100),
            _normalize(indicators.get('MACDh_12_26_9', 0), -abs(indicators.get('MACD_12_26_9',0.1))*0.5, abs(indicators.get('MACD_12_26_9',0.1))*0.5),
            current_glyph.get('details', {}).get('norm_volatility', 0.5),
            current_glyph.get('details', {}).get('norm_entropy', 0.5),
            _normalize(current_glyph.get('details',{}).get('hurst', 0.5), 0, 1),
            _normalize(current_glyph.get('details',{}).get('divergence_score', 0), -1, 1),
            _normalize(current_glyph.get('details',{}).get('sentiment_score', 0), -1, 1),
            1 if portfolio_state['position_size'] > 0 else (-1 if portfolio_state['position_size'] < 0 else 0)
        ]
        return np.array(state, dtype=np.float32)

    def get_action(self, current_glyph: Glyph, predicted_glyph: Optional[Glyph],
                   indicators: pd.Series, portfolio_state: PortfolioState) -> Tuple[str, float]:
        state_vector = self._build_state_vector(current_glyph, predicted_glyph, indicators, portfolio_state)
        return self.agent.get_action(state_vector, portfolio_state) # Pass state to dummy

class HybridDecisionEngine:
    """Implements ensemble voting logic exactly as specified."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg_ml = config['ml']
        self.cfg_s = config['symbolic']
        # Load decision weights dynamically? For now, fixed example
        self.weights = {"RL": 1.2, "Symbolic": 1.0}
        logger.info("HybridDecisionEngine initialized.")

    def _calculate_symbolic_score(self, cg: Glyph, pg: Optional[Glyph], rnn_conf: float,
                                  indicators: pd.Series, sentiment: float, event_impact: float) -> Tuple[float, List[str]]:
        """Calculates the symbolic score based on multiple factors."""
        score = 0.0
        reasons = []
        if not cg or cg['alignment'] == 'Error': return 0.0, ["Invalid Current Glyph"]

        # a) Current Glyph
        cg_p, cg_w = cg['polarity'], cg['weight']
        glyph_signal = 0
        if cg_p == '+': glyph_signal = cg_w / 10.0
        elif cg_p == '-': glyph_signal = -cg_w / 10.0
        score += glyph_signal * self.cfg_s.get('w_cg_p', 0.8); # Use configured weight or default
        if abs(glyph_signal) > 0.1: reasons.append(f"G({cg_p}{cg_w})")

        # b) Predicted Glyph
        use_rnn = self.cfg_ml['use_rnn_prediction'] and pg and rnn_conf >= self.cfg_ml['rnn_confidence_threshold']
        if use_rnn:
            pg_p, pg_w = pg['polarity'], pg['weight']
            pred_signal = 0
            if pg_p == '+': pred_signal = pg_w / 10.0
            elif pg_p == '-': pred_signal = -pg_w / 10.0
            score += pred_signal * self.cfg_s.get('w_pg_p', 0.5) * rnn_conf
            if abs(pred_signal)>0.1: reasons.append(f"P({pg_p}{pg_w}|C{rnn_conf:.1f})")

        # c) Contextual Factors
        div = cg.get('details', {}).get('divergence_score', 0)
        hurst = cg.get('details', {}).get('hurst', 0.5)
        # Add divergence only if confirming the score direction
        if div * np.sign(score + 1e-6) > 0.1:
             score += div * self.cfg_s.get('w_divergence', 0.3)
             reasons.append(f"Div({div:.1f})")
        # Hurst trend continuation / reversion damping
        if pd.notna(hurst):
             trend_factor = (hurst - 0.5) * 2.0
             score *= (1 + trend_factor * self.cfg_s.get('w_hurst_mod', 0.15))
             reasons.append(f"H({hurst:.2f})")
        # Direct sentiment/event push
        score += sentiment * self.cfg_s.get('w_sentiment', 0.2)
        score += event_impact * self.cfg_s.get('w_event', 0.4)
        if abs(sentiment)>0.2: reasons.append(f"S({sentiment:.1f})")
        if abs(event_impact)>0.1: reasons.append(f"E({event_impact:.1f})")

        # Clip score
        score = max(-2.0, min(2.0, score))
        return score, reasons

    def decide(self, current_glyph: Glyph, predicted_glyph: Optional[Glyph], rnn_confidence: float,
               rl_action: str, rl_confidence: float, indicators: pd.Series,
               portfolio_state: PortfolioState) -> Tuple[str, float, str]:
        provisional_decision = "HOLD"
        confidence_map = {"RL": 0.0, "Symbolic": 0.0}
        reasons = []
        final_confidence = 0.0
        current_position_size = portfolio_state['position_size']

        # --- Contextual Overrides ---
        event_impact = current_glyph.get('details', {}).get('event_impact_score', 0.0)
        # Add Glyph Stability Check here if implemented in GlyphSynth
        if abs(event_impact) > 0.8:
            reasons.append(f"EventOverride({event_impact:.1f})")
            if current_position_size != 0: return "CLOSE", 0.9, ", ".join(reasons)
            else: return "HOLD", 0.0, ", ".join(reasons)

        # --- Gather Votes ---
        # RL Vote
        rl_vote = "HOLD"
        use_rl = self.config['ml']['use_rl_decision'] and rl_action != "HOLD" and rl_confidence >= self.config['ml']['rl_confidence_threshold']
        if use_rl:
            # Translate RL action based on current position
            if rl_action == "BUY" and current_position_size <= 0: rl_vote = "ENTER_LONG"
            elif rl_action == "SELL" and current_position_size >= 0: rl_vote = "ENTER_SHORT"
            elif rl_action == "CLOSE" and current_position_size != 0:
                rl_vote = "CLOSE_LONG" if current_position_size > 0 else "CLOSE_SHORT"
            # If RL says BUY but already long, it defaults to HOLD here
            if rl_vote != "HOLD":
                 confidence_map["RL"] = rl_confidence
                 reasons.append(f"RL({rl_action}|{rl_confidence:.2f})")

        # Symbolic Vote
        symbolic_score, sym_reasons = self._calculate_symbolic_score(
            current_glyph, predicted_glyph, rnn_confidence, indicators,
            current_glyph.get('details', {}).get('sentiment_score', 0.0), event_impact)
        symbolic_vote = "HOLD"
        long_thresh = self.cfg_s['decision_long_entry_threshold']
        short_thresh = self.cfg_s['decision_short_entry_threshold']
        symbolic_confidence = min(1.0, abs(symbolic_score)) # Simple confidence
        if symbolic_score > long_thresh and current_position_size <= 0: symbolic_vote = "ENTER_LONG"
        elif symbolic_score < short_thresh and current_position_size >= 0: symbolic_vote = "ENTER_SHORT"
        elif current_position_size > 0 and symbolic_score < short_thresh * 0.5: symbolic_vote = "CLOSE_LONG"; symbolic_confidence *= 0.7
        elif current_position_size < 0 and symbolic_score > long_thresh * 0.5: symbolic_vote = "CLOSE_SHORT"; symbolic_confidence *= 0.7
        if symbolic_vote != "HOLD":
            confidence_map["Symbolic"] = symbolic_confidence
            reasons.extend(sym_reasons[:2])

        # --- Combine Votes (Weighted Average) ---
        final_score = 0.0
        total_weight = 0.0 # Sum of weights * confidences

        # RL Contribution
        if rl_vote != "HOLD":
            weight = self.weights["RL"] # Use base weight
            conf = confidence_map["RL"]
            vote_val = 1.0 if rl_vote in ["ENTER_LONG", "CLOSE_SHORT"] else -1.0
            final_score += vote_val * weight * conf
            total_weight += weight * conf

        # Symbolic Contribution
        if symbolic_vote != "HOLD":
            weight = self.weights["Symbolic"] # Use base weight
            conf = confidence_map["Symbolic"]
            vote_val = 1.0 if symbolic_vote in ["ENTER_LONG", "CLOSE_SHORT"] else -1.0
            final_score += vote_val * weight * conf
            total_weight += weight * conf

        # --- Determine Final Decision ---
        if total_weight < 0.1: # Min combined weighted confidence
             provisional_decision = "HOLD"
             final_confidence = 0.0
             reasons.append("LowCombConf")
        else:
            # Normalize final score by total weight used -> Direction score (-1 to 1)
            final_direction = final_score / (total_weight + 1e-9)
            # Final confidence could be average confidence weighted by score magnitude?
            final_confidence = min(1.0, total_weight / sum(self.weights.values())) * abs(final_direction)

            decision_threshold = 0.35 # Threshold on the final combined score direction

            if final_direction > decision_threshold: # Leaning Long
                 if current_position_size <= 0: provisional_decision = "ENTER_LONG"
                 elif current_position_size < 0 : provisional_decision = "CLOSE_SHORT"
                 else: provisional_decision = "HOLD"
            elif final_direction < -decision_threshold: # Leaning Short
                 if current_position_size >= 0: provisional_decision = "ENTER_SHORT"
                 elif current_position_size > 0 : provisional_decision = "CLOSE_LONG"
                 else: provisional_decision = "HOLD"
            else: # Zone Neutre
                provisional_decision = "HOLD"
                final_confidence = 0.0

        # Final sanity checks
        if provisional_decision == "ENTER_LONG" and current_position_size > 0: provisional_decision = "HOLD"
        if provisional_decision == "ENTER_SHORT" and current_position_size < 0: provisional_decision = "HOLD"
        if provisional_decision in ["CLOSE_LONG", "CLOSE_SHORT"] and current_position_size == 0: provisional_decision = "HOLD"

        reason_str = f"{provisional_decision} | Conf:{final_confidence:.2f} | " + ", ".join(reasons)
        logger.debug(f"HDE Decision: {provisional_decision} (Conf:{final_confidence:.2f}) - Reason: {reason_str}")
        return provisional_decision, final_confidence, reason_str

class RiskModulator:
    """Calculates dynamic position sizing, stop loss, take profit."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg_r = config['risk']
        logger.info("RiskModulator initialized.")

    def calculate_trade_params(self, decision: str, current_glyph: Glyph,
                               indicators: pd.Series, portfolio_state: PortfolioState) -> Optional[TradeParameters]:
        if decision not in ["ENTER_LONG", "ENTER_SHORT"]: return None

        entry_price = indicators.get('Close', np.nan)
        current_atr = indicators.get(f'ATR_{self.config["symbolic"]["frequency_atr_period"]}', np.nan)
        if pd.isna(entry_price) or pd.isna(current_atr) or current_atr < 1e-9:
            logger.warning("RiskMod: Cannot calculate params: Missing price or ATR.")
            return None

        # --- SL Calculation ---
        sl_mult = self.cfg_r['atr_stop_loss_multiplier']
        freq_factor = 1.0 - _normalize(current_glyph['frequency'], 1, 144) * 0.4 # 1.0 (low) to 0.6 (high)
        sl_distance = sl_mult * current_atr * max(0.6, freq_factor)
        min_stop_pips = self.cfg_r.get('min_stop_distance_pips', 0.0005)
        sl_distance = max(sl_distance, min_stop_pips * entry_price if entry_price > 0 else min_stop_pips) # Min distance relative or absolute
        stop_loss_price = entry_price - sl_distance if decision == "ENTER_LONG" else entry_price + sl_distance

        # --- Position Size Calculation ---
        size = 0.0
        capital = portfolio_state['equity']
        if self.cfg_r['base_position_sizing_method'] == 'risk_percent':
            risk_amount = capital * self.cfg_r['risk_per_trade_percent']
            risk_per_unit = abs(entry_price - stop_loss_price)
            if risk_per_unit > 1e-9:
                base_size = risk_amount / risk_per_unit
                size_modifier = 1.0
                if self.cfg_r['use_dynamic_sizing']:
                    norm_vol = current_glyph.get('details', {}).get('norm_volatility', 0.5)
                    norm_entropy = current_glyph.get('details', {}).get('norm_entropy', 0.5)
                    glyph_weight = current_glyph.get('weight', 5)
                    vol_factor = 1.0 - norm_vol; entropy_factor = 1.0 - norm_entropy; weight_factor = _normalize(glyph_weight, 1, 10)
                    size_modifier = (vol_factor * self.cfg_r['dynamic_sizing_vol_weight'] +
                                     entropy_factor * self.cfg_r['dynamic_sizing_entropy_weight'] +
                                     weight_factor * self.cfg_r['dynamic_sizing_glyph_weight'])
                    size_modifier = max(0.3, min(1.7, size_modifier))
                final_size = base_size * size_modifier
                max_pos_value = capital * self.cfg_r['max_position_percent_of_capital']
                max_size_by_capital = max_pos_value / entry_price if entry_price > 0 else 0
                final_size = min(final_size, max_size_by_capital)
                size = round(final_size, 8) if final_size > 1e-9 else 0.0
        else: size = self.cfg_r.get('fixed_position_size', 0.01)

        if size <= 0: logger.warning(f"RiskMod: Calculated size is zero for {decision}."); return None

        # --- TP Calculation ---
        tp_mult = self.cfg_r['atr_take_profit_multiplier']
        tp_distance = tp_mult * current_atr * max(0.7, freq_factor)
        take_profit_price = entry_price + tp_distance if decision == "ENTER_LONG" else entry_price - tp_distance

        params = {'size': size, 'stop_loss': stop_loss_price, 'take_profit': take_profit_price, 'entry_price': entry_price}
        logger.debug(f"RiskMod Params: {params}")
        return params

    def manage_trailing_stop(self, current_price: float, current_atr: float,
                             position_size: float, current_stop_loss: Optional[float]) -> Optional[float]:
        if position_size == 0 or self.config['risk']['trailing_stop_atr_multiplier'] <= 0 or pd.isna(current_atr) or current_atr < 1e-9 or pd.isna(current_price):
            return current_stop_loss # No trailing or invalid data

        trailing_amount = self.config['risk']['trailing_stop_atr_multiplier'] * current_atr
        new_trailing_stop = None
        if position_size > 0: # Long
            candidate_stop = current_price - trailing_amount
            if current_stop_loss is None or candidate_stop > current_stop_loss: new_trailing_stop = candidate_stop
        elif position_size < 0: # Short
            candidate_stop = current_price + trailing_amount
            if current_stop_loss is None or candidate_stop < current_stop_loss: new_trailing_stop = candidate_stop

        # Return the updated SL if it trailed, otherwise the original SL
        return new_trailing_stop if new_trailing_stop is not None else current_stop_loss


class OrderOrchestrator:
    """Formats orders for the execution engine."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ticker = config['general']['ticker']
        logger.info("OrderOrchestrator initialized.")

    def format_order(self, decision: str, trade_params: TradeParameters) -> Optional[Order]:
        # ... (Identique à la version précédente) ...
        if not trade_params: return None
        order_type = "MARKET"; side = "BUY" if decision == "ENTER_LONG" else "SELL"; size = trade_params['size']
        order = { "timestamp": pd.Timestamp.utcnow(), "symbol": self.ticker, "type": order_type, "side": side, "size": size, "price": None, "stop_loss": trade_params.get('stop_loss'), "take_profit": trade_params.get('take_profit'), "status": "NEW" }
        logger.debug(f"Formatted Order: {order}")
        return order

    def format_close_order(self, position_size: float) -> Optional[Order]:
        # ... (Identique à la version précédente) ...
        if abs(position_size) < 1e-9: return None
        order_type = "MARKET"; side = "SELL" if position_size > 0 else "BUY"; size = abs(position_size)
        order = { "timestamp": pd.Timestamp.utcnow(), "symbol": self.ticker, "type": order_type, "side": side, "size": size, "price": None, "stop_loss": None, "take_profit": None, "status": "NEW_CLOSE" }
        logger.debug(f"Formatted Close Order: {order}")
        return order

class ExecutionEngine:
    """Simulates sending orders and receiving fills."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg_risk = config['risk'] # Assume commission/slippage in risk config for now
        self.commission_per_trade = self.cfg_risk.get('commission_percent', 0.0005) # 0.05% default
        self.slippage_factor = self.cfg_risk.get('slippage_percent', 0.0001) # 0.01% default
        logger.info(f"ExecutionEngine initialized (Sim Mode: Comm={self.commission_per_trade*100}%, Slip={self.slippage_factor*100}%)")

    def execute(self, order: Order, current_market_price: float) -> Optional[Fill]:
        # ... (Identique à la version précédente) ...
        if not order or order['status'] not in ["NEW", "NEW_CLOSE"]: return None
        if pd.isna(current_market_price): logger.error(f"ExecEngine: Invalid market price for order {order}"); return None
        size = order['size']; fill_price = current_market_price * (1 + self.slippage_factor) if order['side'] == 'BUY' else current_market_price * (1 - self.slippage_factor)
        commission = size * fill_price * self.commission_per_trade; fill_timestamp = pd.Timestamp.utcnow()
        fill = { "timestamp": fill_timestamp, "order_id": f"sim_{int(fill_timestamp.timestamp()*1000)}_{random.randint(100,999)}", "symbol": order['symbol'], "side": order['side'], "size": size, "fill_price": fill_price, "commission": commission, "status": "FILLED", "original_order": order }
        logger.debug(f"Simulated Fill: {fill}")
        return fill

class PortfolioManager:
    """Tracks cash, positions, PnL, equity curve."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initial_capital = config['general']['initial_capital']
        self.cash = self.initial_capital
        self.position_size = 0.0
        self.entry_price: Optional[float] = None
        self.current_stop_loss: Optional[float] = None # Added SL/TP tracking
        self.current_take_profit: Optional[float] = None
        self.current_equity = self.initial_capital
        self.equity_curve: List[Dict] = []
        self.trade_log: List[Dict] = []
        self.realized_pnl = 0.0
        self.trade_count = 0
        logger.info(f"PortfolioManager initialized with capital: {self.initial_capital}")

    def get_state(self) -> PortfolioState:
        return { 'cash': self.cash, 'position_size': self.position_size, 'entry_price': self.entry_price, 'equity': self.current_equity }

    def update_on_decision(self, decision: str, trade_params: Optional[TradeParameters]):
        """Updates internal SL/TP when an entry decision is made (before execution)."""
        if decision in ["ENTER_LONG", "ENTER_SHORT"] and trade_params:
            self.current_stop_loss = trade_params.get('stop_loss')
            self.current_take_profit = trade_params.get('take_profit')
            logger.debug(f"PM State Update on Decision: SL={self.current_stop_loss}, TP={self.current_take_profit}")
        elif decision in ["CLOSE_LONG", "CLOSE_SHORT"]:
             # SL/TP become irrelevant once close order is generated
             self.current_stop_loss = None
             self.current_take_profit = None

    def update_trailing_stop(self, new_stop_loss: Optional[float]):
         """Updates the SL if the trailing stop moved it."""
         if new_stop_loss is not None:
             self.current_stop_loss = new_stop_loss

    def update_portfolio(self, fill: Fill, current_market_price: Optional[float] = None):
        # ... (Logic largely identical to previous version, ensure SL/TP reset on close) ...
        if not fill or fill['status'] != "FILLED": return
        timestamp=fill['timestamp']; size=fill['size']; price=fill['fill_price']; commission=fill['commission']; side=fill['side']
        position_change = size if side == "BUY" else -size; cost_basis_change = position_change * price
        old_position_size = self.position_size; old_entry_price = self.entry_price
        trade_pnl = 0.0

        if (old_position_size > 0 and side == "SELL") or (old_position_size < 0 and side == "BUY"): # Closing/Reducing
            closed_size = min(abs(old_position_size), size)
            if old_entry_price is not None:
                pnl_per_unit = price - old_entry_price if old_position_size > 0 else old_entry_price - price
                trade_pnl = pnl_per_unit * closed_size - commission
                self.realized_pnl += trade_pnl; self.trade_count += 1
                logger.info(f"Trade Closed/Reduced: Size={closed_size:.8f} @ {price:.5f}, PnL={trade_pnl:.4f}")
            else: logger.error("Cannot calc PNL: Entry price missing.")
            self.cash += closed_size * price * (1 if side == "SELL" else -1); self.cash -= commission
            self.position_size += position_change
            if abs(self.position_size) < 1e-9: # Fully Closed
                self.position_size = 0.0; self.entry_price = None; self.current_stop_loss = None; self.current_take_profit = None
        elif (old_position_size >= 0 and side == "BUY") or (old_position_size <= 0 and side == "SELL"): # Opening/Increasing
            if old_position_size == 0: self.entry_price = price # New position
            else: # Increase position (average entry - simplified)
                 new_total_size = old_position_size + position_change
                 if new_total_size != 0 and old_entry_price is not None: self.entry_price = (old_position_size * old_entry_price + position_change * price) / new_total_size
                 else: self.entry_price = price # Fallback
            self.position_size += position_change
            self.cash -= abs(cost_basis_change); self.cash -= commission
            logger.info(f"Position Opened/Increased: Size={size:.8f} @ {price:.5f}, New Pos={self.position_size:.8f}")
            # Note: SL/TP are set via update_on_decision *before* this fill happens normally
        else: logger.error(f"Unhandled trade logic: Pos={old_position_size}, Side={side}")

        self.trade_log.append({ "timestamp": timestamp, "symbol": fill['symbol'], "side": fill['side'], "size": size, "price": price, "commission": round(commission, 5), "realized_pnl": round(trade_pnl, 5), "position_after": round(self.position_size, 8), "cash_after": round(self.cash, 2) })
        self.update_equity(current_market_price if current_market_price is not None else price, timestamp)


    def update_equity(self, current_market_price: float, timestamp: pd.Timestamp):
        # ... (Identique à la version précédente) ...
        if pd.isna(current_market_price): return
        unrealized_pnl = (current_market_price - self.entry_price) * self.position_size if self.position_size != 0 and self.entry_price is not None else 0.0
        self.current_equity = self.cash + self.position_size * current_market_price
        self.equity_curve.append({'timestamp': timestamp, 'equity': self.current_equity, 'cash': self.cash, 'position': self.position_size, 'unrealized_pnl': unrealized_pnl})


    def calculate_performance(self, trades_df: Optional[pd.DataFrame]=None, equity_df: Optional[pd.DataFrame]=None) -> Dict[str, Any]:
        """Calculates performance metrics based on own logs or provided DFs."""
        # --- Using the improved logic from HyperSyntrader ---
        if trades_df is None: trades_df = pd.DataFrame(self.trade_log)
        if equity_df is None:
             equity_df = pd.DataFrame(self.equity_curve)
             if 'timestamp' in equity_df.columns:
                  try:
                      equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
                      equity_df = equity_df.set_index('timestamp')
                  except Exception: logger.error("PM: Failed equity timestamp conversion."); equity_df=pd.DataFrame() # Fallback empty
             else: equity_df=pd.DataFrame() # Fallback empty


        if trades_df.empty or equity_df.empty or not isinstance(equity_df.index, pd.DatetimeIndex) or len(equity_df) < 2:
            logger.warning("PM: Insufficient data for performance calculation.")
            return {"message": "Insufficient data"}

        equity_df['returns'] = equity_df['equity'].pct_change().fillna(0)
        sharpe_ratio = np.nan; time_delta_days = (equity_df.index[-1] - equity_df.index[0]).total_seconds() / (3600*24)
        try: # Robust Sharpe
            if time_delta_days < 1: periods_per_year = 365*24*60 # Minute? Assume 1min for safety
            elif time_delta_days < 7: periods_per_year = 365*24 # Hourly?
            else: periods_per_year = 252 # Daily approx
            std_dev = equity_df['returns'].std()
            if std_dev > 1e-9: sharpe_ratio = np.sqrt(periods_per_year) * equity_df['returns'].mean() / std_dev
        except Exception as e: logger.warning(f"PM: Sharpe calc error: {e}")
        equity_df['cum_max'] = equity_df['equity'].cummax(); equity_df['drawdown'] = equity_df['equity'] / equity_df['cum_max'] - 1; max_drawdown = equity_df['drawdown'].min()
        closing_trades = trades_df[trades_df['realized_pnl'].notna() & (trades_df['realized_pnl'] != 0)].copy()
        total_trades = len(closing_trades); win_rate = 0.0; profit_factor = np.inf; total_pnl = 0.0; avg_win = 0; avg_loss = 0
        if total_trades > 0:
            win_trades = closing_trades[closing_trades['realized_pnl'] > 0]; loss_trades = closing_trades[closing_trades['realized_pnl'] < 0]
            win_rate = len(win_trades) / total_trades; total_pnl = closing_trades['realized_pnl'].sum()
            total_win_pnl = win_trades['realized_pnl'].sum(); total_loss_pnl = loss_trades['realized_pnl'].sum()
            profit_factor = abs(total_win_pnl / total_loss_pnl) if total_loss_pnl != 0 else np.inf
            avg_win = win_trades['realized_pnl'].mean() if not win_trades.empty else 0
            avg_loss = loss_trades['realized_pnl'].mean() if not loss_trades.empty else 0

        metrics = { "Start Date": equity_df.index.min().strftime('%Y-%m-%d %H:%M'), "End Date": equity_df.index.max().strftime('%Y-%m-%d %H:%M'), "Duration (Days)": round(time_delta_days, 1), "Initial Capital": round(self.initial_capital, 2), "Final Equity": round(equity_df['equity'].iloc[-1], 2), "Total P&L": round(total_pnl, 4), "Total P&L (%)": round((equity_df['equity'].iloc[-1] / self.initial_capital - 1) * 100, 2), "Total Trades": total_trades, "Win Rate (%)": round(win_rate * 100, 2), "Profit Factor": round(profit_factor, 2) if profit_factor != np.inf else "inf", "Sharpe Ratio (Ann.)": round(sharpe_ratio, 2) if pd.notna(sharpe_ratio) else "N/A", "Max Drawdown (%)": round(max_drawdown * 100, 2), "Avg Winning Trade": round(avg_win, 4), "Avg Losing Trade": round(avg_loss, 4), }
        logger.info(f"Performance Metrics Calculated:\n{pd.Series(metrics)}")
        return metrics


class AdaptiveTuner:
    """Placeholder for Optuna/Bayesian optimization integration."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config # Reference to the live config object
        self.cfg_adapt = config['adaptation']
        self.last_tune_trade_count = 0
        logger.info("AdaptiveTuner initialized (Placeholder).")

    def check_and_run_optimization(self, portfolio_manager: PortfolioManager):
        if not self.cfg_adapt['enabled']: return False
        current_trade_count = portfolio_manager.trade_count
        if current_trade_count >= self.last_tune_trade_count + self.cfg_adapt['update_frequency_trades']:
            logger.info(f"--- Triggering Adaptive Parameter Tuning (Trade {current_trade_count}) ---")
            self.last_tune_trade_count = current_trade_count # Update counter
            # --- Placeholder logic ---
            # 1. Get recent performance metrics from PM
            # performance = portfolio_manager.calculate_performance(trades_df=pd.DataFrame(portfolio_manager.trade_log[-self.cfg_adapt['lookback_period_trades']:]))
            # 2. Run simple rule adaptation (or call Optuna study)
            # adjustments = self._run_simple_rule_adaptation(performance)
            adjustments = None # Simulate no change for now
            # 3. Apply adjustments to the *live* config dictionary (self.config)
            if adjustments:
                 logger.warning(f"ADAPTATION SUGGESTED: {adjustments}")
                 # Merge adjustments into self.config carefully
                 for section, params in adjustments.items():
                     if section in self.config:
                         for key, value in params.items():
                              if key in self.config[section]:
                                   logger.warning(f"  Updating config[{section}][{key}]: {self.config[section][key]} -> {value}")
                                   self.config[section][key] = value
                 return True
            else:
                 logger.info("No parameter changes suggested by adaptation.")
                 return False
        return False

    def _run_simple_rule_adaptation(self, metrics):
         # Example simple adaptation rules (from HyperSyntrader)
         adjustments = {}; step = self.cfg_adapt['parameter_adjustment_step']
         if metrics.get("Sharpe Ratio (Ann.)", 0) < self.cfg_adapt['sharpe_target'] * 0.7:
             param_key = 'polarity_threshold_strong'; current_val = self.config['symbolic'][param_key]
             new_val = min(0.95, current_val * (1 + step));
             if abs(new_val - current_val) > 1e-4: adjustments.setdefault('symbolic', {})[param_key] = round(new_val, 3)
         if abs(metrics.get("Max Drawdown (%)", 0)) > self.cfg_adapt['max_drawdown_target_percent']:
              param_key = 'risk_per_trade_percent'; current_val = self.config['risk'][param_key]
              new_val = max(0.001, current_val * (1 - step));
              if abs(new_val - current_val) > 1e-5: adjustments.setdefault('risk', {})[param_key] = round(new_val, 4)
         return adjustments if adjustments else None

# --- Orchestrator ---
class SyntraderOrchestrator:
    """Connects and manages the micro-agents for backtesting or live trading."""
    def __init__(self, config: Dict[str, Any]):
        self.config = deepcopy(config) # Operate on a copy for this run
        self.data: Optional[pd.DataFrame] = None
        self.performance_metrics: Optional[Dict] = None

        logger.info("Initializing agents...")
        # Pass the *same* config reference to agents that need live updates
        self.feature_fabricator = FeatureFabricator(self.config)
        self.glyph_synth = GlyphSynth(self.config)
        self.sequence_forecaster = SequenceForecaster(self.config)
        self.cognitive_agent = CognitiveAgent(self.config)
        self.decision_engine = HybridDecisionEngine(self.config)
        self.risk_modulator = RiskModulator(self.config)
        self.order_orchestrator = OrderOrchestrator(self.config)
        self.execution_engine = ExecutionEngine(self.config)
        self.portfolio_manager = PortfolioManager(self.config)
        self.adaptive_tuner = AdaptiveTuner(self.config) # Tuner modifies self.config directly
        self.glyph_sequence: Deque[Glyph] = deque(maxlen=self.config['ml']['glyph_sequence_length'])
        logger.info("All agents initialized.")

    def _load_data(self) -> bool:
        # ... (Identique à la version précédente) ...
        logger.info(f"Loading data for {self.config['general']['ticker']}...")
        if self.config['general']['api'] == 'yahoo':
             try:
                 fetch_period = self.config['general']['history_period']; interval = self.config['general']['interval']
                 if interval == '1m': fetch_period = '7d'
                 elif interval in ['5m', '15m']: fetch_period = '60d'
                 elif interval in ['30m', '60m', '1h', '90m']: fetch_period = '730d'
                 df = yf.download(tickers=self.config['general']['ticker'], period=fetch_period, interval=interval, progress=False)
                 if df.empty: logger.error("No data from yfinance."); return False
                 df.index = pd.to_datetime(df.index)
                 df['sentiment_score'] = np.random.uniform(-0.5, 0.5, len(df)); df['event_impact_score'] = 0.0 # Placeholders
                 self.data = df; logger.info(f"Data loaded: {len(self.data)} rows"); return True
             except Exception as e: logger.error(f"yfinance error: {e}", exc_info=True); return False
        else: logger.error("Only 'yahoo' API supported."); return False


    def _prepare_features(self):
        if self.data is None or self.data.empty: logger.error("Cannot prepare features: No data."); return False
        self.data = self.feature_fabricator.calculate_all_features(self.data)
        return not self.data.empty

    def run_backtest(self):
        if not self._load_data() or not self._prepare_features():
             logger.error("Backtest aborted: Data/Feature error.")
             return None
        logger.info(f"--- Starting Backtest: {self.config['general']['ticker']} ({self.config['general']['interval']}) ---")
        self.portfolio_manager = PortfolioManager(self.config) # Reset portfolio

        # Event Loop
        for i in range(len(self.data)):
            timestamp = self.data.index[i]
            current_data_row = self.data.iloc[i]
            # History includes current row for calcs based on close price etc.
            history_window_size = max(105, self.config['ml']['glyph_sequence_length']+5) # Ensure enough history
            history_context_df = self.data.iloc[max(0, i - history_window_size) : i+1]

            # --- Agent Pipeline ---
            try:
                # 1. Glyph
                current_glyph = self.glyph_synth.generate(current_data_row)
                if current_glyph['alignment'] == 'Error': logger.warning(f"Skipping bar {timestamp} due to Glyph error."); continue
                self.glyph_sequence.append(current_glyph)
                # 2. Prediction
                predicted_glyph, rnn_confidence, _ = self.sequence_forecaster.predict(self.glyph_sequence)
                # 3. RL Action
                current_portfolio_state = self.portfolio_manager.get_state()
                rl_action, rl_confidence = self.cognitive_agent.get_action(current_glyph, predicted_glyph, current_data_row, current_portfolio_state)
                # 4. Decision
                provisional_decision, final_confidence, reason = self.decision_engine.decide(
                    current_glyph, predicted_glyph, rnn_confidence or 0.0, rl_action, rl_confidence,
                    current_data_row, current_portfolio_state )
                # 5. Risk & Order Gen
                trade_params = None; formatted_order = None; current_sl = self.portfolio_manager.current_stop_loss # Get current SL before potential update
                # 5a. Check Exit First (using potentially updated SL from previous trailing)
                exit_decision, exit_reason = self.risk_modulator.manage_trailing_stop(current_data_row['Close'], current_data_row.get(f'ATR_{self.config["symbolic"]["frequency_atr_period"]}'), current_portfolio_state['position_size'], current_sl)
                if exit_decision: # If trailing stop hit
                     formatted_order = self.order_orchestrator.format_close_order(current_portfolio_state['position_size'])
                     logger.info(f"Exit Triggered: {exit_decision} by Trailing Stop ({exit_reason})")
                     provisional_decision = exit_decision # Override HDE decision
                elif provisional_decision in ["ENTER_LONG", "ENTER_SHORT"]:
                    trade_params = self.risk_modulator.calculate_trade_params(provisional_decision, current_glyph, current_data_row, current_portfolio_state)
                    if trade_params:
                        formatted_order = self.order_orchestrator.format_order(provisional_decision, trade_params)
                        # Update PM state *before* execution for correct logging/state tracking
                        self.portfolio_manager.update_on_decision(provisional_decision, trade_params)
                    else: provisional_decision = "HOLD"; reason += " | RiskMod Reject Size"
                elif provisional_decision in ["CLOSE_LONG", "CLOSE_SHORT"]:
                    formatted_order = self.order_orchestrator.format_close_order(current_portfolio_state['position_size'])
                    # Update PM state (clear SL/TP)
                    self.portfolio_manager.update_on_decision(provisional_decision, None)


                # 6. Execution
                fill_info = None
                if formatted_order:
                    fill_info = self.execution_engine.execute(formatted_order, current_data_row['Close'])
                # 7. Portfolio Update
                if fill_info:
                    self.portfolio_manager.update_portfolio(fill_info, current_data_row['Close'])
                else: # Update equity even if no fill
                    self.portfolio_manager.update_equity(current_data_row['Close'], timestamp)
                # 8. Adaptation Check
                # Pass the portfolio manager which holds the trade count
                self.adaptive_tuner.check_and_run_optimization(self.portfolio_manager)

            except Exception as e: logger.error(f"Error in backtest loop @ {timestamp}: {e}", exc_info=True)

        logger.info("--- Backtest Loop Finished ---")
        self.performance_metrics = self.portfolio_manager.calculate_performance()
        self._save_results()
        return self.performance_metrics

    def _save_results(self):
        # ... (Identique à la version précédente, utilise self.config) ...
        ts = time.strftime("%Y%m%d-%H%M%S")
        log_prefix = f"syntrader_{self.config['general']['ticker']}_{self.config['general']['interval']}_{ts}"
        try:
            pd.DataFrame(self.portfolio_manager.trade_log).to_csv(f"{log_prefix}_trades.csv", index=False)
            pd.DataFrame(self.portfolio_manager.equity_curve).to_csv(f"{log_prefix}_equity.csv", index=False)
            with open(f"{log_prefix}_config.json", 'w') as f: json.dump(self.config, f, indent=4)
            if self.performance_metrics:
                 with open(f"{log_prefix}_performance.json", 'w') as f: json.dump(self.performance_metrics, f, indent=4)
            logger.info(f"Results saved with prefix: {log_prefix}")
        except Exception as e: logger.error(f"Failed to save results: {e}", exc_info=True)

# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("--- Starting SYNTRADERS Modular Backtest ---")
    # Create orchestrator with the default config
    # The orchestrator now uses a *copy* of the config,
    # allowing the AdaptiveTuner to modify the instance's config during the run.
    orchestrator = SyntraderOrchestrator(default_config)

    # Run the backtest
    performance = orchestrator.run_backtest()

    # Print final performance
    if performance and performance.get("message") is None:
        print("\n\n=== Final Backtest Performance ===")
        for key, value in performance.items():
            print(f"- {key:<25}: {value}")
    else:
        print("\nBacktest failed or produced no valid performance metrics.")
        print(f"Final Metrics Dict: {performance}")

    # Note: Plotting equity requires the backtester instance if using the Backtester class wrapper,
    # or accessing orchestrator.portfolio_manager.equity_curve directly and plotting manually.