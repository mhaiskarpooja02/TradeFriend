import socket
import time
import threading
import customtkinter as ctk
from utils.logger import get_logger

logger = get_logger(__name__)

class InternetChecker:
    """Monitors internet connectivity and optionally shows popup alerts."""

    def __init__(self, host="8.8.8.8", port=53, timeout=3):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.is_connected = True
        self._popup = None
        self.lock = threading.Lock()

    def check_once(self) -> bool:
        """Check internet connection once."""
        try:
            socket.setdefaulttimeout(self.timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((self.host, self.port))
            return True
        except Exception:
            return False

    def wait_until_connected(self, max_retries=5, delay=3) -> bool:
        """Wait for internet before continuing app startup."""
        for attempt in range(max_retries):
            if self.check_once():
                logger.info(" Internet connection established.")
                self.is_connected = True
                return True
            logger.warning(f"⚠️ No internet connection. Retrying {attempt + 1}/{max_retries}...")
            time.sleep(delay)
        logger.error(" Internet not available after retries. Application will exit.")
        return False

    def _show_popup(self):
        """Show a non-blocking popup warning (Tkinter window)."""
        if self._popup is not None:
            return  # already visible

        self._popup = ctk.CTkToplevel()
        self._popup.title(" Internet Disconnected")
        self._popup.geometry("320x150")
        self._popup.resizable(False, False)
        self._popup.attributes('-topmost', True)

        label = ctk.CTkLabel(
            self._popup,
            text="Internet connection lost.\nPlease check your network.",
            text_color="red",
            font=("Arial", 14, "bold")
        )
        label.pack(padx=20, pady=30)

        self._popup.protocol("WM_DELETE_WINDOW", lambda: None)  # disable close
        logger.warning(" Internet disconnected — popup displayed.")

    def _close_popup(self):
        """Close popup when internet reconnects."""
        if self._popup is not None:
            try:
                self._popup.destroy()
                logger.info(" Internet reconnected — popup closed.")
            except Exception as e:
                logger.error(f"Error closing popup: {e}")
            finally:
                self._popup = None

    def start_background_monitor(self, app=None, interval=5, on_disconnect=None, on_reconnect=None):
        """
        Start background thread to monitor connection.
        - app: Optional CTk root (if provided, popup is shown)
        - interval: check frequency in seconds
        - on_disconnect/on_reconnect: optional callbacks for logic hooks
        """
        def monitor():
            prev_status = self.check_once()
            self.is_connected = prev_status

            while True:
                current_status = self.check_once()

                if current_status != prev_status:
                    with self.lock:
                        self.is_connected = current_status

                    if not current_status:
                        logger.warning(" Internet disconnected.")
                        if app:
                            app.after(0, self._show_popup)
                        if callable(on_disconnect):
                            on_disconnect()
                    else:
                        logger.info(" Internet reconnected.")
                        if app:
                            app.after(0, self._close_popup)
                        if callable(on_reconnect):
                            on_reconnect()

                    prev_status = current_status

                time.sleep(interval)

        threading.Thread(target=monitor, daemon=True).start()
