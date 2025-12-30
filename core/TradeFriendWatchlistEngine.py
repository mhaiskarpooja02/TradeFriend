class TradeFriendWatchlistEngine:
    """
    PURPOSE:
    - Save scanner results to DB
    """

    def __init__(self, watchlist_repo):
        self.repo = watchlist_repo

    def process(self, scan_result):
        if not scan_result:
            return
        self.repo.upsert(scan_result)
