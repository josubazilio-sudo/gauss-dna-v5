import json
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
import os
from pathlib import Path

class ValidationMetrics:
    def __init__(self):
        self.metrics_file = METRICS_PATH
        self.load_metrics()

    def load_metrics(self):
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                self.stats = json.load(f)
        else:
            self.stats = {
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'drawdown': 0.0,
                'expectancy': 0.0,
                'sharpe': 0.0,
                'sortino': 0.0,
                'total_trades': 0
            }

    def update(self, metrics: dict):
        self.stats.update(metrics)
        with open(self.metrics_file, 'w') as f:
            json.dump(self.stats, f)