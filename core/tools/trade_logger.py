import csv
from datetime import datetime
class TradeLogger:
    def __init__(self, filename="storage/trade_history.csv"):
        self.filename = filename
        self._init_file()
    def _init_file(self):
        try:
            with open(self.filename, 'x', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'symbol', 'side', 'entry_price', 'exit_price', 'pnl', 'duration_seconds', 'reason'])
        except FileExistsError:
            pass
    def log_trade(self, **kwargs):
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(),
                kwargs.get('symbol'),
                kwargs.get('side'),
                kwargs.get('entry_price'),
                kwargs.get('exit_price'),
                kwargs.get('pnl'),
                kwargs.get('duration'),
                kwargs.get('reason')
            ])
