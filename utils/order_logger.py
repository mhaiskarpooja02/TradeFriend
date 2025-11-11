import logging
import os

# Create logs folder if not exists
os.makedirs("logs", exist_ok=True)

order_logger = logging.getLogger("orders")
order_logger.setLevel(logging.INFO)

# File handler (append mode, no date split)
fh = logging.FileHandler("logs/orders.log", mode="a")
fh.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)

order_logger.addHandler(fh)
