class TradeFriendScoring:
    """
    PURPOSE:
    - Score quality of trade (0–10)
    """

    def score(self, df):
        score = 0
        last = df.iloc[-1]

        if last.get("rsi", 0) > 60:
            score += 2
        if last["close"] > last.get("ema_50", last["close"]):
            score += 2
        if last["volume"] > df["volume"].rolling(20).mean().iloc[-1]:
            score += 2
        if last.get("adx", 0) > 20:
            score += 2

        return score
