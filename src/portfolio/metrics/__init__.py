"""Portfolio metrics computation modules.

Each module computes one category of metrics from the canonical holdings
DataFrame and writes results to ~/data/portfolio/metrics/<category>/.

Usage (called automatically by daily_refresh, or manually):
    from portfolio.metrics import allocation, performance, income, risk
    from portfolio.storage.reader import DataReader

    holdings = DataReader().current_holdings()
    allocation.compute_all(holdings)
    performance.compute_all(holdings)
    income.compute_all(holdings)
    risk.compute_all(holdings)
"""
