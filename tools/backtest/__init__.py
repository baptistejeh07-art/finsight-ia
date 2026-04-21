"""FinSight Score backtest — MVP.

Modules :
- fetch_history.py    : télécharge OHLC + ratios historiques via yfinance
- score_history.py    : calcule le Score FinSight à chaque snapshot mensuel
                        (sans look-ahead bias)
- run_backtest.py     : agrège par bucket + calcule perf forward 12m vs SPY

Résultats sortis dans outputs/backtest/ (Parquet/CSV).

Pour lancer le MVP :
    python -m tools.backtest.run_backtest --universe sp100 --years 3
"""
